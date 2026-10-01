from cockpit import schedule


def add_item(browser, db, project, title, start, end=None, kind="phase", **extra):
    data = {"project_id": str(project), "kind": kind, "title": title, "start_date": start,
            "end_date": end or "", "progress": "", "assignee": ""}
    data.update({k: str(v) for k, v in extra.items()})
    response = browser.post("/zeitplan/neu", data)
    assert response.status_code == 302
    return db.execute("SELECT id FROM schedule_items WHERE title = ?", (title,)).fetchone()[0]


def link(browser, pred, succ, lag=0):
    return browser.post(f"/zeitplan/{succ}/vorgaenger", {"pred_id": str(pred),
                                                          "lag_days": str(lag)},
                        follow_redirects=True)


def dates(db, item_id):
    row = db.execute("SELECT start_date, end_date FROM schedule_items WHERE id = ?",
                     (item_id,)).fetchone()
    return row[0], row[1]


def test_milestone_is_one_day_and_page_renders(browser, db, sample):
    kick = add_item(browser, db, sample["project"], "Kick-off", "2030-03-04", "2030-03-20",
                    kind="milestone")
    assert dates(db, kick) == ("2030-03-04", "2030-03-04")
    page = browser.get(f"/zeitplan?projekt={sample['project']}").get_data(as_text=True)
    assert "<svg class=\"gantt\"" in page and "Kick-off" in page
    assert browser.get("/zeitplan").status_code == 200


def test_end_before_start_rejected(browser, db, sample):
    browser.post("/zeitplan/neu", {"project_id": str(sample["project"]), "kind": "phase",
                                   "title": "Falsch", "start_date": "2030-03-10",
                                   "end_date": "2030-03-01", "progress": "", "assignee": ""})
    assert db.execute("SELECT COUNT(*) FROM schedule_items").fetchone()[0] == 0


def test_conflict_detected_and_resolved_with_cascade(browser, db, sample):
    p = sample["project"]
    export = add_item(browser, db, p, "Export", "2030-03-02", "2030-03-20")
    test = add_item(browser, db, p, "Testphase", "2030-03-16", "2030-03-29")
    golive = add_item(browser, db, p, "Go-live", "2030-03-30", kind="milestone")
    link(browser, export, test)
    link(browser, test, golive)
    ov = schedule.overview(db, schedule.util.to_date("2030-03-01"), p)
    assert [c["succ"]["id"] for c in ov["conflicts"]] == [test]
    page = browser.get(f"/zeitplan?projekt={p}").get_data(as_text=True)
    assert "Konflikte im Zeitplan" in page and "Auf 21.03.2030 schieben" in page

    link_id = db.execute("SELECT id FROM schedule_links WHERE succ_id = ?", (test,)).fetchone()[0]
    browser.post(f"/zeitplan/abhaengigkeiten/{link_id}/aufloesen", {"next": "/zeitplan"})
    assert dates(db, test) == ("2030-03-21", "2030-04-03")      # duration kept
    assert dates(db, golive) == ("2030-04-04", "2030-04-04")    # successor moved along
    ov = schedule.overview(db, schedule.util.to_date("2030-03-01"), p)
    assert ov["conflicts"] == []


def test_cycles_and_self_links_rejected(browser, db, sample):
    p = sample["project"]
    a = add_item(browser, db, p, "A", "2030-03-02", "2030-03-05")
    b = add_item(browser, db, p, "B", "2030-03-06", "2030-03-09")
    link(browser, a, b)
    page = link(browser, b, a).get_data(as_text=True)
    assert "Kreis" in page
    link(browser, a, a)
    assert db.execute("SELECT COUNT(*) FROM schedule_links").fetchone()[0] == 1


def test_cross_project_dependency_and_push_on_edit(browser, db, sample):
    browser.post("/projekte/neu", {"name": "Halle", "code": "H3", "client": "", "status": "aktiv",
                                   "priority": "2", "start_date": "", "end_date": "",
                                   "notes": ""})
    other = db.execute("SELECT id FROM projects WHERE code = 'H3'").fetchone()[0]
    elektrik = add_item(browser, db, other, "Abnahme Elektrik", "2030-04-10", kind="milestone")
    aufbau = add_item(browser, db, sample["project"], "Aufbau", "2030-04-12", "2030-04-20")
    link(browser, elektrik, aufbau)
    browser.post(f"/zeitplan/{elektrik}", {"project_id": str(other), "kind": "milestone",
                                           "title": "Abnahme Elektrik", "start_date": "2030-04-15",
                                           "end_date": "", "progress": "", "assignee": "",
                                           "push": "on"})
    assert dates(db, aufbau) == ("2030-04-15", "2030-04-23")
    page = browser.get(f"/zeitplan?projekt={sample['project']}").get_data(as_text=True)
    assert "Abhängigkeiten zu anderen Projekten" in page


def test_project_progress_weighted_by_duration(browser, db, sample):
    p = sample["project"]
    add_item(browser, db, p, "Kurz", "2030-03-01", "2030-03-01", progress=100)
    add_item(browser, db, p, "Lang", "2030-03-02", "2030-03-04", progress=0)
    assert schedule.project_progress(schedule.items(db, p)) == 25


def test_project_with_timeline_cannot_be_deleted(browser, db, sample):
    add_item(browser, db, sample["project"], "Phase", "2030-03-01", "2030-03-02")
    browser.post(f"/projekte/{sample['project']}/loeschen")
    assert db.execute("SELECT COUNT(*) FROM projects WHERE id = ?",
                      (sample["project"],)).fetchone()[0] == 1
