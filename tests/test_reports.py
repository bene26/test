from cockpit import notify, reports, util
from cockpit.views.times import month_range

from .conftest import add_task
from .test_orders import new_order, record
from .test_schedule import add_item, link


def test_status_report_lights_and_content(browser, db, sample):
    p = sample["project"]
    a = add_item(browser, db, p, "Export", "2020-01-01", "2020-01-10")
    b = add_item(browser, db, p, "Testphase", "2020-01-05", "2020-01-20")
    link(browser, a, b)
    add_item(browser, db, p, "Go-live", "2099-01-01", kind="milestone")
    add_task(browser, "Alt", project_id=p, due_date="2020-01-01")
    order_id = new_order(browser, sample["firm"], project_id=p, amount="10")
    record(browser, order_id, "12")
    page = browser.get(f"/berichte/status?projekt={p}").get_data(as_text=True)
    assert "Projektstatus" in page and "Go-live" in page
    assert "light-rot" in page            # conflict and overrun
    assert "Testphase beginnt vor dem Ende von Export" in page
    first, last = month_range(util.today().strftime("%Y-%m"), util.today())
    items = reports.build(db, util.today(), first, last, p)
    assert items[0]["lights"]["Termine"] == "rot"
    assert items[0]["lights"]["Kontingent"] == "rot"
    text = reports.as_text(items, util.today().replace(day=1))
    assert "Konflikt: Testphase beginnt vor Ende von Export" in text


def test_report_overview_and_protocol_archive(browser, db, sample):
    page = browser.get("/berichte").get_data(as_text=True)
    assert "Projektstatus" in page and "Protokolle" in page
    assert browser.get("/berichte/status").status_code == 200
    csv = browser.client.get("/berichte/kontingente.csv")
    assert csv.status_code == 200 and csv.mimetype == "text/csv"


def test_send_status_validates_recipients(browser, sample, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "smtp_configured", lambda: True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append((to, subject)))
    page = browser.post("/berichte/status/senden", {"monat": "2030-03", "projekt": "",
                                                    "recipients": "nicht-gueltig"},
                        follow_redirects=True).get_data(as_text=True)
    assert "gültige E-Mail-Adressen" in page and not sent
    browser.post("/berichte/status/senden", {"monat": "2030-03", "projekt": "",
                                             "recipients": "a@firma.de, b@firma.de"})
    assert sent == [(["a@firma.de", "b@firma.de"], "Projektstatus März 2030")]
