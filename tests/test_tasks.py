from datetime import timedelta

from cockpit import util

from .conftest import add_task


def test_quick_add_and_list(browser, sample):
    add_task(browser, "Schnittstelle testen", project_id=sample["project"],
             assignee=f"f:{sample['firm']}", due_date="2030-01-10", effort_hours="16")
    text = browser.get("/aufgaben").get_data(as_text=True)
    assert "Schnittstelle testen" in text
    assert "Alpha GmbH" in text


def test_overdue_filter(browser, sample):
    add_task(browser, "Alt", due_date="2020-01-01")
    add_task(browser, "Neu", due_date="2099-01-01")
    text = browser.get("/aufgaben?ansicht=ueberfaellig").get_data(as_text=True)
    assert "Alt" in text and ">Neu<" not in text


def test_status_change_sets_done_at(browser, sample, db):
    add_task(browser, "Erledigen")
    task_id = db.execute("SELECT id FROM tasks").fetchone()[0]
    browser.post(f"/aufgaben/{task_id}/status", {"status": "erledigt"})
    row = db.execute("SELECT status, done_at FROM tasks").fetchone()
    assert row["status"] == "erledigt" and row["done_at"]
    browser.post(f"/aufgaben/{task_id}/status", {"status": "offen"})
    assert db.execute("SELECT done_at FROM tasks").fetchone()[0] is None


def test_bulk_postpone_and_delete(browser, sample, db):
    add_task(browser, "A", due_date="2030-01-01")
    add_task(browser, "B")
    ids = [r[0] for r in db.execute("SELECT id FROM tasks ORDER BY id")]
    browser.post("/aufgaben/sammel", {"ids": [str(i) for i in ids], "action": "verschieben"})
    dues = [r[0] for r in db.execute("SELECT due_date FROM tasks ORDER BY id")]
    assert dues[0] == "2030-01-08"
    assert dues[1] == (util.today() + timedelta(days=7)).isoformat()
    browser.post("/aufgaben/sammel", {"ids": [str(ids[0])], "action": "loeschen"})
    assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1


def test_bulk_assign_validates_reference(browser, sample, db):
    add_task(browser, "A")
    task_id = db.execute("SELECT id FROM tasks").fetchone()[0]
    response = browser.post("/aufgaben/sammel", {"ids": str(task_id), "action": "zuweisen",
                                                 "bulk_assignee": "f:999"}, follow_redirects=True)
    assert "gibt es nicht" in response.get_data(as_text=True)


def test_edit_task(browser, sample, db):
    add_task(browser, "Alt")
    task_id = db.execute("SELECT id FROM tasks").fetchone()[0]
    browser.post(f"/aufgaben/{task_id}", {
        "title": "Neu", "project_id": str(sample["project"]), "assignee": f"p:{sample['anna']}",
        "due_date": "2030-02-01", "start_date": "", "effort_hours": "4,5", "priority": "1",
        "status": "wartet", "waiting_for": "Testdaten", "description": "Zeile 1\nZeile 2"})
    row = db.execute("SELECT * FROM tasks").fetchone()
    assert (row["title"], row["person_id"], row["effort_hours"], row["status"]) == \
        ("Neu", sample["anna"], 4.5, "wartet")
    assert row["description"] == "Zeile 1\nZeile 2"


def test_person_of_contract_firm_cannot_be_planned_individually(browser, sample, db):
    response = browser.post("/team/personen/neu", {
        "name": "Extern", "role": "", "email": "", "weekly_hours": "40", "availability": "80",
        "firm_id": str(sample["firm"])}, follow_redirects=True)
    assert "Arbeitnehmerüberlassung" in response.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM people WHERE name = 'Extern'").fetchone()[0] == 0
    browser.post("/team/personen/neu", {
        "name": "Leih", "role": "", "email": "", "weekly_hours": "40", "availability": "80",
        "firm_id": str(sample["anue_firm"])})
    assert db.execute("SELECT COUNT(*) FROM people WHERE name = 'Leih'").fetchone()[0] == 1


def test_csv_export_neutralises_formulas(browser, sample):
    add_task(browser, "=HYPERLINK(\"http://x\")")
    response = browser.get("/aufgaben/export.csv")
    text = response.get_data(as_text=True)
    assert response.mimetype == "text/csv"
    assert "'=HYPERLINK" in text


def test_search_escapes_wildcards(browser, sample):
    add_task(browser, "100% fertig")
    add_task(browser, "Anderes")
    text = browser.get("/aufgaben?q=%25").get_data(as_text=True)
    assert "100% fertig" in text and "Anderes" not in text


def test_title_is_escaped(browser, sample):
    add_task(browser, "<script>alert(1)</script>")
    text = browser.get("/aufgaben").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;" in text


def test_dashboard_counts(browser, sample):
    add_task(browser, "Liegt zurück", due_date=(util.today() - timedelta(days=3)).isoformat())
    text = browser.get("/").get_data(as_text=True)
    assert "Liegt zurück" in text
    assert 'class="stat alert"' in text
