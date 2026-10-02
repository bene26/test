"""Pages with a year of example data, settings, export, deleting, charts and assessments."""

import sys
from pathlib import Path

import pytest

from gesundheit import bewertung, charts, settings, store, util

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import demo_daten  # noqa: E402


@pytest.fixture
def filled(logged_in, db):
    demo_daten.fill(db, util.today(), 120)
    return logged_in


@pytest.mark.parametrize("url", [
    "/", "/koerper", "/herz", "/schlaf", "/aktivitaet", "/quellen", "/daten", "/einstellungen",
    "/koerper?zeitraum=7", "/herz?zeitraum=90", "/schlaf?zeitraum=365", "/aktivitaet?zeitraum=7",
    "/verlauf/weight", "/verlauf/steps?zeitraum=90", "/verlauf/hrv_rmssd", "/verlauf/spo2",
    "/verlauf/body_battery_max", "/koerper?zeitraum=abc", "/koerper?zeitraum=5"])
def test_pages_with_data(filled, url):
    response = filled.get(url)
    assert response.status_code == 200
    assert 'style="' not in response.get_data(as_text=True)


def test_overview_shows_today(filled):
    page = filled.get("/").get_data(as_text=True)
    for text in ("Heute", "Schritte", "Ruhepuls", "Blutdruck", "Letzte Nacht", "data-ring",
                 "Die letzten 7 Tage"):
        assert text in page
    assert "Noch keine Daten" not in page


def test_unknown_metric_is_404(filled):
    assert filled.get("/verlauf/passwort").status_code == 404
    assert filled.get("/verlauf/ekg_afib").status_code == 404


def test_history_shows_other_sources(filled):
    page = filled.get("/verlauf/steps").get_data(as_text=True)
    assert "Andere Quellen" in page and "iPhone" in page


def test_search_for_card_file(filled):
    hits = filled.get("/suche.json?q=schlaf").get_json()["treffer"]
    assert any(h["url"] == "/schlaf" for h in hits)
    assert filled.get("/suche.json?q=a").get_json() == {"treffer": []}
    hits = filled.get("/suche.json?q=korper").get_json()["treffer"]
    assert any(h["titel"] == "Körper" for h in hits)


def test_csv_export(filled, db):
    store.add_measurement(db, "weight", 80, util.to_datetime("2026-01-01 07:00:00"), "withings")
    db.commit()
    response = filled.get("/daten/export/werte.csv")
    text = response.get_data(as_text=True)
    assert text.startswith("﻿Datum;Uhrzeit;Wert") and "Gewicht" in text and ";80;" in text
    assert "attachment" in response.headers["Content-Disposition"]
    for name in ("schlaf", "trainings"):
        assert filled.get(f"/daten/export/{name}.csv").status_code == 200
    assert filled.get("/daten/export/geheim.csv").status_code == 404


def test_goals(filled, db):
    filled.get("/einstellungen")
    filled.post("/einstellungen/ziele", {"height_cm": "181", "goal_steps": "8000",
                                         "goal_active_min": "40", "goal_active_kcal": "450",
                                         "goal_sleep_h": "7,5", "goal_weight": "76,5"})
    values = settings.get_all(db)
    assert values["goal_steps"] == 8000 and values["goal_sleep_min"] == 450
    assert values["goal_weight_dg"] == 765 and values["height_cm"] == 181
    filled.post("/einstellungen/ziele", {"goal_steps": "5", "goal_active_min": "40",
                                         "goal_active_kcal": "450", "goal_sleep_h": "7"})
    assert settings.get(db, "goal_steps") == 8000
    filled.post("/einstellungen/ziele", {"goal_steps": "8000", "goal_active_min": "40",
                                         "goal_active_kcal": "450", "goal_sleep_h": "7",
                                         "admin": "1"})
    assert settings.get(db, "goal_sleep_min") == 450  # unknown field: nothing saved


def test_source_order_buttons(filled, db):
    filled.get("/quellen")
    filled.post("/quellen/reihenfolge", {"familie": "aktivitaet", "quelle": "apple_watch",
                                         "richtung": "hoch"})
    assert store.priority(db, "aktivitaet")[:3] == ["garmin", "apple_watch", "apple_garmin"]
    filled.post("/quellen/reihenfolge", {"familie": "aktivitaet", "quelle": "apple_watch",
                                         "richtung": "hoch"})
    assert store.priority(db, "aktivitaet")[0] == "apple_watch"
    filled.post("/quellen/reihenfolge", {"familie": "aktivitaet", "richtung": "standard"})
    assert store.priority(db, "aktivitaet")[0] == "garmin"
    filled.post("/quellen/reihenfolge", {"familie": "boese", "richtung": "hoch"})
    filled.post("/quellen/reihenfolge", {"familie": "koerper", "quelle": "x", "richtung": "hoch"})
    assert db.execute("SELECT COUNT(*) FROM source_priority").fetchone()[0] == 0


def test_retention(filled, db):
    filled.get("/daten")
    filled.post("/daten/aufbewahrung", {"tage": "365"})
    assert settings.get(db, "retention_days") == 365
    filled.post("/daten/aufbewahrung", {"tage": "3"})
    assert settings.get(db, "retention_days") == 365


def test_delete_source_and_everything(filled, db):
    filled.get("/daten")
    filled.post("/daten/loeschen/quelle", {"quelle": "iphone"})
    assert store.sources_overview(db)["iphone"]["count"] == 0
    assert store.sources_overview(db)["garmin"]["count"] > 0
    filled.post("/daten/loeschen/alles", {"bestaetigung": "ja"})
    assert store.sources_overview(db)["garmin"]["count"] > 0
    filled.post("/daten/loeschen/alles", {"bestaetigung": "löschen"})
    assert all(v["count"] == 0 for v in store.sources_overview(db).values())
    assert filled.get("/").status_code == 200  # still logged in, account kept


# ---------- Charts and assessments ----------

def test_nice_ticks():
    assert charts.nice_ticks(0, 10000) == [0, 2500, 5000, 7500, 10000]
    ticks = charts.nice_ticks(78.4, 79.8)
    assert ticks[0] <= 78.4 and ticks[-1] >= 79.8 and len(ticks) <= 6
    assert charts._tick_decimals([48.2, 48.25, 48.3]) == 2


def test_line_chart_markup():
    points = [{"day": f"2026-09-{d:02d}", "value": 70 + d / 10, "source": "withings"}
              for d in range(1, 21)]
    svg = str(charts.line(points, util.to_date("2026-09-01"), util.to_date("2026-09-20"), "kg", 1,
                          "Gewicht", band=(60, 75, "Normal"), goal=71))
    assert svg.count('class="dot"') == 20 and 'class="trend"' in svg and 'class="band"' in svg
    assert "Mi 02.09.: 70,2 kg (Withings)" in svg and "<script" not in svg
    assert str(charts.line([], None, None, "", 0, "x")).startswith('<div class="chart-empty"')


def test_chart_escapes_text():
    points = [{"day": "2026-09-01", "value": 1, "source": "<b>x</b>"}]
    svg = str(charts.bars(points, util.to_date("2026-09-01"), util.to_date("2026-09-02"), "", 0,
                          '"><script>'))
    assert "<script>" not in svg and "<b>" not in svg


def test_score_axis_stops_at_100():
    points = [{"day": f"2026-09-{d:02d}", "value": 95 + d % 5, "source": "garmin"}
              for d in range(1, 11)]
    svg = str(charts.line(points, util.to_date("2026-09-01"), util.to_date("2026-09-10"), "", 0,
                          "Score", limits=(0, 100)))
    assert "<span>120</span>" not in svg and "<span>100</span>" in svg


@pytest.mark.parametrize("sys_v,dia_v,key", [
    (115, 75, "optimal"), (125, 79, "normal"), (119, 82, "normal"), (135, 70, "hochnormal"),
    (145, 85, "grad1"), (120, 95, "grad1"), (165, 90, "grad2"), (185, 80, "grad3"),
    (130, 112, "grad3")])
def test_blood_pressure_levels(sys_v, dia_v, key):
    assert bewertung.bp_category(sys_v, dia_v)[0] == key


def test_home_threshold():
    assert bewertung.home_bp_raised(135, 80) and bewertung.home_bp_raised(120, 85)
    assert not bewertung.home_bp_raised(134, 84)


def test_bmi():
    assert bewertung.bmi(80, 180) == pytest.approx(24.69, 0.01)
    assert bewertung.bmi(None, 180) is None
    assert bewertung.bmi_category(17)[0] == "untergewicht"
    assert bewertung.bmi_category(24.9)[0] == "normal"
    assert bewertung.bmi_category(27)[0] == "uebergewicht"
    assert bewertung.bmi_category(31)[0] == "adipositas"


def test_trend_direction():
    assert bewertung.trend_class(-2, "down") == "gut"
    assert bewertung.trend_class(2, "down") == "schlecht"
    assert bewertung.trend_class(2, "") == "neutral"
    assert bewertung.trend_class(None, "up") == "neutral"


def test_number_formats():
    assert util.fmt_num(12345.678, 1) == "12.345,7"
    assert util.fmt_minutes(452) == "7 h 32 min" and util.fmt_minutes(45) == "45 min"
    assert util.fmt_signed(-0.44) == "−0,4" and util.fmt_signed(0.01) == "±0"
    assert util.csv_cell("=SUMME(A1)") == "'=SUMME(A1)"
