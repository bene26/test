"""Error pages with the switchable graphics (404 and the others)."""

import importlib.util
from pathlib import Path

import cockpit
from cockpit import auth

ROOT = Path(__file__).resolve().parent.parent
GRAPHICS = ("fallblatt", "loch", "bon", "flieger", "kartei", "schluessel")


def test_404_page_has_all_graphics_links_and_escapes_the_path(browser):
    response = browser.get("/projekte/<b>alt</b>")
    page = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Seite nicht gefunden" in page and "Fehler 404" in page
    for key in GRAPHICS:
        assert f'data-grafik-bild="{key}"' in page, key
    assert "&lt;b&gt;alt&lt;/b&gt;" in page and "<b>alt</b>" not in page
    assert "Oder direkt zu:" in page and "data-kartei-oeffnen" in page
    assert "NICHT GEFUNDEN" in page and "Beleg Nr. 404" in page


def test_missing_entry_uses_the_same_page(browser):
    page = browser.get("/aufgaben/99999")
    assert page.status_code == 404 and "Seite nicht gefunden" in page.get_data(as_text=True)


def test_other_errors_are_german(browser, anon):
    page = browser.get("/startseite")                       # POST only
    assert page.status_code == 405 and "So geht das nicht" in page.get_data(as_text=True)
    expired = browser.client.post("/startseite", data={"csrf_token": "falsch"})
    text = expired.get_data(as_text=True)
    assert expired.status_code == 400 and "Das Formular ist abgelaufen" in text
    assert 'data-grafik-bild="bon"' in text


def test_errors_answer_json_when_asked(browser):
    reply = browser.client.get("/gibt-es-nicht", headers={"Accept": "application/json"})
    assert reply.status_code == 404 and reply.get_json()["ok"] is False
    plane = browser.client.post("/berichte/status/senden", data={"csrf_token": "falsch"},
                                headers={"X-Cockpit-Ajax": "1"})
    assert plane.status_code == 400 and "abgelaufen" in plane.get_json()["nachricht"]


def test_server_error_page_and_fallback(app, monkeypatch):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/kaputt")
    def kaputt():
        raise RuntimeError("geheime Einzelheit")

    monkeypatch.setattr(auth, "PUBLIC_ENDPOINTS", auth.PUBLIC_ENDPOINTS | {"kaputt"})
    client = app.test_client()
    page = client.get("/kaputt")
    text = page.get_data(as_text=True)
    assert page.status_code == 500 and "Etwas ist schiefgelaufen" in text
    assert "geheime Einzelheit" not in text and "STÖRUNG" in text

    def broken(*args, **kwargs):
        raise RuntimeError("Vorlage kaputt")
    monkeypatch.setattr(cockpit, "render_template", broken)
    plain = client.get("/kaputt")
    assert plain.status_code == 500 and plain.mimetype == "text/plain"
    assert "Etwas ist schiefgelaufen" in plain.get_data(as_text=True)


def test_graphic_choice_in_settings(browser, db):
    settings = browser.get("/einstellungen").get_data(as_text=True)
    assert 'name="grafik" value="schluessel"' in settings and "grafik-vorschau" in settings
    browser.post("/einstellungen/darstellung", {"theme": "violett", "grafik": "flieger"})
    head = browser.get("/gibt-es-nicht").get_data(as_text=True).split(">", 2)[1]
    assert 'data-grafik="flieger"' in head
    bad = browser.post("/einstellungen/darstellung", {"theme": "violett", "grafik": "rakete"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Grafik für Fehlerseiten" in bad and "ungültigen Wert" in bad


def test_design_kit_404_page_is_current():
    spec = importlib.util.spec_from_file_location("build_404_page", ROOT / "tools" / "build_404_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current = (ROOT / "design-kit" / "404.html").read_text(encoding="utf-8")
    assert current == module.build(), "python3 tools/build_404_page.py ausführen"
    for key in GRAPHICS:
        assert f'data-grafik-bild="{key}"' in current
    assert "data-fehler-pfad" in current and "§" not in current
