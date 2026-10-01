from cockpit import themes

from .conftest import PASSWORD, add_task

LOOK = {"theme": "violett", "modus": "hell", "akzent": "blau", "schrift": "gross",
        "ecken": "rund", "menue": "neon", "zahlen": "fallblatt", "grafik": "kartei"}


def test_save_appearance_renders_attributes_and_cookies(app, browser, db):
    response = browser.post("/einstellungen/darstellung", LOOK)
    assert response.status_code == 302
    row = db.execute("SELECT theme, appearance FROM users").fetchone()
    assert row[0] == "violett" and themes.load_look(row[1])["menue"] == "neon"
    page = browser.get("/").get_data(as_text=True)
    head = page.split(">", 2)[1]
    for attr in ('data-theme="violett"', 'data-mode="hell"', 'data-accent="blau"',
                 'data-size="gross"', 'data-shape="rund"', 'data-menu="neon"',
                 'data-digits="fallblatt"', 'data-grafik="kartei"', 'data-tone="hell"',
                 'data-nav="voll"'):
        assert attr in head, attr
    assert browser.client.get_cookie(themes.LOOK_COOKIE).value == \
        "hell.blau.gross.rund.neon.fallblatt.kartei"

    browser.post("/abmelden")
    login = browser.get("/anmelden").get_data(as_text=True).split(">", 2)[1]
    assert 'data-accent="blau"' in login and 'data-theme="violett"' in login


def test_defaults_leave_attributes_out(browser):
    head = browser.get("/").get_data(as_text=True).split(">", 2)[1]
    assert 'data-theme="glas"' in head and "data-accent" not in head and "data-menu" not in head


def test_invalid_values_are_rejected(browser, db):
    page = browser.post("/einstellungen/darstellung", {**LOOK, "akzent": "#ff0000"},
                        follow_redirects=True).get_data(as_text=True)
    assert "Akzentfarbe" in page and "ungültigen Wert" in page
    assert db.execute("SELECT appearance FROM users").fetchone()[0] == ""
    browser.post("/einstellungen/darstellung", {**LOOK, "extra": "1"})
    assert db.execute("SELECT appearance FROM users").fetchone()[0] == ""


def test_forged_cookies_are_ignored(app):
    client = app.test_client()
    client.set_cookie(themes.LOOK_COOKIE, 'hell.<x>.gross.rund."neon')
    client.set_cookie(themes.NAV_COOKIE, '"><script>')
    page = client.get("/einrichten").get_data(as_text=True)
    head = page.split(">", 2)[1]
    assert "<x>" not in page and "data-accent" not in head
    assert themes.look_from_cookie("a.b") == themes.DEFAULT_LOOK
    assert themes.look_from_cookie("a.b.c.d.e.f.g.h") == themes.DEFAULT_LOOK


def test_cookie_from_before_the_digits_option_still_works():
    look = themes.look_from_cookie("hell.blau.gross.rund.neon")
    assert look["menue"] == "neon" and look["zahlen"] == "" and look["grafik"] == ""


def test_sidebar_state_from_cookie_only_for_sidebar_designs(browser):
    browser.client.set_cookie(themes.NAV_COOKIE, "mini")
    assert 'data-nav="mini"' in browser.get("/").get_data(as_text=True).split(">", 2)[1]
    browser.post("/einstellungen/darstellung", {**LOOK, "theme": "bronze"})
    assert "data-nav" not in browser.get("/").get_data(as_text=True).split(">", 2)[1]


def test_menu_badges_and_sections(browser, sample):
    from datetime import timedelta
    from cockpit import util
    add_task(browser, "Alt", due_date=(util.today() - timedelta(days=2)).isoformat())
    page = browser.get("/").get_data(as_text=True)
    assert '<span class="nav-section" aria-hidden="true">Planung</span>' in page
    assert '<span class="nav-badge"><span class="sr-only">: </span>1<span class="sr-only"> überfällig</span></span>' in page
    assert 'data-nav-toggle' in page and 'role="search"' in page


def test_login_page_v7(anon, app, browser):
    browser.post("/abmelden")
    page = browser.get("/anmelden").get_data(as_text=True)
    assert 'class="v7-card"' in page and "data-toggle-password" in page
    assert "Willkommen <em>zurück</em>" in page
    response = browser.post("/anmelden", {"username": "pl", "password": PASSWORD})
    assert response.status_code == 302
