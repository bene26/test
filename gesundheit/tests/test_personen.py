"""Several persons under one login: switching, separate data, deleting, migration from v1."""

import sqlite3
from datetime import datetime

from gesundheit import db as dbmod
from gesundheit import persons, store


def at(day="2026-09-01", hour=7):
    return datetime.fromisoformat(f"{day} {hour:02d}:00:00")


def test_first_person_is_named_after_account(logged_in, db, me):
    assert persons.get(db, me)["name"] == "anna"
    assert ", anna</h1>" in logged_in.get("/").get_data(as_text=True)


def test_create_and_switch(logged_in, db, me):
    logged_in.get("/personen")
    response = logged_in.post("/personen", {"name": "Lena", "color": "gruen"})
    lena = db.execute("SELECT id FROM persons WHERE name = 'Lena'").fetchone()[0]
    assert response.headers["Location"].endswith(f"/personen/{lena}")
    page = logged_in.get("/").get_data(as_text=True)
    assert "Lena" in page and 'class="avatar p-gruen"' in page
    logged_in.post(f"/personen/{me}/zeigen", {"next": "/koerper"})
    assert "anna" in logged_in.get("/").get_data(as_text=True)


def test_switch_redirects_only_locally(logged_in, me):
    response = logged_in.post(f"/personen/{me}/zeigen", {"next": "https://boese.example/"})
    assert response.headers["Location"] == "/"


def test_unknown_person_cookie_falls_back(app, logged_in, me):
    logged_in.client.set_cookie(persons.COOKIE, "999")
    assert logged_in.get("/").status_code == 200
    logged_in.client.set_cookie(persons.COOKIE, "<script>")
    assert logged_in.get("/").status_code == 200
    assert logged_in.get("/personen/999").status_code == 404


def test_values_stay_with_their_person(logged_in, db, me):
    other = persons.create(db, "Ben", "blau")
    store.add_measurement(db, other, "weight", 91.0, at(), "withings")
    store.set_daily(db, other, "steps", "2026-09-01", "garmin", 12000)
    db.commit()
    assert store.latest(db, me, "weight") is None
    assert store.daily_series(db, me, "steps", "2026-09-01", "2026-09-01") == []
    assert "91,0" not in logged_in.get("/koerper?zeitraum=365").get_data(as_text=True)


def test_delete_person_needs_name_and_cascades(logged_in, db, me):
    other = persons.create(db, "Ben", "blau")
    store.add_measurement(db, other, "weight", 91.0, at(), "withings")
    db.commit()
    logged_in.get(f"/personen/{other}")
    logged_in.post(f"/personen/{other}/loeschen", {"bestaetigung": "ben"})
    assert persons.get(db, other)
    logged_in.post(f"/personen/{other}/loeschen", {"bestaetigung": "Ben"})
    assert persons.get(db, other) is None
    assert db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 0


def test_last_person_cannot_be_deleted(logged_in, db, me):
    logged_in.get(f"/personen/{me}")
    logged_in.post(f"/personen/{me}/loeschen", {"bestaetigung": "anna"})
    assert persons.get(db, me)


def test_order_of_persons(logged_in, db, me):
    other = persons.create(db, "Ben", "blau")
    db.commit()
    logged_in.get("/personen")
    logged_in.post("/personen/reihenfolge", {"person": str(other), "richtung": "hoch"})
    assert [p["id"] for p in persons.all_persons(db)] == [other, me]


def test_delete_data_of_one_person(logged_in, db, me):
    other = persons.create(db, "Ben", "blau")
    store.add_measurement(db, me, "weight", 80.0, at(), "withings")
    store.add_measurement(db, other, "weight", 91.0, at(), "withings")
    db.commit()
    logged_in.get("/daten")
    logged_in.post("/daten/loeschen/person", {"bestaetigung": "anna"})
    assert store.latest(db, me, "weight") is None and store.latest(db, other, "weight")
    assert persons.get(db, me)


def test_error_page_keeps_navigation(logged_in):
    response = logged_in.client.post("/personen", data={"name": "X", "color": "rot",
                                                        "csrf_token": "falsch"})
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert 'class="person-wahl"' in page and "Formular ist abgelaufen" in page


def test_migration_from_version_1(tmp_path):
    path = tmp_path / "alt.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(dbmod.MIGRATIONS[0])
    conn.execute("PRAGMA user_version = 1")
    conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES ('mia', 'x', '2026-01-01')")
    conn.executemany("INSERT INTO settings (key, value) VALUES (?, ?)",
                     [("goal_steps", "7000"), ("height_cm", "170"), ("garmin_enabled", "1"),
                      ("retention_days", "365")])
    conn.execute("INSERT INTO measurements (metric, value, measured_at, day, source) VALUES "
                 "('weight', 70, '2026-09-01 07:00:00', '2026-09-01', 'withings')")
    conn.execute("INSERT INTO daily_values VALUES ('steps', '2026-09-01', 'garmin', 9000, 'x')")
    conn.execute("INSERT INTO sleep (night, source, asleep_min) VALUES ('2026-09-01', 'garmin', 400)")
    conn.execute("INSERT INTO workouts (source, external_id, kind, started_at, day) VALUES "
                 "('garmin', '1', 'laufen', '2026-09-01 18:00:00', '2026-09-01')")
    conn.execute("INSERT INTO connections (provider, secret_enc) VALUES ('withings', 'abc')")
    conn.execute("INSERT INTO imports (kind, filename, status, started_at) VALUES "
                 "('apple', 'e.zip', 'fertig', 'x')")
    conn.commit()
    conn.close()
    dbmod.init_db(path)
    conn = dbmod.connect(path)
    person = dict(conn.execute("SELECT * FROM persons").fetchone())
    assert person["id"] == 1 and person["name"] == "mia"
    assert person["goal_steps"] == 7000 and person["height_cm"] == 170 and person["garmin_enabled"] == 1
    for table in ("measurements", "daily_values", "sleep", "workouts", "connections", "imports"):
        assert conn.execute(f"SELECT person_id FROM {table}").fetchone()[0] == 1, table
    keys = {r[0] for r in conn.execute("SELECT key FROM settings")}
    assert keys == {"retention_days"}
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(dbmod.MIGRATIONS)
    assert store.latest(conn, 1, "weight")["value"] == 70
    conn.close()


def test_fresh_database_has_no_person_until_login(app, db):
    assert db.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
