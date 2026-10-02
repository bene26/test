"""Analyses, relationships, comparisons, reports and the new chart kinds."""

import re
from datetime import date, datetime, timedelta

import pytest

from gesundheit import auswertung, charts, persons, store, util

TODAY = date(2026, 9, 30)  # a Wednesday


def day(n: int) -> date:
    return TODAY - timedelta(days=n)


def fill_steps(db, pid, values: dict[int, float], source="garmin"):
    store.set_daily_many(db, pid, [("steps", day(n), source, v) for n, v in values.items()])


# ---------- Statistics ----------

def test_pearson_and_fit():
    xs = [1, 2, 3, 4, 5]
    assert auswertung.pearson(xs, [2, 4, 6, 8, 10]) == pytest.approx(1)
    assert auswertung.pearson(xs, [10, 8, 6, 4, 2]) == pytest.approx(-1)
    assert auswertung.pearson(xs, [1, 1, 1, 1, 1]) is None
    assert auswertung.pearson([1, 2], [1, 2]) is None
    assert auswertung.linear_fit(xs, [3, 5, 7, 9, 11]) == pytest.approx((2, 1))
    assert auswertung.strength(0.05)[0] == "keiner"
    assert auswertung.strength(-0.35)[0] == "mittel"
    assert auswertung.strength(0.7)[0] == "stark"


def test_derived_series(db, pid):
    store.upsert_sleep(db, pid, day(1), "garmin", {
        "asleep_min": 450, "score": 81, "deep_min": 70,
        "bed_start": datetime(2026, 9, 29, 0, 30), "bed_end": datetime(2026, 9, 29, 8, 0)})
    store.upsert_sleep(db, pid, day(0), "garmin", {
        "asleep_min": 420, "bed_start": datetime(2026, 9, 29, 22, 15)})
    store.upsert_workout(db, pid, "garmin", "w1", {"kind": "laufen", "duration_min": 40,
                                                   "started_at": datetime(2026, 9, 29, 18, 0)})
    store.set_daily(db, pid, "steps", day(2), "garmin", 5000)
    hours = auswertung.series(db, pid, "schlaf_dauer", day(3), TODAY)
    assert [p["value"] for p in hours] == [7.5, 7.0]
    bed = auswertung.series(db, pid, "zubettgehen", day(3), TODAY)
    assert [p["value"] for p in bed] == [24.5, 22.25]  # after midnight counts on
    assert auswertung.fmt("zubettgehen", 24.5) == "00:30"
    training = {p["day"]: p["value"] for p in auswertung.series(db, pid, "training_min", day(3), TODAY)}
    assert training[day(1).isoformat()] == 40 and training[day(2).isoformat()] == 0
    assert day(3).isoformat() not in training  # before the first data


def test_compare_periods(db, pid):
    fill_steps(db, pid, {n: 10000 for n in range(7)})            # this week
    fill_steps(db, pid, {n: 8000 for n in range(7, 14)})         # week before
    fill_steps(db, pid, {n: 5000 for n in range(364, 371)})      # a year ago
    result = auswertung.compare_periods(db, pid, "steps", 7, TODAY)
    assert result["current"]["avg"] == 10000 and result["current"]["total"] == 70000
    assert result["change_prev"] == pytest.approx(25) and result["trend_prev"] == "gut"
    assert result["change_year"] == pytest.approx(100)
    shifted = result["overlay"][1]["points"]
    assert shifted[0]["day"] == day(6).isoformat()  # previous week laid over this one


def test_records_and_streaks(db, pid):
    person = persons.get(db, pid)
    fill_steps(db, pid, {9: 12000, 8: 11000, 7: 10500, 6: 4000, 5: 10000, 4: 9000,
                         3: 15000, 2: 10200, 1: 10100, 0: 13000})
    rec = auswertung.records(db, pid, "steps", person, TODAY)
    assert rec["best"]["value"] == 15000 and rec["worst"]["value"] == 4000
    assert rec["longest"] == 4 and rec["current"] == 4 and rec["reached_days"] == 8


def test_weekday_profile():
    points = [{"day": "2026-09-28", "value": 10}, {"day": "2026-10-05", "value": 20},
              {"day": "2026-10-04", "value": 7}]
    profile = auswertung.weekday_profile(points)
    assert profile[0] == 15 and profile[6] == 7 and profile[2] is None


def test_relationship_with_lag(db, pid):
    for n in range(30):
        store.set_daily(db, pid, "steps", day(n + 1), "garmin", 5000 + n * 200)
        store.upsert_sleep(db, pid, day(n), "garmin", {"asleep_min": 360 + n * 5,
                                                       "bed_start": datetime(2026, 1, 1)})
    rel = auswertung.relationship(db, pid, "steps", "schlaf_dauer", day(40), TODAY, lag=1)
    assert rel["n"] == 30 and rel["r"] == pytest.approx(1) and rel["level"] == "stark"
    assert "mehr Schlafdauer" in rel["effect"]


def test_insights_find_clear_patterns(db, pid):
    import random
    rng = random.Random(1)
    for n in range(60):
        sleep_h = 6 + rng.random() * 3
        store.upsert_sleep(db, pid, day(n), "garmin", {"asleep_min": sleep_h * 60,
                                                       "bed_start": datetime(2026, 1, 1)})
        store.set_daily(db, pid, "resting_hr", day(n), "garmin", 70 - 3 * sleep_h + rng.gauss(0, 0.5))
    found = auswertung.insights(db, pid, TODAY, 90)
    assert found and found[0]["title"] == "Schlaf und Ruhepuls"
    assert found[0]["r"] < -0.8 and "niedriger" in found[0]["sentence"]


# ---------- Persons ----------

def test_compare_ranking_and_radar(db):
    anna = persons.create(db, "Anna", "pink", goal_steps=10000)
    ben = persons.create(db, "Ben", "blau", goal_steps=5000)
    fill_steps(db, anna, {n: 9000 for n in range(7)})
    fill_steps(db, ben, {n: 6000 for n in range(7)})
    people = persons.all_persons(db)
    rows = auswertung.compare_persons(db, people, "steps", day(6), TODAY)
    by_name = {r["person"]["name"]: r for r in rows}
    assert by_name["Anna"]["goal_share"] == pytest.approx(90)
    assert by_name["Ben"]["goal_share"] == pytest.approx(120) and by_name["Ben"]["goal_days"] == 7
    ranked = auswertung.ranking([dict(r) for r in rows], auswertung.KEYS["steps"])
    assert [r["person"]["name"] for r in ranked] == ["Anna", "Ben"] and ranked[0]["bar"] == 100
    radar = auswertung.radar_values(db, people[1], day(6), TODAY)
    assert radar[0] == pytest.approx(1.2) and radar[1] is None


def test_ranking_lower_is_better():
    rows = [{"summary": {"avg": 55, "total": None}, "person": {"name": "A"}},
            {"summary": {"avg": 62, "total": None}, "person": {"name": "B"}}]
    ranked = auswertung.ranking(rows, auswertung.KEYS["resting_hr"])
    assert ranked[0]["person"]["name"] == "A"


# ---------- Reports ----------

def test_report_periods():
    assert auswertung.report_period("woche", date(2026, 10, 1))[:2] == (date(2026, 9, 28), date(2026, 10, 4))
    assert auswertung.report_period("monat", date(2028, 2, 10)) == (
        date(2028, 2, 1), date(2028, 2, 29), date(2028, 1, 1), date(2028, 1, 31))


def test_report_blood_pressure_protocol(db, pid):
    for hour, sys_v in ((7, 120), (13, 125), (21, 130)):
        at = datetime(2026, 9, 29, hour, 0)
        store.add_measurements(db, pid, [("bp_sys", sys_v, at, "withings", f"g{hour}"),
                                         ("bp_dia", 80, at, "withings", f"g{hour}")])
    rep = auswertung.report(db, persons.get(db, pid), "woche", date(2026, 9, 30))
    (the_day, slots), = rep["protocol"]
    assert the_day == "2026-09-29"
    assert [len(slots[s]) for s in ("morgens", "mittags", "abends")] == [1, 1, 1]
    assert rep["bp"]["morning"]["sys"] == 120 and rep["bp"]["evening"]["sys"] == 130
    assert rep["bp"]["all"]["count"] == 3


# ---------- Pages ----------

@pytest.fixture
def two(logged_in, db, me):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import demo_daten
    demo_daten.fill(db, me, util.today(), 90)
    other = persons.create(db, "Ben", "blau")
    demo_daten.fill(db, other, util.today(), 90, seed=3, profile=demo_daten.PROFILES["Ben"])
    return logged_in


@pytest.mark.parametrize("url", [
    "/auswertungen", "/auswertungen?wert=gibts-nicht&zeitraum=9", "/auswertungen?wert=schlaf_dauer",
    "/auswertungen?wert=resting_hr&zeitraum=365", "/auswertungen/zusammenhaenge",
    "/auswertungen/zusammenhaenge?x=x&y=y&versatz=7", "/vergleich", "/vergleich?wert=weight&p=1",
    "/vergleich?wert=schlaf_dauer&zeitraum=7&p=999", "/berichte", "/berichte?art=monat",
    "/berichte?art=x&datum=kaputt", "/berichte?datum=1900-01-01"])
def test_analysis_pages(two, url):
    response = two.get(url)
    assert response.status_code == 200
    assert 'style="' not in response.get_data(as_text=True)


def test_comparison_shows_everyone(two):
    page = two.get("/vergleich").get_data(as_text=True)
    assert "Ben" in page and "anna" in page and 'class="radar"' in page and "Wochen-Challenge" in page
    assert page.count('class="serie p-') >= 2


def test_report_page(two):
    page = two.get("/berichte?art=monat").get_data(as_text=True)
    assert "Blutdruck-Protokoll" in page and "data-drucken" in page and "keine Diagnose" in page


def test_analysis_page_content(two):
    page = two.get("/auswertungen?wert=steps").get_data(as_text=True)
    for text in ("Bestwerte und Serien", "Nach Wochentag", "Das Jahr auf einen Blick",
                 'class="heatmap"', "Zeitraum davor"):
        assert text in page


# ---------- Charts ----------

def test_smooth_path_does_not_overshoot():
    coords = [(0, 100), (10, 50), (20, 50), (30, 0)]
    path = charts.smooth_path(coords)
    ys = [float(v) for v in re.findall(r"[ C]-?[\d.]+ (-?[\d.]+)", path)]
    assert min(ys) >= 0 and max(ys) <= 100


def test_rings_gauge_donut():
    svg = str(charts.rings([{"key": "kalorien", "value": 650, "goal": 500},
                            {"key": "schritte", "value": None, "goal": 10000}]))
    assert 'data-ring="100.0"' in svg and "ring-lap" in svg and 'data-ring="0.0"' in svg
    assert "gauge-gut" in str(charts.gauge(85, 100, "Schlaf"))
    assert "gauge-niedrig" in str(charts.gauge(20, 100, "Schlaf"))
    assert str(charts.gauge(None, 100, "x")) == ""
    donut = str(charts.donut([("tief", "Tief", 60), ("rem", "REM", 0), ("wach", "Wach", 20)], "7:00"))
    assert donut.startswith("<svg") and donut.count("donut-teil") == 2 and "&lt;" not in donut


def test_radar_heatmap_columns():
    radar = str(charts.radar(["A", "B", "C"], [{"label": "X", "cls": "p-blau", "values": [1, 2, None]}]))
    assert radar.count("radar-ring") == 3 and "p-blau" in radar
    values = {(TODAY - timedelta(days=n)).isoformat(): float(n) for n in range(100)}
    heat = str(charts.heatmap(values, TODAY, "", 0, "Test"))
    assert heat.count('class="hm hm-') >= 100 and "hm-4" in heat and "hm-1" in heat
    cols = str(charts.columns(util.WEEKDAYS, [1, 2, 3, None, 5, 4, 2], "", 0, "W"))
    assert cols.count("bar reached") == 1


def test_scatter_needs_points():
    assert "Zu wenige" in str(charts.scatter([(1, 2, "a")], ("x", "", 0), ("y", "", 0)))
    svg = str(charts.scatter([(1, 2, "a"), (2, 3, "b"), (3, 5, "c")], ("x", "h", 1), ("y", "", 0),
                             fit=(1.5, 0.3)))
    assert 'class="fit"' in svg and svg.count('class="dot"') == 3
