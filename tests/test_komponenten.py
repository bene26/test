"""Server side of the components: Strg+K search, "Frag das Cockpit", paper plane, receipt."""

import json
from datetime import timedelta

from cockpit import assistent, dashboard, notify, util

from .conftest import add_task
from .test_orders import new_order, record

JSON = {"Accept": "application/json"}


def ask(browser, question):
    response = browser.client.get("/assistent", query_string={"frage": question}, headers=JSON)
    assert response.status_code == 200 and response.mimetype == "application/json"
    return response.get_json()


def test_search_finds_everything_and_needs_login(anon, browser, db, sample):
    add_task(browser, "Schnittstelle 100% fertig", project_id=sample["project"])
    new_order(browser, sample["firm"], number="4500999", title="Wartung")
    assert anon.client.get("/suche.json?q=ERP").status_code == 302
    hits = browser.client.get("/suche.json?q=ERP", headers=JSON).get_json()["treffer"]
    assert {"titel": "ERP", "gruppe": "Projekt"}.items() <= hits[0].items()
    groups = {h["gruppe"] for h in browser.client.get("/suche.json?q=a").get_json()["treffer"]}
    assert groups == set()                                   # single letters are ignored
    for query, group in (("Schnittstelle", "Aufgabe"), ("Alpha", "Firma"), ("Anna", "Person"),
                         ("4500999", "Bestellung")):
        hits = browser.client.get("/suche.json", query_string={"q": query}).get_json()["treffer"]
        assert any(h["gruppe"] == group for h in hits), query
    # LIKE wildcards are matched literally
    hits = browser.client.get("/suche.json", query_string={"q": "100%"}).get_json()["treffer"]
    assert [h["titel"] for h in hits] == ["Schnittstelle 100% fertig"]
    assert browser.client.get("/suche.json", query_string={"q": "_%"}).get_json()["treffer"] == []


def test_assistant_answers_from_data(browser, db, sample):
    yesterday = (util.today() - timedelta(days=1)).isoformat()
    add_task(browser, "Abnahme vorbereiten", due_date=yesterday)
    answer = ask(browser, "Was ist überfällig?")
    assert "1 Aufgabe ist überfällig" in answer["absaetze"][0]
    assert answer["links"][0]["text"] == "Abnahme vorbereiten"
    assert "Kalenderwoche" in ask(browser, "Fasse meine Woche zusammen")["absaetze"][0]
    assert "keine kommenden Meetings" in ask(browser, "Wann ist das nächste Meeting?")["absaetze"][0]
    assert "keine aktiven Bestellungen" in ask(browser, "Wie stehen die Kontingente?")["absaetze"][0]
    order_id = new_order(browser, sample["firm"], amount="10")
    record(browser, order_id, "12")
    quota = ask(browser, "Kontingente?")
    assert "Alpha GmbH" in quota["absaetze"][0] and quota["links"][0]["text"] == "Alpha GmbH"
    assert "keine Konflikte" in ask(browser, "Gibt es Konflikte im Zeitplan?")["absaetze"][0]
    assert "niemand überbucht" in ask(browser, "Wer ist überbucht?")["absaetze"][0]
    assert "keine Stunden" in ask(browser, "Wie viele Stunden sind erfasst?")["absaetze"][0]
    assert "ohne KI" in ask(browser, "Hilfe")["absaetze"][0]
    found = ask(browser, "Wo ist die Abnahme?")
    assert found["links"] and found["links"][0]["text"] == "Abnahme vorbereiten"
    assert "nichts gefunden" in ask(browser, "Quantenphysik")["absaetze"][0]


def test_assistant_page_without_javascript_escapes(browser):
    page = browser.get("/assistent?frage=<b>Hallo</b>").get_data(as_text=True)
    assert "Frag das Cockpit" in page and "&lt;b&gt;Hallo&lt;/b&gt;" in page
    assert "<b>Hallo</b>" not in page
    long = ask(browser, "x" * 5000)
    assert long["absaetze"]


def test_start_page_has_orb_flaps_and_card_file(browser, db):
    page = browser.get("/").get_data(as_text=True)
    assert 'data-orb data-orb-quelle="/assistent"' in page
    assert '<div class="stats" data-fallblatt>' in page
    assert 'data-kartei data-kartei-suche="/suche.json"' in page
    assert 'data-tasten="G A"' in page and "komponenten.js" in page
    # A start page saved before the orb existed gets it behind the key figures.
    old = [e for e in dashboard.default_layout() if e["k"] != "assistent"]
    keys = [e["k"] for e in dashboard.load(json.dumps(old))]
    assert keys.index("assistent") == keys.index("kennzahlen") + 1


def test_card_file_anchors_exist(browser, sample):
    assert 'id="neu" data-fokus' in browser.get("/meetings").get_data(as_text=True)
    assert 'id="neu" data-fokus' in browser.get("/projekte").get_data(as_text=True)
    schedule = browser.get(f"/zeitplan?projekt={sample['project']}").get_data(as_text=True)
    assert 'id="neu" data-fokus' in schedule
    team = browser.get("/team").get_data(as_text=True)
    assert 'id="neue-person"' in team and 'id="neue-firma"' in team


def test_key_and_lock_on_setup(anon):
    setup = anon.get("/einrichten").get_data(as_text=True)
    assert 'data-schluessel data-passwort="password" data-wiederholung="password2"' in setup
    assert 'data-regel="laenge"' in setup and "data-kartei" not in setup


def test_key_and_lock_on_password_change(browser):
    settings = browser.get("/einstellungen").get_data(as_text=True)
    assert 'data-passwort="pw-new" data-wiederholung="pw-new2"' in settings
    assert 'name="zahlen" value="fallblatt"' in settings


def test_order_receipt(browser, sample):
    order_id = new_order(browser, sample["firm"], amount="100")
    record(browser, order_id, "40")
    record(browser, order_id, "5", status="eingereicht")
    page = browser.get(f"/bestellungen/{order_id}").get_data(as_text=True)
    assert "data-bon" in page and 'data-bon-vorlage="nachweise"' in page
    assert 'data-bon-barcode="4500123"' in page and "Kontingent-Beleg" in page
    assert "60 h" in page                                    # free


def test_send_status_answers_json_for_the_paper_plane(browser, sample, monkeypatch):
    sent = []
    headers = {"X-Cockpit-Ajax": "1", "Accept": "application/json"}
    form = {"monat": "2030-03", "projekt": "", "recipients": "a@firma.de",
            "csrf_token": browser.token}
    monkeypatch.setattr(notify, "smtp_configured", lambda: False)
    reply = browser.client.post("/berichte/status/senden", data=form, headers=headers).get_json()
    assert reply == {"ok": False, "nachricht": "E-Mail-Versand ist nicht eingerichtet (siehe Einstellungen)."}
    monkeypatch.setattr(notify, "smtp_configured", lambda: True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append(to))
    bad = browser.client.post("/berichte/status/senden", headers=headers,
                              data={**form, "recipients": "kaputt"}).get_json()
    assert bad["ok"] is False and "gültige E-Mail-Adressen" in bad["nachricht"]
    missing = browser.client.post("/berichte/status/senden", headers=headers,
                                  data={**form, "monat": ""}).get_json()
    assert missing["ok"] is False and "Monat" in missing["nachricht"]
    good = browser.client.post("/berichte/status/senden", data=form, headers=headers).get_json()
    assert good == {"ok": True, "nachricht": "Statusbericht an 1 Empfänger versendet."}
    assert sent == [["a@firma.de"]]
    # The flash messages of the JSON requests do not show up later.
    assert "nicht eingerichtet" not in browser.get("/berichte").get_data(as_text=True)


def test_fold_and_stopwords():
    assert assistent.fold("Überfällig ÄÖß") == "ueberfaellig aeoess"
    assert "was" in assistent.STOPWORDS
