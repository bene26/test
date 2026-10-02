import re

import pytest

from gesundheit import create_app
from gesundheit.db import connect

PASSWORD = "ein-sehr-langes-passwort-1"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("GESUNDHEIT_KEY", raising=False)
    app = create_app({
        "DATA_DIR": str(tmp_path / "data"),
        "TESTING": True,
        "SCHEDULER": False,
        "BACKGROUND_JOBS": False,
        "IMPORT_DIR": str(tmp_path / "import"),
        "BASE_URL": "http://nas.local:8090",
        "WITHINGS_CLIENT_ID": "",
        "WITHINGS_CLIENT_SECRET": "",
    })
    yield app


@pytest.fixture
def db(app):
    conn = connect(app.config["DATABASE"])
    yield conn
    conn.close()


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "kein CSRF-Token in der Seite"
    return match.group(1)


class Browser:
    """Test client that carries the CSRF token like a browser form would."""

    def __init__(self, client):
        self.client = client
        self.token = None

    def get(self, url, **kwargs):
        response = self.client.get(url, **kwargs)
        text = response.get_data(as_text=True)
        if 'name="csrf_token"' in text:
            self.token = csrf_from(text)
        return response

    def post(self, url, data=None, **kwargs):
        data = dict(data or {})
        data.setdefault("csrf_token", self.token)
        return self.client.post(url, data=data, **kwargs)


@pytest.fixture
def browser(app):
    return Browser(app.test_client())


@pytest.fixture
def logged_in(app, browser):
    code = (app.config["DATA_DIR"] + "/EINRICHTUNGSCODE.txt")
    with open(code, encoding="utf-8") as fh:
        setup_code = fh.read().split(": ", 1)[1].split()[0]
    browser.get("/einrichten")
    response = browser.post("/einrichten", {"code": setup_code, "username": "anna",
                                            "password": PASSWORD, "password2": PASSWORD})
    assert response.status_code == 302
    browser.get("/")
    return browser
