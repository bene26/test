import json

from cockpit import dashboard

ALL = list(dashboard.WIDGETS)


def stored(db):
    return json.loads(db.execute("SELECT dashboard FROM users").fetchone()[0])


def test_default_start_page_shows_default_widgets(browser):
    page = browser.get("/").get_data(as_text=True)
    for key, (label, _desc, visible, _wide) in dashboard.WIDGETS.items():
        if key == "routinen":
            continue  # only shown when a routine is due
        assert (f'id="w-{key}"' in page) == visible, key
    assert "Startseite anpassen" in page


def test_edit_mode_lists_every_widget_with_tools(browser):
    page = browser.get("/?anpassen=1").get_data(as_text=True)
    for key in ALL:
        assert f'name="order" value="{key}"' in page
    assert 'id="layout"' in page and "inert" in page


def test_save_hide_show_wide_and_order(browser, db):
    order = ["zeiten"] + [k for k in ALL if k != "zeiten"]
    shown = [k for k in ALL if k != "kalender"]
    response = browser.post("/startseite", {"order": order, "show": shown, "wide": ["zeiten"],
                                            "done": "1"})
    assert response.headers["Location"].endswith("/")
    layout = stored(db)
    assert layout[0] == {"k": "zeiten", "v": True, "w": True}
    assert {"k": "kalender", "v": False, "w": False} in layout
    page = browser.get("/").get_data(as_text=True)
    assert 'id="w-kalender"' not in page
    assert page.index('id="w-zeiten"') < page.index('id="w-kennzahlen"')
    assert 'widget-zeiten wide' in page


def test_move_buttons_and_reset(browser, db):
    browser.post("/startseite", {"order": ALL, "show": ALL, "wide": [], "move": "meetings:up"})
    keys = [e["k"] for e in stored(db)]
    assert keys.index("meetings") == ALL.index("meetings") - 1
    browser.post("/startseite", {"reset": "1"})
    assert stored(db) == dashboard.default_layout()


def test_invalid_layout_input_rejected(browser, db):
    browser.post("/startseite", {"order": ["kennzahlen", "<script>"], "show": []})
    browser.post("/startseite", {"order": ALL, "move": "x;drop:up"})
    assert db.execute("SELECT dashboard FROM users").fetchone()[0] == ""


def test_load_is_robust():
    assert dashboard.load("") == dashboard.default_layout()
    assert dashboard.load("{kaputt") == dashboard.default_layout()
    layout = dashboard.load(json.dumps([{"k": "zeiten", "v": True, "w": False},
                                        {"k": "gibt-es-nicht", "v": True},
                                        {"k": "zeiten", "v": False}]))
    assert layout[0] == {"k": "zeiten", "v": True, "w": False}
    assert [e["k"] for e in layout].count("zeiten") == 1
    assert len(layout) == len(ALL)


def test_widgets_render_with_data(browser, db, sample):
    from .test_orders import new_order
    from .test_schedule import add_item
    add_item(browser, db, sample["project"], "Kick-off", "2099-01-05", kind="milestone")
    new_order(browser, sample["firm"])
    browser.post("/startseite", {"order": ALL, "show": ALL, "wide": [], "done": "1"})
    page = browser.get("/").get_data(as_text=True)
    assert "Alpha GmbH" in page            # quota widget
    assert 'class="cal"' in page           # calendar
    assert "Zeiten diese Woche" in page
    assert browser.get("/?kal=2099-01").status_code == 200
    assert browser.get("/?kal=kaputt").status_code == 200
