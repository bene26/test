from pathlib import Path

from cockpit.auth import SESSION_COOKIE, SETUP_FILE

from .conftest import PASSWORD, setup_code


def test_first_visit_redirects_to_setup(anon):
    response = anon.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/einrichten")


def test_setup_rejects_wrong_code(anon, db):
    anon.get("/einrichten")
    response = anon.post("/einrichten", {"code": "FALSCH", "username": "x",
                                         "password": PASSWORD, "password2": PASSWORD},
                         follow_redirects=True)
    assert "Einrichtungscode stimmt nicht" in response.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_setup_rejects_short_password(app, anon, db):
    anon.get("/einrichten")
    response = anon.post("/einrichten", {"code": setup_code(app), "username": "x",
                                         "password": "kurz", "password2": "kurz"},
                         follow_redirects=True)
    assert "mindestens 12 Zeichen" in response.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_setup_creates_account_once_and_removes_code(app, browser, db):
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert not Path(app.config["DATA_DIR"], SETUP_FILE).exists()
    assert db.execute("SELECT COUNT(*) FROM meta WHERE key = 'setup_code'").fetchone()[0] == 0
    response = browser.get("/einrichten")
    assert response.status_code == 302


def test_password_is_hashed(browser, db):
    stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert PASSWORD not in stored
    assert stored.startswith("scrypt:")


def test_login_logout_revokes_session(app, browser, db):
    cookie = browser.client.get_cookie(SESSION_COOKIE).value
    assert browser.get("/").status_code == 200
    browser.post("/abmelden")
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    other = app.test_client()
    other.set_cookie(SESSION_COOKIE, cookie)
    assert other.get("/").status_code == 302


def test_wrong_password_and_throttle(app, browser):
    browser.post("/abmelden")
    browser.get("/anmelden")
    for _ in range(5):
        response = browser.post("/anmelden", {"username": "pl", "password": "falsch-falsch-1"},
                                follow_redirects=True)
        assert "falsch" in response.get_data(as_text=True)
    response = browser.post("/anmelden", {"username": "pl", "password": PASSWORD},
                            follow_redirects=True)
    assert "Zu viele Fehlversuche" in response.get_data(as_text=True)


def test_login_ignores_foreign_redirect(browser):
    browser.post("/abmelden")
    browser.get("/anmelden")
    response = browser.post("/anmelden", {"username": "pl", "password": PASSWORD,
                                          "next": "//evil.example/x"})
    assert response.status_code == 302
    assert "evil" not in response.headers["Location"]


def test_post_without_csrf_is_rejected(browser):
    response = browser.client.post("/projekte/neu", data={"name": "X"})
    assert response.status_code == 400


def test_unknown_form_fields_are_rejected(browser, db):
    response = browser.post("/projekte/neu", {"name": "X", "is_admin": "1"}, follow_redirects=True)
    assert "unerwartete Felder" in response.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_security_headers(browser):
    response = browser.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_session_cookie_flags(browser):
    cookie = browser.client.get_cookie(SESSION_COOKIE)
    assert cookie.http_only
    assert cookie.same_site == "Lax"


def test_health_is_public(anon):
    assert anon.get("/health").status_code == 200


def test_password_change_signs_out_other_devices(app, browser, db):
    other = app.test_client()
    other.get("/anmelden")
    from .conftest import Browser
    second = Browser(other)
    second.get("/anmelden")
    second.post("/anmelden", {"username": "pl", "password": PASSWORD})
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    browser.post("/einstellungen/passwort", {"current": PASSWORD, "new": "ein-neues-passwort",
                                             "new2": "ein-neues-passwort"})
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    assert second.get("/").status_code == 302
    assert browser.get("/").status_code == 200


def test_manage_resets_password(app, browser, db, monkeypatch, capsys):
    from cockpit import manage
    answers = iter(["ganz-neues-passwort", "ganz-neues-passwort"])
    monkeypatch.setattr(manage.getpass, "getpass", lambda prompt="": next(answers))
    assert manage.main(["passwort", "pl"]) == 0
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert browser.get("/").status_code == 302
    browser.get("/anmelden")
    response = browser.post("/anmelden", {"username": "pl", "password": "ganz-neues-passwort"})
    assert response.headers["Location"] == "/"
    assert manage.main(["passwort", "gibtsnicht"]) == 1
