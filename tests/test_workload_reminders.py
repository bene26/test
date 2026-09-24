from datetime import date, datetime

import pytest

from cockpit import data, forms, notify, reminders
from cockpit.db import connect

from .conftest import add_task

MONDAY = date(2030, 3, 4)


def test_effort_is_spread_until_due_week(browser, sample, db):
    # Due on Friday of the third week: 30 h over three weeks.
    add_task(browser, "Konzept", assignee=f"p:{sample['anna']}", due_date="2030-03-22",
             effort_hours="30")
    result = data.workload(db, MONDAY, weeks=4)
    anna = next(p for p in result["people"] if p["name"] == "Anna")
    hours = [round(c["hours"], 1) for c in anna["cells"]]
    assert hours == [10.0, 10.0, 10.0, 0.0]
    # 10 h of 32 h net capacity (40 h × 80 %).
    assert round(anna["cells"][0]["percent"]) == 31
    assert anna["cells"][0]["level"] == "frei"


def test_overdue_effort_counts_in_current_week(browser, sample, db):
    add_task(browser, "Alt", assignee=f"p:{sample['anna']}", due_date="2030-02-01",
             effort_hours="40")
    anna = data.workload(db, MONDAY, weeks=2)["people"][0]
    assert anna["cells"][0]["hours"] == 40
    assert anna["cells"][0]["level"] == "ueber"
    assert anna["overdue"] == 1


def test_firm_load_and_unplanned(browser, sample, db):
    add_task(browser, "Mit Aufwand", assignee=f"f:{sample['firm']}", due_date="2030-03-06",
             effort_hours="12")
    add_task(browser, "Ohne Aufwand", assignee=f"f:{sample['firm']}")
    firm = next(f for f in data.workload(db, MONDAY, weeks=2)["firms"] if f["id"] == sample["firm"])
    assert firm["cells"][0]["hours"] == 12
    assert firm["open"] == 2 and firm["unplanned"] == 1


@pytest.mark.parametrize("percent,level", [(0, "frei"), (69.9, "frei"), (70, "ok"),
                                           (94.9, "ok"), (95, "voll"), (105, "voll"),
                                           (105.1, "ueber")])
def test_levels(percent, level):
    assert data.level(percent) == level


@pytest.fixture
def pushes(monkeypatch):
    sent = []
    monkeypatch.setenv("NTFY_URL", "http://ntfy.local")
    monkeypatch.setenv("NTFY_TOPIC", "cockpit-test")
    monkeypatch.setattr(notify, "send_ntfy", lambda title, message, click="": sent.append(
        (title, message)))
    return sent


def test_morning_digest_once_and_without_details(app, browser, sample, pushes):
    add_task(browser, "Geheimer Titel", due_date="2020-01-01")
    ran = reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 7, 31))
    assert "digest:2030-03-04" in ran
    assert len([p for p in pushes if p[0] == "Guten Morgen"]) == 1
    assert "1 überfällig" in pushes[0][1]
    assert all("Geheimer Titel" not in message for _, message in pushes)
    reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 7, 45))
    assert len([p for p in pushes if p[0] == "Guten Morgen"]) == 1


def test_no_digest_before_time_or_on_weekend(app, browser, sample, pushes):
    add_task(browser, "Alt", due_date="2020-01-01")
    reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 7, 0))
    reminders.run_due_jobs(app.config, datetime(2030, 3, 9, 9, 0))  # Saturday
    assert pushes == []


def test_weekly_planning_repeats_until_done(app, browser, sample, pushes):
    reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 8, 46))
    assert ("Wochenplanung" in [p[0] for p in pushes])
    reminders.run_due_jobs(app.config, datetime(2030, 3, 5, 8, 46))
    assert [p[0] for p in pushes].count("Wochenplanung") == 2
    db = connect(app.config["DATABASE"])
    db.execute("INSERT INTO routine_checks VALUES ('wochenplanung', '2030-W10', '2030-03-05')")
    db.commit()
    db.close()
    reminders.run_due_jobs(app.config, datetime(2030, 3, 6, 8, 46))
    assert [p[0] for p in pushes].count("Wochenplanung") == 2


def test_meeting_preparation_reminder(app, browser, sample, pushes):
    browser.post("/meetings/neu", {"type": "team", "title": "", "project_id": "", "firm_id": "",
                                   "date": "2030-03-05", "time": "09:00", "duration_min": "",
                                   "location": "", "participants": ""})
    reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 15, 5))
    assert ("Meetings vorbereiten" in [p[0] for p in pushes])


def test_backup_created_and_pruned(app, browser):
    folder = reminders.Path(app.config["DATA_DIR"]) / "backups"
    folder.mkdir()
    for day in range(1, 21):
        (folder / f"cockpit-2030-01-{day:02d}.sqlite3").write_text("x")
    reminders.run_due_jobs(app.config, datetime(2030, 3, 4, 3, 0))
    files = sorted(p.name for p in folder.glob("cockpit-*.sqlite3"))
    assert len(files) == reminders.BACKUP_KEEP
    assert files[-1] == "cockpit-2030-03-04.sqlite3"


def test_due_routines_month_end(db):
    assert [r["key"] for r in data.due_routines(db, date(2030, 3, 29))] == [
        "wochenabschluss", "monatsbericht"]
    assert [r["period"] for r in data.due_routines(db, date(2030, 4, 2))
            if r["key"] == "monatsbericht"] == ["2030-03"]
    assert not [r for r in data.due_routines(db, date(2030, 4, 10)) if r["key"] == "monatsbericht"]


class Form(dict):
    def getlist(self, key):
        value = self.get(key)
        return [] if value is None else value if isinstance(value, list) else [value]


def test_forms_validation():
    spec = {"title": forms.Text("Titel", required=True, max_len=5),
            "hours": forms.Number("Stunden", min_value=0, max_value=10),
            "who": forms.Assignee("Zuständig")}
    assert forms.parse(Form(title="ab", hours="2,5", who="p:3"), spec) == \
        {"title": "ab", "hours": 2.5, "who": (3, None)}
    for bad in (Form(title=""), Form(title="zu lang"), Form(title="a", hours="11"),
                Form(title="a", who="x:1"), Form(title="a", extra="1"),
                Form(title="a\x00")):
        with pytest.raises(forms.ValidationError):
            forms.parse(bad, spec)
    assert forms.Date("Datum").parse("2032-02-29") == "2032-02-29"
    with pytest.raises(forms.ValidationError):
        forms.Date("Datum").parse("2030-02-30")
