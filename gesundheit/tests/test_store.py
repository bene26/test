"""Source order, daily values, readings, sleep and workouts."""

from datetime import date, datetime, timedelta

from gesundheit import store

D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)


def at(day, hour=7, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute)


def test_first_source_in_order_wins_per_day(db, pid):
    store.set_daily_many(db, pid, [
        ("steps", D1, "garmin", 9000), ("steps", D1, "apple_watch", 8500),
        ("steps", D1, "iphone", 6000),
        ("steps", D2, "apple_watch", 7000), ("steps", D2, "iphone", 5000),
        ("steps", D3, "iphone", 4000),
    ])
    series = store.daily_series(db, pid, "steps", D1, D3)
    assert [(s["day"], s["value"], s["source"]) for s in series] == [
        ("2026-09-01", 9000, "garmin"), ("2026-09-02", 7000, "apple_watch"),
        ("2026-09-03", 4000, "iphone")]


def test_values_of_sources_are_never_added(db, pid):
    store.add_measurement(db, pid, "weight", 80.0, at(D1), "withings", "g1")
    store.add_measurement(db, pid, "weight", 80.0, at(D1, 7, 1), "apple_withings", "")
    series = store.daily_series(db, pid, "weight", D1, D1)
    assert series == [{"day": "2026-09-01", "value": 80.0, "source": "withings"}]


def test_changing_the_order(db, pid):
    store.set_daily_many(db, pid, [("steps", D1, "garmin", 9000), ("steps", D1, "apple_watch", 8500)])
    store.set_priority(db, "aktivitaet", ["apple_watch", "garmin"])
    assert store.daily_series(db, pid, "steps", D1, D1)[0]["source"] == "apple_watch"
    order = store.priority(db, "aktivitaet")
    assert order[:2] == ["apple_watch", "garmin"] and len(order) == 7  # missing ones appended
    store.reset_priority(db, "aktivitaet")
    assert store.daily_series(db, pid, "steps", D1, D1)[0]["source"] == "garmin"


def test_unknown_sources_in_order_are_ignored(db, pid):
    store.set_priority(db, "koerper", ["boese", "garmin", "garmin"])
    order = store.priority(db, "koerper")
    assert order[0] == "garmin" and "boese" not in order and len(order) == len(set(order))


def test_day_aggregation_per_metric(db, pid):
    store.add_measurements(db, pid, [
        ("weight", 81.0, at(D1, 7), "withings", ""), ("weight", 80.2, at(D1, 21), "withings", ""),
        ("bp_sys", 120, at(D1, 7), "withings", "a"), ("bp_sys", 130, at(D1, 21), "withings", "b"),
    ])
    assert store.daily_series(db, pid, "weight", D1, D1)[0]["value"] == 80.2  # last of the day
    assert store.daily_series(db, pid, "bp_sys", D1, D1)[0]["value"] == 125  # mean


def test_implausible_values_are_dropped(db, pid):
    assert not store.add_measurement(db, pid, "weight", 2000, at(D1), "withings")
    assert not store.add_measurement(db, pid, "weight", float("nan"), at(D1), "withings")
    assert not store.add_measurement(db, pid, "weight", True, at(D1), "withings")
    assert not store.add_measurement(db, pid, "weight", 80, at(D1), "fremd")
    assert not store.add_measurement(db, pid, "unbekannt", 80, at(D1), "withings")
    assert store.set_daily_many(db, pid, [("steps", D1, "garmin", -5), ("steps", D1, "garmin", "x")]) == 0


def test_reimport_replaces_instead_of_duplicating(db, pid):
    store.add_measurement(db, pid, "weight", 80.0, at(D1), "withings", "g1")
    store.add_measurement(db, pid, "weight", 79.5, at(D1), "withings", "g1")
    store.set_daily(db, pid, "steps", D1, "garmin", 1000)
    store.set_daily(db, pid, "steps", D1, "garmin", 1200)
    assert db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 1
    assert store.latest(db, pid, "weight")["value"] == 79.5
    assert store.daily_series(db, pid, "steps", D1, D1)[0]["value"] == 1200


def test_latest_and_until(db, pid):
    store.add_measurement(db, pid, "weight", 82.0, at(D1), "withings")
    store.add_measurement(db, pid, "weight", 80.0, at(D3), "withings")
    assert store.latest(db, pid, "weight", until=D3)["value"] == 80.0
    assert store.latest(db, pid, "weight", until=D2)["value"] == 82.0
    assert store.latest(db, pid, "resting_hr") is None


def test_readings_group_and_follow_order(db, pid):
    store.add_measurements(db, pid, [
        ("bp_sys", 125, at(D1), "withings", "w1"), ("bp_dia", 82, at(D1), "withings", "w1"),
        ("pulse", 61, at(D1), "withings", "w1"),
        ("bp_sys", 125, at(D1), "apple_withings", ""), ("bp_dia", 82, at(D1), "apple_withings", ""),
        ("bp_sys", 131, at(D2, 8), "apple_andere", ""), ("bp_dia", 85, at(D2, 8), "apple_andere", ""),
    ])
    readings = store.readings(db, pid, ("bp_sys", "bp_dia", "pulse"), D1, D2)
    assert [(r["day"], r["source"]) for r in readings] == [("2026-09-02", "apple_andere"),
                                                          ("2026-09-01", "withings")]
    assert readings[1]["values"] == {"bp_sys": 125, "bp_dia": 82, "pulse": 61}


def test_sleep_one_night_per_day(db, pid):
    store.upsert_sleep(db, pid, D2, "garmin", {"asleep_min": 420, "deep_min": 70, "light_min": 260,
                                          "rem_min": 90, "awake_min": 20,
                                          "bed_start": at(D1, 23), "bed_end": at(D2, 6, 40)})
    store.upsert_sleep(db, pid, D2, "apple_watch", {"asleep_min": 410, "bed_start": at(D1, 23)})
    store.upsert_sleep(db, pid, D3, "apple_watch", {"asleep_min": 390, "bed_start": at(D2, 23)})
    nights = store.sleep_series(db, pid, D1, D3)
    assert [(n["night"], n["source"]) for n in nights] == [("2026-09-02", "garmin"),
                                                          ("2026-09-03", "apple_watch")]
    assert not store.upsert_sleep(db, pid, D1, "garmin", {})  # nothing to store


def test_same_workout_from_two_sources_once(db, pid):
    base = {"kind": "laufen", "duration_min": 40, "distance_km": 7.5}
    store.upsert_workout(db, pid, "garmin", "1", dict(base, started_at=at(D1, 18)))
    store.upsert_workout(db, pid, "iphone", "a", dict(base, started_at=at(D1, 18, 3)))
    store.upsert_workout(db, pid, "iphone", "b", dict(base, started_at=at(D1, 20)))
    rows = store.workouts(db, pid, D1, D1)
    assert [(r["source"], r["started_at"][11:16]) for r in rows] == [("iphone", "20:00"),
                                                                    ("garmin", "18:00")]


def test_overview_delete_and_retention(db, pid):
    store.set_daily_many(db, pid, [("steps", D1, "garmin", 1000), ("steps", D3, "iphone", 2000)])
    store.add_measurement(db, pid, "weight", 80, at(D1), "withings")
    overview = store.sources_overview(db, pid)
    assert overview["garmin"] == {"count": 1, "first": "2026-09-01", "last": "2026-09-01"}
    assert store.delete_source(db, pid, "garmin") == 1
    assert store.apply_retention(db, 1, today=D3) == 1  # weight from D1 is older than one day
    assert store.apply_retention(db, 0, today=D3) == 0
    assert db.execute("SELECT COUNT(*) FROM daily_values").fetchone()[0] == 1
    store.set_priority(db, "koerper", ["garmin"])
    store.delete_all(db)
    assert all(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
               for t in ("measurements", "daily_values", "sleep", "workouts", "source_priority"))


def test_summary():
    assert store.summary([]) == {"avg": None, "min": None, "max": None, "count": 0}
    assert store.summary([1, 2, 3])["avg"] == 2
