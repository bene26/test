import re
from pathlib import Path

import pytest

from cockpit import auth, create_app
from cockpit.db import connect

PASSWORD = "sehr-geheimes-passwort"
TOKEN_RE = re.compile(r'name="csrf(?:_token|-token)" (?:value|content)="([^"]+)"')


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("NTFY_URL", "NTFY_TOPIC", "NTFY_TOKEN", "SMTP_HOST", "SMTP_FROM", "SMTP_USER",
                 "SMTP_PASSWORD", "REMINDER_EMAIL_TO", "COCKPIT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COCKPIT_DATA_DIR", str(tmp_path))
    auth.throttle._failures.clear()
    return create_app({"SCHEDULER": False, "TESTING": True})


@pytest.fixture
def db(app):
    conn = connect(app.config["DATABASE"])
    yield conn
    conn.close()


class Browser:
    """Test client that keeps track of the current CSRF token."""

    def __init__(self, client):
        self.client = client
        self.token = None

    def _remember(self, response):
        match = TOKEN_RE.search(response.get_data(as_text=True))
        if match:
            self.token = match.group(1)
        return response

    def get(self, url, **kwargs):
        return self._remember(self.client.get(url, **kwargs))

    def post(self, url, data=None, **kwargs):
        data = dict(data or {})
        if self.token is None:
            self.get("/")
        data.setdefault("csrf_token", self.token)
        return self._remember(self.client.post(url, data=data, **kwargs))


def setup_code(app) -> str:
    text = (Path(app.config["DATA_DIR"]) / auth.SETUP_FILE).read_text(encoding="utf-8")
    return text.split(": ", 1)[1].split()[0]


@pytest.fixture
def anon(app):
    return Browser(app.test_client())


@pytest.fixture
def browser(app):
    b = Browser(app.test_client())
    b.get("/einrichten")
    response = b.post("/einrichten", {"code": setup_code(app), "username": "pl",
                                      "password": PASSWORD, "password2": PASSWORD})
    assert response.status_code == 302
    b.get("/")
    return b


@pytest.fixture
def sample(browser, db):
    """One project, a firm under Werkvertrag, one under ANÜ, two people."""
    browser.post("/projekte/neu", {"name": "ERP", "code": "ERP", "client": "", "status": "aktiv",
                                   "priority": "2", "start_date": "", "end_date": "",
                                   "notes": ""})
    browser.post("/team/firmen/neu", {"name": "Alpha GmbH", "contract_type": "werkvertrag",
                                      "contact_name": "", "contact_email": "",
                                      "contact_phone": "", "notes": ""})
    browser.post("/team/firmen/neu", {"name": "Beta AG", "contract_type": "anue",
                                      "contact_name": "", "contact_email": "",
                                      "contact_phone": "", "notes": ""})
    browser.post("/team/personen/neu", {"name": "Anna", "role": "Backend", "email": "",
                                        "weekly_hours": "40", "availability": "80",
                                        "firm_id": ""})
    return {
        "project": db.execute("SELECT id FROM projects").fetchone()[0],
        "firm": db.execute("SELECT id FROM firms WHERE name = 'Alpha GmbH'").fetchone()[0],
        "anue_firm": db.execute("SELECT id FROM firms WHERE name = 'Beta AG'").fetchone()[0],
        "anna": db.execute("SELECT id FROM people WHERE name = 'Anna'").fetchone()[0],
    }


def add_task(browser, title, **fields):
    data = {"title": title, "project_id": "", "assignee": "", "due_date": "",
            "effort_hours": ""}
    data.update({k: str(v) for k, v in fields.items()})
    response = browser.post("/aufgaben/neu", data)
    assert response.status_code == 302
    return response
