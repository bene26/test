import json

from cockpit import notify
from cockpit.meeting_types import MEETING_TYPES


def new_meeting(browser, **fields):
    data = {"type": "jourfixe", "title": "", "project_id": "", "firm_id": "",
            "date": "2030-03-04", "time": "10:00", "duration_min": "", "location": "",
            "participants": ""}
    data.update({k: str(v) for k, v in fields.items()})
    response = browser.post("/meetings/neu", data)
    assert response.status_code == 302
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def editor_data(db, meeting_id, **overrides):
    m = db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    data = {"title": m["title"], "project_id": m["project_id"] or "", "firm_id": m["firm_id"] or "",
            "date": m["starts_at"][:10], "time": m["starts_at"][11:16],
            "duration_min": m["duration_min"], "location": m["location"],
            "participants": m["participants"]}
    for item in db.execute("SELECT id, title, notes FROM agenda_items WHERE meeting_id = ?",
                           (meeting_id,)):
        data[f"title_{item['id']}"] = item["title"]
        data[f"note_{item['id']}"] = item["notes"]
    data.update(overrides)
    return {k: str(v) for k, v in data.items()}


def test_agenda_comes_from_template(browser, sample, db):
    meeting_id = new_meeting(browser, firm_id=sample["firm"], project_id=sample["project"])
    titles = [r[0] for r in db.execute(
        "SELECT title FROM agenda_items WHERE meeting_id = ? ORDER BY position", (meeting_id,))]
    assert titles == [t for t, _ in MEETING_TYPES["jourfixe"]["agenda"]]
    title = db.execute("SELECT title FROM meetings").fetchone()[0]
    assert title == "Jour fixe · Alpha GmbH · ERP"


def test_action_becomes_task_and_shows_up_in_next_meeting(browser, sample, db):
    first = new_meeting(browser, firm_id=sample["firm"], project_id=sample["project"])
    browser.post(f"/meetings/{first}/massnahmen", {"title": "Schnittstelle beschreiben",
                                                   "assignee": f"f:{sample['firm']}",
                                                   "due_date": "2030-03-10"})
    task = db.execute("SELECT * FROM tasks").fetchone()
    assert task["meeting_id"] == first and task["firm_id"] == sample["firm"]
    assert task["project_id"] == sample["project"]
    browser.post(f"/meetings/{first}/folgetermin", {"date": "2030-03-11", "time": "10:00"})
    second = db.execute("SELECT id FROM meetings WHERE previous_meeting_id = ?",
                        (first,)).fetchone()[0]
    text = browser.get(f"/meetings/{second}").get_data(as_text=True)
    assert "Schnittstelle beschreiben" in text


def test_decision_numbers_per_project(browser, sample, db):
    meeting_id = new_meeting(browser, project_id=sample["project"])
    browser.post(f"/meetings/{meeting_id}/entscheidungen", {"text": "CSV statt XML"})
    browser.post(f"/meetings/{meeting_id}/entscheidungen", {"text": "Go-live im Mai"})
    other = new_meeting(browser)
    browser.post(f"/meetings/{other}/entscheidungen", {"text": "ohne Projekt"})
    numbers = [tuple(r) for r in db.execute("SELECT project_id, number FROM decisions ORDER BY id")]
    assert numbers == [(sample["project"], 1), (sample["project"], 2), (None, 1)]
    text = browser.get(f"/projekte/{sample['project']}").get_data(as_text=True)
    assert "E-02" in text and "Go-live im Mai" in text


def test_autosave_saves_notes(browser, sample, db):
    meeting_id = new_meeting(browser)
    item_id = db.execute("SELECT id FROM agenda_items LIMIT 1").fetchone()[0]
    response = browser.client.post(
        f"/meetings/{meeting_id}",
        data=editor_data(db, meeting_id, **{f"note_{item_id}": "Import zu 80 % fertig"}),
        headers={"X-Autosave": "1", "X-CSRF-Token": browser.token})
    assert response.status_code == 204
    assert db.execute("SELECT notes FROM agenda_items WHERE id = ?",
                      (item_id,)).fetchone()[0] == "Import zu 80 % fertig"


def test_finalize_freezes_and_correction_makes_new_version(browser, sample, db):
    meeting_id = new_meeting(browser, participants="Chefin <chefin@example.com>")
    item_id = db.execute("SELECT id FROM agenda_items LIMIT 1").fetchone()[0]
    browser.post(f"/meetings/{meeting_id}/abschliessen",
                 editor_data(db, meeting_id, **{f"note_{item_id}": "Version eins"}))
    assert db.execute("SELECT protocol_status, version FROM meetings").fetchone()[:] == \
        ("abgeschlossen", 1)
    snapshot = json.loads(db.execute("SELECT snapshot_json FROM protocol_versions").fetchone()[0])
    assert snapshot["agenda"][0]["notes"] == "Version eins"

    # Frozen: further edits are refused.
    response = browser.post(f"/meetings/{meeting_id}/entscheidungen", {"text": "zu spät"})
    assert response.status_code == 302
    assert db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0

    browser.post(f"/meetings/{meeting_id}/korrektur")
    browser.post(f"/meetings/{meeting_id}/abschliessen",
                 editor_data(db, meeting_id, **{f"note_{item_id}": "Version zwei"}))
    versions = db.execute("SELECT version, snapshot_json FROM protocol_versions "
                          "ORDER BY version").fetchall()
    assert [v[0] for v in versions] == [1, 2]
    assert json.loads(versions[0][1])["agenda"][0]["notes"] == "Version eins"
    assert "Version zwei" in browser.get(f"/meetings/{meeting_id}").get_data(as_text=True)
    assert browser.get(f"/meetings/{meeting_id}/druck?version=1").status_code == 200


def test_finalize_and_send(browser, sample, db, monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_FROM", "cockpit@example.com")
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append((to, body)))
    meeting_id = new_meeting(browser, participants="Chefin <chefin@example.com>\nOhne Mail")
    data = editor_data(db, meeting_id)
    data["send"] = "1"
    browser.post(f"/meetings/{meeting_id}/abschliessen", data)
    assert sent and sent[0][0] == ["chefin@example.com"]
    assert "PROTOKOLL" in sent[0][1]
    assert db.execute("SELECT sent_to FROM protocol_versions").fetchone()[0] == "chefin@example.com"


def test_meeting_with_protocol_cannot_be_deleted(browser, sample, db):
    meeting_id = new_meeting(browser)
    browser.post(f"/meetings/{meeting_id}/abschliessen", editor_data(db, meeting_id))
    browser.post(f"/meetings/{meeting_id}/loeschen")
    assert db.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 1


def test_missing_protocol_listed(browser, sample, db):
    new_meeting(browser, date="2020-01-01")
    text = browser.get("/").get_data(as_text=True)
    assert "Protokoll fehlt" in text
    assert db.execute("SELECT COUNT(*) FROM meetings WHERE protocol_status = 'offen'"
                      ).fetchone()[0] == 1
