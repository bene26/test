from cockpit import util


def save_week(browser, person, week, cells):
    data = {"person_id": str(person), "week": week}
    data.update(cells)
    return browser.post("/zeiten", data, follow_redirects=True)


def hours(db):
    return {(r[0], r[1], r[2]): r[3] for r in db.execute(
        "SELECT person_id, project_id, work_date, hours FROM time_entries")}


def test_grid_saves_updates_and_deletes(browser, db, sample):
    anna, project = sample["anna"], sample["project"]
    page = save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-04": "7,5",
                                                f"h_{project}_2030-03-05": "8"})
    assert "Gespeichert: 15,5 h in KW 10" in page.get_data(as_text=True)
    assert hours(db) == {(anna, project, "2030-03-04"): 7.5, (anna, project, "2030-03-05"): 8}
    save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-04": "6",
                                         f"h_{project}_2030-03-05": ""})
    assert hours(db) == {(anna, project, "2030-03-04"): 6}
    page = browser.get(f"/zeiten?person={anna}&woche=2030-W10").get_data(as_text=True)
    assert 'value="6"' in page and "Mo 04.03." in page


def test_rejects_cells_outside_the_week_and_too_many_hours(browser, db, sample):
    anna, project = sample["anna"], sample["project"]
    page = save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-20": "5"})
    assert "passt nicht zur gewählten Woche" in page.get_data(as_text=True)
    page = save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-04": "25"})
    assert "höchstens 24" in page.get_data(as_text=True)
    page = save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-04": "abc"})
    assert "muss eine Zahl sein" in page.get_data(as_text=True)
    browser.post("/zeiten", {"person_id": str(anna), "week": "2030-W10", "evil": "1"})
    assert hours(db) == {}


def test_day_total_limit_across_projects(browser, db, sample):
    browser.post("/projekte/neu", {"name": "Zwei", "code": "", "client": "", "status": "aktiv",
                                   "priority": "2", "start_date": "", "end_date": "",
                                   "notes": ""})
    second = db.execute("SELECT id FROM projects WHERE name = 'Zwei'").fetchone()[0]
    page = save_week(browser, sample["anna"], "2030-W10",
                     {f"h_{sample['project']}_2030-03-04": "14",
                      f"h_{second}_2030-03-04": "11"})
    assert "mehr als 24 Stunden" in page.get_data(as_text=True)
    assert hours(db) == {}


def test_copy_previous_week_and_team_view_and_csv(browser, db, sample):
    anna, project = sample["anna"], sample["project"]
    save_week(browser, anna, "2030-W10", {f"h_{project}_2030-03-04": "4"})
    browser.post("/zeiten/vorwoche", {"person_id": str(anna), "week": "2030-W11"})
    assert hours(db)[(anna, project, "2030-03-11")] == 4
    team = browser.get("/zeiten/team?woche=2030-W11").get_data(as_text=True)
    assert "Anna" in team and "4 h" in team
    csv = browser.client.get("/zeiten/export.csv?monat=2030-03").get_data(as_text=True)
    assert "04.03.2030;Anna;;ERP;ERP;4" in csv


def test_person_with_hours_cannot_be_deleted(browser, db, sample):
    save_week(browser, sample["anna"], "2030-W10", {f"h_{sample['project']}_2030-03-04": "4"})
    browser.post(f"/team/personen/{sample['anna']}/loeschen")
    assert db.execute("SELECT COUNT(*) FROM people WHERE id = ?",
                      (sample["anna"],)).fetchone()[0] == 1


def test_week_parsing():
    from cockpit.views.times import parse_week
    today = util.to_date("2026-10-01")
    assert parse_week("2026-W41", today).isoformat() == "2026-10-05"
    assert parse_week("2026-W99", today).isoformat() == "2026-09-28"
    assert parse_week("x", today).isoformat() == "2026-09-28"
