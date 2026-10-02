"""Tape measure and the body analysis at the practice: entry, CSV import, display, findings."""

import io
from datetime import date, datetime, timedelta

import pytest

from gesundheit import apple, ausblick, auswertung, befunde, messungen, persons, store, uebersicht, util

TODAY = date(2026, 9, 30)


def day(n: int) -> date:
    return TODAY - timedelta(days=n)


def at(n: int, hour: int = 8) -> datetime:
    return datetime.combine(day(n), datetime.min.time()).replace(hour=hour)


def person(db, pid):
    return persons.get(db, pid)


# ---------- Catalogue and Apple ----------

def test_apple_brings_the_waist_and_knows_renpho():
    assert apple.QUANTITY["HKQuantityTypeIdentifierWaistCircumference"][0] == "circ_waist"
    assert apple.convert("circ_waist", 0.85, "m") == pytest.approx(85)
    assert apple.convert("circ_waist", 33, "in") == pytest.approx(83.82)
    assert apple.source_key("RENPHO Health", "") == "apple_renpho"
    assert apple.source_key("Renpho", "<<HKDevice: manufacturer:Renpho>>") == "apple_renpho"


def test_practice_values_only_fill_days_without_a_home_value(db, pid):
    store.add_measurement(db, pid, "fat_ratio", 21.0, at(0, 7), "withings")
    store.add_measurement(db, pid, "fat_ratio", 18.5, at(0, 16), "praxis")
    store.add_measurement(db, pid, "fat_ratio", 18.9, at(5, 16), "praxis")
    db.commit()
    series = {p["day"]: (p["value"], p["source"]) for p in store.daily_series(db, pid, "fat_ratio", day(10), TODAY)}
    assert series[TODAY.isoformat()] == (21.0, "withings")
    assert series[day(5).isoformat()] == (18.9, "praxis")


# ---------- Entry ----------

def test_save_and_delete_an_entry(db, pid):
    group, count = messungen.save(db, pid, "massband", at(0), {"circ_waist": 84.5, "circ_hip": 98,
                                                               "circ_neck": None, "weight": 80})
    db.commit()
    assert count == 2 and messungen.GROUP_PATTERN.match(group)  # weight is not a tape value
    entries = messungen.sessions(db, pid)
    assert entries[0]["id"] == group and [m for m, _ in entries[0]["values"]] == ["circ_waist", "circ_hip"]
    assert messungen.delete(db, pid, "massband-zzz") == 0
    assert messungen.delete(db, pid + 1, group) == 0          # another person's id does nothing
    assert messungen.delete(db, pid, group) == 2
    assert messungen.sessions(db, pid) == []


def test_entry_page_saves_validates_and_deletes(logged_in, db, me):
    page = logged_in.get("/messungen").get_data(as_text=True)
    assert "Maßband" in page and "Körperanalyse in der Praxis" in page and 'name="circ_calf_r"' in page
    today = util.today().isoformat()
    r = logged_in.post("/messungen/massband", {"datum": today, "circ_waist": "84,5", "circ_hip": "98"})
    assert r.status_code == 302
    rows = db.execute("SELECT metric, value, source FROM measurements WHERE person_id = ?", (me,)).fetchall()
    assert sorted((r["metric"], r["value"], r["source"]) for r in rows) == [
        ("circ_hip", 98.0, "massband"), ("circ_waist", 84.5, "massband")]
    r = logged_in.post("/messungen/praxis", {"datum": today, "uhrzeit": "16:30", "phase_angle": "5,9",
                                             "bcm": "31,2", "hydration": "47"})
    assert r.status_code == 302
    # out of range, empty, in the future, unknown field
    assert "höchstens" in logged_in.post("/messungen/massband", {"datum": today, "circ_waist": "900"},
                                         follow_redirects=True).get_data(as_text=True)
    assert "mindestens einen Wert" in logged_in.post("/messungen/massband", {"datum": today},
                                                     follow_redirects=True).get_data(as_text=True)
    future = (util.today() + timedelta(days=2)).isoformat()
    assert "Zukunft" in logged_in.post("/messungen/massband", {"datum": future, "circ_waist": "80"},
                                       follow_redirects=True).get_data(as_text=True)
    assert "unerwartete Felder" in logged_in.post("/messungen/massband", {"datum": today, "x": "1"},
                                                  follow_redirects=True).get_data(as_text=True)
    assert logged_in.post("/messungen/nichts", {"datum": today}).status_code == 404
    page = logged_in.get("/messungen").get_data(as_text=True)
    assert "Phasenwinkel 5,9" in page
    group = db.execute("SELECT group_id FROM measurements WHERE source = 'praxis' LIMIT 1").fetchone()[0]
    logged_in.post("/messungen/loeschen", {"eintrag": group})
    assert db.execute("SELECT COUNT(*) FROM measurements WHERE source = 'praxis'").fetchone()[0] == 0
    # deleting needs the token like every other change
    other = db.execute("SELECT group_id FROM measurements LIMIT 1").fetchone()[0]
    assert logged_in.client.post("/messungen/loeschen", data={"eintrag": other}).status_code == 400


# ---------- CSV ----------

def test_csv_with_german_headers_units_and_decimal_commas(db, pid):
    raw = ("Datum;Uhrzeit;Taille (cm);Hüfte;Oberarm links [cm];Bemerkung\n"
           "01.09.2026;07:30;84,5;98,0;31\n"
           "2026-09-08;;84,1 cm;97,6;30,8\n"
           "kein Datum;;80;90;30\n"
           "09.09.2099;;80;90;30\n"
           ";;;;\n").encode("utf-8")
    rows, skipped, unknown = messungen.read_csv(raw)
    assert [r[0] for r in rows] == [datetime(2026, 9, 1, 7, 30), datetime(2026, 9, 8, 8, 0)]
    assert rows[1][1] == {"circ_waist": 84.1, "circ_hip": 97.6, "circ_arm_l": 30.8}
    assert skipped == 2 and unknown == ["Bemerkung"]


def test_csv_import_keeps_only_values_of_the_kind_and_range(db, pid):
    raw = ("date,waist,hips,weight,phase angle\n"
           "2026-09-01,84.5,98,80.1,5.8\n"
           "2026-09-02,999,98,,\n").encode("utf-8")
    result = messungen.import_csv(db, pid, "massband", raw)
    db.commit()
    assert result["entries"] == 2 and result["values"] == 3   # 84.5, 98 and 98
    assert result["dropped"] == 3                             # weight, phase angle, 999 cm
    result = messungen.import_csv(db, pid, "praxis", raw)
    assert result["values"] == 2 and result["entries"] == 1    # weight and phase angle of row 1


def test_csv_errors(db, pid):
    for raw, message in ((b"", "leer"), (b"Taille;Huefte\n80;90\n", "Datum"),
                         (b"Datum;Notiz\n01.09.2026;x\n", "Messwert-Spalte"),
                         (b"x" * (messungen.CSV_MAX_BYTES + 1), "1 MB"),
                         (b"Datum;Taille\n\x00\x01", "Textdatei")):
        with pytest.raises(messungen.ImportError_, match=message):
            messungen.read_csv(raw)
    many = "Datum;Taille\n" + "01.09.2026;80\n" * (messungen.CSV_MAX_ROWS + 1)
    with pytest.raises(messungen.ImportError_, match="Zeilen"):
        messungen.read_csv(many.encode())


def test_csv_template_round_trip(logged_in, db, me):
    response = logged_in.get("/messungen/vorlage-praxis.csv")
    text = response.get_data(as_text=True)
    assert response.mimetype == "text/csv" and "Phasenwinkel (°)" in text and "Körperzellmasse (BCM) (kg)" in text
    header = text.lstrip("﻿").splitlines()[0]
    filled = header + "\n" + "01.09.2026;16:30;80;19" + ";" * (header.count(";") - 3) + "\n"
    rows, skipped, unknown = messungen.read_csv(filled.encode("utf-8"))
    assert rows[0][1] == {"weight": 80.0, "fat_ratio": 19.0} and not unknown
    logged_in.get("/messungen")
    r = logged_in.post("/messungen/import", {"art": "praxis",
                                             "datei": (io.BytesIO(filled.encode("utf-8")), "werte.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert "1 Einträge mit 2 Werten übernommen" in r.get_data(as_text=True)
    assert logged_in.get("/messungen/vorlage-nichts.csv").status_code == 404


# ---------- Body page ----------

def tape(db, pid, waist_of, hips=100.0, weeks=12):
    for w in range(weeks, -1, -1):
        messungen.save(db, pid, "massband", at(w * 7), {"circ_waist": waist_of(w), "circ_hip": hips,
                                                       "circ_arm_l": 31})
    db.commit()


def test_waist_ratios_and_circumference_overview(db, pid):
    persons.update(db, pid, height_cm=180)
    tape(db, pid, lambda w: 90 - (12 - w) * 0.25)
    whtr = auswertung.series(db, pid, "whtr", day(30), TODAY)
    assert whtr[-1]["value"] == pytest.approx(87 / 180)
    assert auswertung.series(db, pid, "whr", day(30), TODAY)[-1]["value"] == pytest.approx(0.87)
    c = messungen.circumferences(db, pid, TODAY)
    tiles = {t["key"]: t for t in c["tiles"]}
    assert tiles["circ_waist"]["value"] == 87 and tiles["circ_waist"]["change"] < 0
    assert c["ratios"]["whtr"]["category"] == ("gesund", "Gesunder Bereich")
    assert "Taille" in str(c["chart"])
    assert messungen.circumferences(db, pid + 99, TODAY) is None


def test_practice_overview_compares_with_home(db, pid):
    for n, (back, fat, muscle) in enumerate(((70, 20.0, 33.0), (14, 19.0, 33.6))):
        messungen.save(db, pid, "praxis", at(back, 16),
                       {"fat_ratio": fat, "muscle_mass": muscle, "phase_angle": 5.6 + n * 0.3, "bcm": 31 + n})
        store.add_measurement(db, pid, "fat_ratio", fat + 2, at(back + 1, 7), "withings")
        store.add_measurement(db, pid, "muscle_mass", muscle + 25, at(back + 2, 7), "withings")
    db.commit()
    pr = messungen.practice(db, pid, TODAY)
    assert pr["count"] == 2 and pr["phase"] == pytest.approx(5.9)
    assert "üblichen Bereich" in pr["phase_note"]
    cmp = {c["key"]: c for c in pr["comparisons"]}
    assert cmp["fat_ratio"]["mean"] == pytest.approx(2.0)
    assert cmp["fat_ratio"]["trend"]["same"] is True
    assert cmp["muscle_mass"]["mean"] == pytest.approx(25.0) and cmp["muscle_mass"]["note"]
    assert "Zu Hause" in str(cmp["fat_ratio"]["chart"]())
    rows = {r["key"]: r for r in pr["rows"]}
    assert rows["phase_angle"]["change"] == pytest.approx(0.3) and rows["phase_angle"]["trend"] == "gut"


def test_body_page_shows_tape_and_practice(logged_in, db, me):
    persons.update(db, me, height_cm=180)
    db.commit()
    page = logged_in.get("/koerper").get_data(as_text=True)
    assert "Noch keine Umfänge" in page and "Noch keine Analyse" in page
    today = util.today()
    for w in range(5):
        messungen.save(db, me, "massband", datetime.combine(today - timedelta(days=7 * w), datetime.min.time()),
                       {"circ_waist": 85 + w * 0.5, "circ_hip": 99})
    messungen.save(db, me, "praxis", datetime.combine(today, datetime.min.time()).replace(hour=16),
                   {"fat_ratio": 19.5, "phase_angle": 6.1})
    store.add_measurement(db, me, "fat_ratio", 21.0, datetime.combine(today, datetime.min.time()).replace(hour=7),
                          "withings")
    db.commit()
    page = logged_in.get("/koerper?vergleich=fat_ratio").get_data(as_text=True)
    assert "Taille zu Größe" in page and "0,47" in page
    assert "Phasenwinkel 6,1°" in page and "Zu Hause und in der Praxis" in page
    assert 'data-vergleich="fat_ratio">' in page


# ---------- Findings, outlook, overview ----------

def test_waist_findings(db, pid):
    persons.update(db, pid, height_cm=170)
    tape(db, pid, lambda w: 92 - (12 - w) * 0.3)                # 0.3 cm a week, eleven weeks shown
    f = befunde.waist(db, pid, person(db, pid), TODAY)
    assert f.tone == befunde.GOOD and f.title_b == "3,3 cm schmaler geworden."
    db.execute("DELETE FROM measurements")
    tape(db, pid, lambda w: 95.0)                               # steady, but above half the height
    f = befunde.waist(db, pid, person(db, pid), TODAY)
    assert f.tone == befunde.INFO and f.big == "0,56" and "halben Körpergröße" in f.title_b


def test_practice_finding(db, pid):
    messungen.save(db, pid, "praxis", at(60, 16), {"phase_angle": 6.0, "bcm": 32})
    messungen.save(db, pid, "praxis", at(10, 16), {"phase_angle": 5.5, "bcm": 31.5})
    db.commit()
    f = befunde.practice(db, pid, person(db, pid), TODAY)
    assert f.tone == befunde.WARN and f.big == "−0,5°"
    assert "phasenwinkel" in str(f.chart()).lower()


def test_waist_outlook_and_overview_tile(db, pid):
    persons.update(db, pid, height_cm=180)
    for w in range(52, -1, -1):
        rate = [-0.4, 0.3][(w // 8) % 2]
        messungen.save(db, pid, "massband", at(w * 7), {"circ_waist": 95 + rate * (w % 8)})
    db.commit()
    o = ausblick.trend(db, pid, person(db, pid), "circ_waist", TODAY, 84)
    assert o.direction == "down" and o.paths["gut"].end < o.paths["schlecht"].end
    tiles = {t["key"]: t for t in uebersicht.sources(db, pid, person(db, pid), TODAY)}
    assert tiles["manuell"]["state"] == "an" and tiles["manuell"]["status"].startswith("zuletzt")
