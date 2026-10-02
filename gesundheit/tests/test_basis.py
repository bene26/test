"""Login, CSRF, security headers, error pages and the design shared with the cockpit."""

import importlib.util
from pathlib import Path

import pytest

from conftest import PASSWORD, Browser
from gesundheit import auth, themes

REPO = Path(__file__).resolve().parents[2]
PAGES = ["/", "/koerper", "/herz", "/schlaf", "/aktivitaet", "/quellen", "/einstellungen",
         "/daten", "/personen", "/auswertungen", "/auswertungen/zusammenhaenge", "/vergleich",
         "/berichte", "/verlauf/weight", "/personen/1", "/suche.json?q=ge",
         "/quellen/import/1.json"]


def _cockpit_module(name):
    spec = importlib.util.spec_from_file_location(f"cockpit_{name}", REPO / "cockpit" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_start_needs_setup_code(app, browser):
    response = browser.get("/")
    assert response.status_code == 302 and response.headers["Location"].endswith("/einrichten")
    page = browser.get("/einrichten").get_data(as_text=True)
    assert "Einrichtungscode" in page and "Gesundheits-Cockpit" in page
    wrong = browser.post("/einrichten", {"code": "FALSCH", "username": "anna",
                                         "password": "x" * 12, "password2": "x" * 12})
    assert wrong.status_code == 302
    assert "Einrichtungscode stimmt nicht" in browser.get("/einrichten").get_data(as_text=True)


@pytest.mark.parametrize("url", PAGES)
def test_every_page_needs_login(app, logged_in, url):
    client = app.test_client()  # fresh client without session
    response = client.get(url)
    assert response.status_code == 302
    assert "/anmelden" in response.headers["Location"]


@pytest.mark.parametrize("url", PAGES[:15])
def test_pages_render_without_data(logged_in, url):
    response = logged_in.get(url)
    assert response.status_code == 200, url


def test_empty_overview_explains_next_steps(logged_in):
    page = logged_in.get("/").get_data(as_text=True)
    assert "Noch keine Daten" in page and "Withings" in page and "Apple" in page


def test_post_without_csrf_is_rejected(logged_in):
    response = logged_in.client.post("/personen", data={"name": "Eve", "color": "rot"})
    assert response.status_code == 400
    assert "Formular ist abgelaufen" in response.get_data(as_text=True)


def test_security_headers(logged_in):
    response = logged_in.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp and "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert 'style="' not in response.get_data(as_text=True)


def test_cookie_names_differ_from_cockpit(logged_in):
    cookies = {c.key for c in logged_in.client._cookies.values()}
    assert "gs_session" in cookies
    assert not cookies & {"pc_session", "pc_form", "pc_theme", "pc_look"}


def test_design_options_match_cockpit():
    cockpit_themes = _cockpit_module("themes")
    # Every cockpit design exists here unchanged; the health app adds "Indigo" as its default.
    assert {k: v for k, v in themes.THEMES.items() if k in cockpit_themes.THEMES} \
        == cockpit_themes.THEMES
    assert set(themes.THEMES) - set(cockpit_themes.THEMES) == {"indigo"}
    assert themes.DEFAULT == "indigo"
    assert themes.APPEARANCE == cockpit_themes.APPEARANCE
    for name in themes.THEMES:
        assert name in themes.DEFAULT_TONE and name in themes.DEFAULT_GRAFIK
    assert {k: themes.DEFAULT_GRAFIK[k] for k in cockpit_themes.DEFAULT_GRAFIK} \
        == cockpit_themes.DEFAULT_GRAFIK
    assert themes.LOOK_COOKIE != cockpit_themes.LOOK_COOKIE


def test_shared_static_files_are_served_publicly(app):
    client = app.test_client()
    for name in ("app.css", "komponenten.js", "app.js"):
        response = client.get(f"/gemeinsam/{name}")
        assert response.status_code == 200, name
        response.close()
    assert client.get("/static/gesundheit.css").status_code == 200
    assert client.get("/health").get_json() == {"status": "ok"}


def test_404_uses_shared_graphics_with_own_name(logged_in):
    response = logged_in.get("/gibt-es-nicht")
    page = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Seite nicht gefunden" in page and "data-grafik-bild" in page
    assert "Gesundheits-Cockpit" in page and "Projekt-Cockpit</strong>" not in page


def test_only_error_graphics_come_from_cockpit(app):
    with app.app_context():
        assert app.jinja_env.get_template("_grafiken.html")
        with pytest.raises(Exception):
            app.jinja_env.get_template("dashboard.html")  # cockpit-only template


def test_json_errors(logged_in):
    response = logged_in.client.get("/gibt-es-nicht", headers={"Accept": "application/json"})
    assert response.status_code == 404 and response.get_json()["ok"] is False


def test_change_password_signs_out_other_devices(app, logged_in):
    other = app.test_client()
    other.post("/anmelden", data={"username": "anna", "password": PASSWORD,
                                  "csrf_token": _anon_token(other)})
    assert other.get("/").status_code == 200
    logged_in.get("/einstellungen")
    logged_in.post("/einstellungen/passwort", {"current": PASSWORD, "new": "neues-passwort-12345",
                                               "new2": "neues-passwort-12345"})
    assert other.get("/").status_code == 302
    assert logged_in.get("/").status_code == 200


def _anon_token(client):
    import re
    page = client.get("/anmelden").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def test_login_throttle_blocks_after_five_failures(app):
    client = app.test_client()
    auth.throttle.reset("login:127.0.0.1")
    b = Browser(client)
    # create the account first
    code = Path(app.config["DATA_DIR"], "EINRICHTUNGSCODE.txt").read_text().split(": ", 1)[1].split()[0]
    b.get("/einrichten")
    b.post("/einrichten", {"code": code, "username": "anna", "password": "x" * 14,
                           "password2": "x" * 14})
    b.post("/abmelden")
    fresh = Browser(app.test_client())
    for _ in range(5):
        fresh.get("/anmelden")
        fresh.post("/anmelden", {"username": "anna", "password": "falsch-falsch"})
    fresh.get("/anmelden")
    fresh.post("/anmelden", {"username": "anna", "password": "x" * 14})
    assert fresh.get("/").status_code == 302
    auth.throttle.reset("login:127.0.0.1")


def test_appearance_is_saved_and_validated(logged_in):
    logged_in.get("/einstellungen")
    logged_in.post("/einstellungen/darstellung", {"theme": "bronze", "akzent": "gelb",
                                                  "grafik": "bon"})
    page = logged_in.get("/").get_data(as_text=True)
    assert 'data-theme="bronze"' in page and 'data-accent="gelb"' in page
    logged_in.post("/einstellungen/darstellung", {"theme": "bronze", "akzent": "#ff0000"})
    assert 'data-accent="gelb"' in logged_in.get("/").get_data(as_text=True)


def test_key_file_is_private(app):
    key = Path(app.config["DATA_DIR"]) / "schluessel"
    assert key.exists() and oct(key.stat().st_mode & 0o777) == "0o600"
