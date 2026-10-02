from datetime import timedelta

from cockpit import quotas, util

from .conftest import add_task


def new_order(browser, firm, **fields):
    data = {"number": "4500123", "title": "Schnittstellen", "project_id": "", "unit": "h",
            "amount": "100", "hours_per_day": "", "valid_from": "", "valid_to": "", "notes": ""}
    data.update({k: str(v) for k, v in fields.items()})
    response = browser.post(f"/bestellungen/neu/{firm}", data)
    assert response.status_code == 302
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def record(browser, order_id, amount, status="geprueft"):
    browser.post(f"/bestellungen/{order_id}/nachweise",
                 {"period_start": "2030-03-01", "period_end": "2030-03-31", "amount": amount,
                  "description": "März", "status": status})


def test_order_usage_and_warnings(browser, db, sample):
    order_id = new_order(browser, sample["firm"], amount="100")
    record(browser, order_id, "50")
    record(browser, order_id, "35,5")
    record(browser, order_id, "10", status="eingereicht")
    o = quotas.order(db, order_id, util.today())
    assert o["billed"] == 85.5 and o["pending"] == 10
    assert o["level"] == "voll" and "86 % verbraucht" in o["warnings"]
    page = browser.get(f"/bestellungen/{order_id}").get_data(as_text=True)
    assert "85,5 h" in page and "86 % verbraucht" in page


def test_person_days_are_converted_for_the_firm_summary(browser, db, sample):
    new_order(browser, sample["firm"], unit="pt", amount="10", hours_per_day="8")
    add_task(browser, "Paket A", assignee=f"f:{sample['firm']}", effort_hours=90)
    summary = quotas.firm_summary(db, util.today(), sample["firm"])[0]
    assert summary["ordered"] == 80 and summary["planned"] == 90
    assert summary["level"] == "ueber" and summary["warnings"][0].startswith("überplant")
    page = browser.get(f"/team/firmen/{sample['firm']}").get_data(as_text=True)
    assert "überplant" in page
    assert "Kontingent verplant" in browser.get("/auslastung").get_data(as_text=True)


def test_expiry_warning(browser, db, sample):
    soon = (util.today() + timedelta(days=10)).isoformat()
    order_id = new_order(browser, sample["firm"], valid_to=soon)
    assert "läuft in 10 Tagen ab" in quotas.order(db, order_id, util.today())["warnings"]


def test_rejected_records_do_not_count_and_status_change(browser, db, sample):
    order_id = new_order(browser, sample["firm"])
    record(browser, order_id, "40", status="abgelehnt")
    assert quotas.order(db, order_id, util.today())["billed"] == 0
    rid = db.execute("SELECT id FROM service_records").fetchone()[0]
    browser.post(f"/bestellungen/nachweise/{rid}/status", {"status": "geprueft"})
    assert quotas.order(db, order_id, util.today())["billed"] == 40


def test_invalid_order_values_rejected(browser, db, sample):
    browser.post(f"/bestellungen/neu/{sample['firm']}",
                 {"number": "", "title": "X", "project_id": "", "unit": "kg", "amount": "5",
                  "hours_per_day": "", "valid_from": "", "valid_to": "", "notes": ""})
    browser.post(f"/bestellungen/neu/{sample['firm']}",
                 {"number": "", "title": "X", "project_id": "", "unit": "h", "amount": "5",
                  "hours_per_day": "", "valid_from": "2030-05-01", "valid_to": "2030-04-01",
                  "notes": ""})
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_order_with_records_cannot_be_deleted_and_blocks_firm_delete(browser, db, sample):
    order_id = new_order(browser, sample["firm"])
    record(browser, order_id, "5")
    browser.post(f"/bestellungen/{order_id}/loeschen")
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1
    browser.post(f"/team/firmen/{sample['firm']}/loeschen")
    assert db.execute("SELECT COUNT(*) FROM firms WHERE id = ?",
                      (sample["firm"],)).fetchone()[0] == 1
