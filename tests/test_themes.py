from cockpit import themes

from .conftest import PASSWORD


def test_default_design_before_login(anon):
    page = anon.get("/einrichten").get_data(as_text=True)
    assert f'data-theme="{themes.DEFAULT}"' in page


def test_settings_offer_all_designs(browser):
    page = browser.get("/einstellungen").get_data(as_text=True)
    for key in themes.THEMES:
        assert f'name="theme" value="{key}"' in page
        assert f'class="theme-preview" data-theme="{key}"' in page


def test_save_design_per_user_and_remember_for_login(app, browser, db):
    response = browser.post("/einstellungen/darstellung", {"theme": "bronze"})
    assert response.status_code == 302
    assert db.execute("SELECT theme FROM users").fetchone()[0] == "bronze"
    assert browser.client.get_cookie(themes.COOKIE).value == "bronze"
    assert 'data-theme="bronze"' in browser.get("/").get_data(as_text=True)

    browser.post("/abmelden")
    assert 'data-theme="bronze"' in browser.get("/anmelden").get_data(as_text=True)

    # A fresh browser learns the design at login.
    other = type(browser)(app.test_client())
    other.get("/anmelden")
    other.post("/anmelden", {"username": "pl", "password": PASSWORD})
    assert 'data-theme="bronze"' in other.get("/").get_data(as_text=True)
    assert other.client.get_cookie(themes.COOKIE).value == "bronze"


def test_unknown_design_is_rejected(browser, db):
    response = browser.post("/einstellungen/darstellung", {"theme": "x\" onload=\"alert(1)"},
                            follow_redirects=True)
    assert "ungültigen Wert" in response.get_data(as_text=True)
    assert db.execute("SELECT theme FROM users").fetchone()[0] == ""


def test_unexpected_fields_are_rejected(browser, db):
    browser.post("/einstellungen/darstellung", {"theme": "hell", "user_id": "2"})
    assert db.execute("SELECT theme FROM users").fetchone()[0] == ""


def test_forged_cookie_falls_back_to_default(anon):
    anon.client.set_cookie(themes.COOKIE, '"><script>')
    page = anon.get("/einrichten").get_data(as_text=True)
    assert f'data-theme="{themes.DEFAULT}"' in page
    assert "<script>" not in page.split("<body>", 1)[0].replace(
        '<script src="/static/app.js', "")


def test_design_change_needs_login(browser, db):
    browser.post("/abmelden")
    browser.get("/anmelden")
    response = browser.post("/einstellungen/darstellung", {"theme": "hell"})
    assert response.status_code == 302
    assert "/anmelden" in response.headers["Location"]
    assert db.execute("SELECT theme FROM users").fetchone()[0] == ""


def test_fonts_are_served_locally(app, browser):
    css = browser.get("/static/app.css").get_data(as_text=True)
    assert "fonts.googleapis" not in css and "gstatic" not in css
    response = browser.client.get("/static/fonts/geist.woff2")
    assert response.status_code == 200
    assert response.mimetype == "font/woff2"


def test_existing_database_gets_theme_column(tmp_path):
    from cockpit import db as dbmod

    path = tmp_path / "alt.sqlite3"
    conn = dbmod.connect(path)
    conn.executescript(dbmod.MIGRATIONS[0])
    conn.execute("PRAGMA user_version = 1")
    conn.execute("INSERT INTO users (username, password_hash, created_at) "
                 "VALUES ('pl', 'x', '2026-01-01')")
    conn.commit()
    conn.close()

    dbmod.init_db(path)
    conn = dbmod.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(dbmod.MIGRATIONS)
        assert conn.execute("SELECT theme FROM users").fetchone()[0] == ""
    finally:
        conn.close()
