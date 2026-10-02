"""Overview features from version 0.3: load and form, the 3D skyline, findings, the week coach,
goal forecasts and the prepared questions."""

import math
import re
from datetime import date, datetime, timedelta

import pytest

from gesundheit import belastung, charts, persons, store, uebersicht, util

TODAY = date(2026, 9, 30)  # a Wednesday


def day(n: int) -> date:
    return TODAY - timedelta(days=n)


def person(db, pid):
    return persons.get(db, pid)


# ---------- Load and form ----------

def test_impulse_follows_banister():
    assert belastung.impulse(60, 0.5) == pytest.approx(60 * 0.5 * 0.64 * math.exp(0.96))
    assert belastung.impulse(0, 0.8) == 0
    assert belastung.impulse(None, 0.8) == 0
    assert belastung.impulse(30, 2) == belastung.impulse(30, 1)  # reserve is capped


def test_heart_limits_from_age_rest_and_trainings(db, pid):
    persons.update(db, pid, birth_year=1986)
    for n in range(5):
        store.set_daily(db, pid, "resting_hr", day(n), "garmin", 50 + n)
    rest, maximum = belastung.heart_limits(db, pid, person(db, pid), TODAY)
    assert rest == 52 and maximum == 180
    store.upsert_workout(db, pid, "garmin", "hard", {
        "kind": "laufen", "duration_min": 30, "hr_avg": 170, "hr_max": 191,
        "started_at": datetime(2026, 9, 20, 18, 0)})
    assert belastung.heart_limits(db, pid, person(db, pid), TODAY)[1] == 191
    persons.update(db, pid, birth_year=None)
    db.commit()
    assert belastung.heart_limits(db, pid, person(db, pid), TODAY)[1] == 191


def test_daily_load_counts_trainings_and_light_minutes_once(db, pid):
    store.set_daily(db, pid, "resting_hr", day(0), "garmin", 60)
    persons.update(db, pid, birth_year=1986)  # maximum 180
    store.upsert_workout(db, pid, "garmin", "run", {
        "kind": "laufen", "duration_min": 40, "hr_avg": 150,
        "started_at": datetime(2026, 9, 30, 7, 0)})
    store.set_daily(db, pid, "active_min", day(0), "garmin", 70)
    store.set_daily(db, pid, "active_min", day(1), "garmin", 30)
    loads = belastung.daily(db, pid, person(db, pid), day(2), TODAY)
    run = belastung.impulse(40, (150 - 60) / (180 - 60))
    assert loads[TODAY.isoformat()] == pytest.approx(run + belastung.impulse(30, 0.3), abs=0.1)
    assert loads[day(1).isoformat()] == pytest.approx(belastung.impulse(30, 0.3), abs=0.1)
    assert day(2).isoformat() not in loads  # no data is not a zero


def test_form_needs_enough_days_then_reads_like_a_coach(db, pid):
    for n in range(10):
        store.set_daily(db, pid, "active_min", day(n), "garmin", 40)
    db.commit()
    assert belastung.form(db, pid, person(db, pid), TODAY) is None
    for n in range(10, 120):
        store.set_daily(db, pid, "active_min", day(n), "garmin", 40)
    # a hard last week
    for n in range(7):
        store.upsert_workout(db, pid, "garmin", f"w{n}", {
            "kind": "laufen", "duration_min": 90,
            "started_at": datetime.combine(day(n), datetime.min.time()).replace(hour=7)})
    db.commit()
    result = belastung.form(db, pid, person(db, pid), TODAY)
    assert result["fatigue"] > result["fitness"]
    assert result["form"] < 0 and result["label"] in ("im Aufbau", "überlastet")
    assert 0 <= result["position"] < 50
    assert len(result["course"]) == 56
    assert belastung.state(20)[0] == "sehr frisch"
    assert belastung.state(0)[0] == "ausgeglichen"
    assert belastung.state(-50)[0] == "überlastet"


# ---------- Skyline ----------

def test_skyline_chart_draws_one_column_per_day_and_marks_the_peak():
    cells = [{"day": day(n), "value": None if n == 3 else 1000 + n * 10,
              "tip": [f"Tag {n}", ("1.000", "Schritte")]} for n in range(20, -1, -1)]
    svg = str(charts.skyline(cells, "", 0, "Test"))
    assert svg.count('class="sk-bar') == 21
    assert svg.count("sk-peak") == 1 and "1.200" in svg  # day(20) has the highest value
    assert svg.count('class="sk-leer"') == 1
    assert 'preserveAspectRatio="none"' not in svg  # never stretched
    assert 'data-tip="Tag 0|1.000|Schritte"' in svg
    assert "style=" not in svg
    assert re.search(r'<text class="sk-monat"[^>]*>Sep</text>', svg)


def test_skyline_chart_paints_back_to_front():
    cells = [{"day": day(n), "value": 5000, "tip": ["t"]} for n in range(13, -1, -1)]
    svg = str(charts.skyline(cells, "", 0, "Test"))
    weeks = [int(w) for w in re.findall(r'data-w="(\d+)"', svg)]
    # later weeks stand further back on the rising ribbon, so they come first
    assert weeks[0] == max(weeks) and weeks[-1] == 0


def test_skyline_chart_without_values_is_empty():
    assert "chart-empty" in str(charts.skyline([{"day": TODAY, "value": None}], "", 0, "x"))


def test_skyline_views_and_totals(db, pid):
    for n in range(30):
        store.set_daily(db, pid, "steps", day(n), "garmin", 10000)
        store.set_daily(db, pid, "distance_km", day(n), "garmin", 7.5)
        store.set_daily(db, pid, "active_min", day(n), "garmin", 30)
    store.upsert_workout(db, pid, "garmin", "w", {"kind": "laufen", "duration_min": 45,
                                                  "started_at": datetime(2026, 9, 28, 7, 0)})
    db.commit()
    sky = uebersicht.skyline(db, pid, person(db, pid), TODAY, "3M")
    assert sky["period"] == "3M" and sky["label"] == "Deine letzten 3 Monate"
    steps, load = sky["views"]
    assert steps["number"] == 300000 and steps["decimals"] == 0
    assert "225 km" in steps["sub"] and "1 Trainings" in steps["sub"]
    assert load["unit"] == "Belastungspunkte" and load["number"] > 0
    assert uebersicht.skyline(db, pid, person(db, pid), TODAY, "quatsch")["period"] == "12M"
    assert uebersicht._big(3_881_000) == (3.88, 2, " Mio.")


def test_overview_shows_skyline_and_switches(logged_in, db, me):
    for n in range(20):
        store.set_daily(db, me, "steps", util.today() - timedelta(days=n), "garmin", 8000 + n)
    db.commit()
    page = logged_in.get("/?zeit=6M&ansicht=belastung").get_data(as_text=True)
    assert "Deine letzten 6 Monate" in page
    assert 'data-sky-ansicht="schritte"' in page
    # only steps so far: the load view needs activity minutes or trainings
    assert 'data-sky-ansicht="belastung"' not in page
    assert 'aria-current="true">6M</a>' in page


# ---------- Findings ----------

from gesundheit import befunde  # noqa: E402


def wobble(n: int, size: float = 1.0) -> float:
    """Small deterministic day-to-day variation."""
    return size * ((n * 7) % 5 - 2) / 2


def daily(db, pid, metric, days, value_of, source="garmin"):
    store.set_daily_many(db, pid, [(metric, day(n), source, value_of(n)) for n in days])
    db.commit()


def find(db, pid, rule):
    return rule(db, pid, person(db, pid), TODAY)


def test_resting_pulse_above_normal_is_a_warning(db, pid):
    daily(db, pid, "resting_hr", range(7, 35), lambda n: 55 + wobble(n))
    daily(db, pid, "resting_hr", range(0, 7), lambda n: 61 + wobble(n, 0.5))
    f = find(db, pid, befunde.resting_pulse)
    assert f.tone == befunde.WARN and f.title_b == "6 Schläge über normal."
    assert f.stats[2][0] == "7 von 7" and "aus 35 Tagen" == f.basis
    svg = str(f.chart())
    assert "zone-oben" in svg and svg.count("dot-treffer") >= 7  # every recent day is above
    assert any("28 Tage davor" in s for s in f.steps)


def test_resting_pulse_without_change_or_history_finds_nothing(db, pid):
    daily(db, pid, "resting_hr", range(0, 35), lambda n: 55 + wobble(n))
    assert find(db, pid, befunde.resting_pulse) is None
    db.execute("DELETE FROM daily_values")
    daily(db, pid, "resting_hr", range(0, 10), lambda n: 70)
    assert find(db, pid, befunde.resting_pulse) is None


def test_hrv_drop_and_rise(db, pid):
    daily(db, pid, "hrv_rmssd", range(7, 35), lambda n: 50 + wobble(n, 2))
    daily(db, pid, "hrv_rmssd", range(0, 7), lambda n: 40 + wobble(n))
    f = find(db, pid, befunde.hrv)
    assert f.tone == befunde.WARN and f.big == "−20 %"
    daily(db, pid, "hrv_rmssd", range(0, 7), lambda n: 60 + wobble(n))
    assert find(db, pid, befunde.hrv).tone == befunde.GOOD


def _training(db, pid, n, minutes, hr, key=None):
    store.upsert_workout(db, pid, "garmin", key or f"t{n}", {
        "kind": "laufen", "duration_min": minutes, "hr_avg": hr, "hr_max": hr + 15 if hr else None,
        "started_at": datetime.combine(day(n), datetime.min.time()).replace(hour=18)})


def test_hard_easy_runs_are_found_with_the_zone_limit(db, pid):
    persons.update(db, pid, birth_year=1986)  # maximum 180
    daily(db, pid, "resting_hr", range(0, 30), lambda n: 60)
    for i in range(10):
        _training(db, pid, 3 + i * 7, 45, 160 if i < 8 else 120)
    db.commit()
    f = find(db, pid, befunde.easy_trainings)
    assert f.tone == befunde.WARN and f.title_b == "nicht ruhig."
    assert f.stats[0][0] == "8 von 10" and f.stats[2][0] == "144 bpm"  # 60 + 0.7 * 120
    assert "Zone 3 · ab 144 Puls" in str(f.chart())


def test_easy_runs_that_are_easy_find_nothing(db, pid):
    persons.update(db, pid, birth_year=1986)
    for i in range(10):
        _training(db, pid, 3 + i * 7, 45, 125)
    db.commit()
    assert find(db, pid, befunde.easy_trainings) is None


def test_load_jump_compares_with_three_weeks(db, pid):
    daily(db, pid, "active_min", range(0, 56), lambda n: 40)
    for n in range(0, 7):
        _training(db, pid, n, 90, None)
    db.commit()
    f = find(db, pid, befunde.load_jump)
    assert f.tone == befunde.WARN and f.title_b.startswith("um ")
    assert "letzte 7 T" in str(f.chart())


def test_sleep_debt_and_a_good_week(db, pid):
    persons.update(db, pid, goal_sleep_min=480)
    for n in range(7):
        store.upsert_sleep(db, pid, day(n), "garmin", {"asleep_min": 400})
    db.commit()
    f = find(db, pid, befunde.sleep_debt)
    assert f.tone == befunde.WARN and f.title_b == "9 h 20 min Schlaf."
    for n in range(7):
        store.upsert_sleep(db, pid, day(n), "garmin", {"asleep_min": 490})
    db.commit()
    assert find(db, pid, befunde.sleep_debt).tone == befunde.GOOD


def test_irregular_bedtime(db, pid):
    for n in range(14):
        hour = 21 if n % 2 else 24
        bed = datetime.combine(day(n) - timedelta(days=1), datetime.min.time()) + timedelta(hours=hour)
        store.upsert_sleep(db, pid, day(n), "garmin", {"asleep_min": 420, "bed_start": bed})
    db.commit()
    f = find(db, pid, befunde.bedtime)
    assert f.tone == befunde.WARN and f.stats[0][0] == "21:00" and f.stats[1][0] == "00:00"
    assert "21:00" in str(f.chart())  # clock labels on the axis


def test_weight_trend_toward_and_away_from_goal(db, pid):
    for n in range(0, 28, 2):
        store.add_measurement(db, pid, "weight", 80 - (27 - n) * 0.1,
                              datetime.combine(day(n), datetime.min.time()).replace(hour=7),
                              "withings")
    db.commit()
    f = find(db, pid, befunde.weight_trend)  # losing 0.7 kg a week
    assert f.tone == befunde.INFO and f.title_b == "0,7 kg pro Woche." and f.big == "−0,7 kg"
    persons.update(db, pid, goal_weight_dg=750)
    db.commit()
    assert find(db, pid, befunde.weight_trend).tone == befunde.GOOD
    persons.update(db, pid, goal_weight_dg=850)
    db.commit()
    assert find(db, pid, befunde.weight_trend).tone == befunde.WARN


def test_raised_blood_pressure(db, pid):
    for n in range(10):
        at = datetime.combine(day(n), datetime.min.time()).replace(hour=7)
        sys_v = 142 if n < 7 else 125
        store.add_measurements(db, pid, [("bp_sys", sys_v, at, "withings", f"b{n}"),
                                         ("bp_dia", 88, at, "withings", f"b{n}")])
    db.commit()
    f = find(db, pid, befunde.blood_pressure)
    assert f.tone == befunde.WARN and "10 von 10" in f.title_b  # 88 diastolic counts too
    assert "keine Diagnose" in f.text


def test_step_streak_and_weekday_gap(db, pid):
    persons.update(db, pid, goal_steps=8000)
    daily(db, pid, "steps", range(0, 84),
          lambda n: 3000 if day(n).weekday() == 6 else (9000 if n < 6 else 7000))
    f = find(db, pid, befunde.step_streak)
    assert f is None or f.tone == befunde.GOOD
    gap = find(db, pid, befunde.weekday_gap)
    assert gap.title_a == "Am Sonntag gehst du" and gap.tone == befunde.INFO


def test_compute_sorts_caches_and_survives_a_broken_rule(db, pid, monkeypatch):
    daily(db, pid, "resting_hr", range(7, 35), lambda n: 55 + wobble(n))
    daily(db, pid, "resting_hr", range(0, 7), lambda n: 61)
    befunde.clear_cache()

    def broken(*_args):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(befunde, "RULES", [broken, befunde.resting_pulse])
    found = befunde.compute(db, pid, person(db, pid), TODAY)
    assert [f.rule for f in found] == ["ruhepuls"]
    assert found[0].key == "ruhepuls-2026-40"
    assert befunde.compute(db, pid, person(db, pid), TODAY) is found  # cached
    store.set_daily(db, pid, "steps", TODAY, "garmin", 5)
    db.commit()
    assert befunde.compute(db, pid, person(db, pid), TODAY) is not found  # data changed


def test_seen_findings_and_news(db, pid):
    daily(db, pid, "resting_hr", range(7, 35), lambda n: 55 + wobble(n))
    daily(db, pid, "resting_hr", range(0, 7), lambda n: 61)
    befunde.clear_cache()
    found = befunde.compute(db, pid, person(db, pid), TODAY)
    assert befunde.news(found, person(db, pid)) is found[0]
    befunde.mark_seen(db, pid, person(db, pid), [found[0].key, "<script>"])
    db.commit()
    assert befunde.seen(person(db, pid)) == [found[0].key]
    assert befunde.news(found, person(db, pid)) is None
    assert befunde.seen({"seen_findings": "kein json"}) == []


def test_findings_page_badge_and_toast(logged_in, db, me):
    today = util.today()
    store.set_daily_many(db, me, [("resting_hr", today - timedelta(days=n), "garmin",
                                   55 + wobble(n)) for n in range(7, 35)])
    store.set_daily_many(db, me, [("resting_hr", today - timedelta(days=n), "garmin", 62)
                                  for n in range(7)])
    db.commit()
    befunde.clear_cache()
    page = logged_in.get("/befunde").get_data(as_text=True)
    assert "Schläge über normal." in page and "Rechenweg" in page
    assert 'class="nav-badge"' in page and "Hinweise" in page
    overview = logged_in.get("/").get_data(as_text=True)
    assert "Wichtigster Befund" in overview and "Neuer Befund" in overview
    key = re.search(r'name="key" value="([^"]+)"', overview).group(1)
    # without the token nothing is stored
    assert logged_in.client.post("/befunde/gesehen", data={"key": key}).status_code == 400
    response = logged_in.post("/befunde/gesehen", {"key": key, "next": "/befunde#" + key})
    assert response.status_code == 302 and response.headers["Location"].endswith("/befunde#" + key)
    assert "Neuer Befund" not in logged_in.get("/").get_data(as_text=True)
    # unknown keys are ignored
    logged_in.post("/befunde/gesehen", {"key": "erfunden-2026-01"})
    seen = db.execute("SELECT seen_findings FROM persons WHERE id = ?", (me,)).fetchone()[0]
    assert "erfunden" not in seen


def test_form_card_on_overview(logged_in, db, me):
    today = util.today()
    store.set_daily_many(db, me, [("active_min", today - timedelta(days=n), "garmin", 45)
                                  for n in range(60)])
    db.commit()
    page = logged_in.get("/").get_data(as_text=True)
    assert "Form heute" in page and "Fitness" in page and "Ermüdung" in page
    assert 'class="fk-punkt" d="M' in page
