"""Fill a database with a year of made-up health data (for screenshots and trying things out).

    python tools/demo_daten.py /pfad/zum/datenordner [--tage 365]

Never run this against your real data folder: it writes values from all sources.
"""

import argparse
import math
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gesundheit import store, util  # noqa: E402
from gesundheit.db import connect, init_db  # noqa: E402


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute))


def fill(db, today: date, days: int = 365, seed: int = 7) -> None:
    rng = random.Random(seed)
    start = today - timedelta(days=days - 1)
    measurements, daily = [], []
    workout_no = 0
    for i, day in enumerate(util.days(start, today)):
        progress = i / max(days - 1, 1)
        weekend = day.weekday() >= 5
        apple_day = rng.random() < 0.15          # Garmin not worn: Apple Watch instead
        # Withings scale, most mornings; the same weighing also arrives via Apple Health.
        if rng.random() < 0.75:
            weight = 82.4 - 3.6 * progress + 0.6 * math.sin(i / 9) + rng.gauss(0, 0.25)
            at = _at(day, 7, rng.randint(0, 25))
            group = f"demo{i}"
            fat = 22.5 - 2.2 * progress + rng.gauss(0, 0.3)
            for metric, value in (("weight", weight), ("fat_ratio", fat),
                                  ("fat_mass", weight * fat / 100),
                                  ("muscle_mass", weight * 0.745 + rng.gauss(0, 0.2)),
                                  ("hydration", weight * 0.545), ("bone_mass", 3.2),
                                  ("fat_free_mass", weight * (1 - fat / 100)),
                                  ("visceral_fat", 9 - 2 * progress), ("bmr", 1780 - 40 * progress),
                                  ("pulse", 62 + rng.gauss(0, 3))):
                measurements.append((metric, value, at, "withings", group))
            measurements.append(("weight", weight, at, "apple_withings", ""))
        # Blood pressure morning and evening, most days.
        for hour in (7, 21):
            if rng.random() < 0.7:
                at = _at(day, hour, rng.randint(30, 50))
                sys_v = 131 - 6 * progress + rng.gauss(0, 5) + (3 if hour == 21 else 0)
                dia_v = 84 - 3 * progress + rng.gauss(0, 3.5)
                group = f"bd{i}{hour}"
                measurements += [("bp_sys", sys_v, at, "withings", group),
                                 ("bp_dia", dia_v, at, "withings", group),
                                 ("pulse", 64 + rng.gauss(0, 4), at, "withings", group)]
        if day.day == 3:
            at = _at(day, 19, 12)
            measurements += [("ekg_afib", 0 if rng.random() < 0.9 else 2, at, "withings", f"ecg{i}"),
                             ("ekg_puls", 63 + rng.gauss(0, 3), at, "withings", f"ecg{i}")]
        if rng.random() < 0.06:
            measurements.append(("temperature", 36.6 + rng.gauss(0, 0.25), _at(day, 8), "withings", ""))
        if day.weekday() == 0:
            measurements.append(("pwv", 7.4 + rng.gauss(0, 0.3), _at(day, 7, 5), "withings", ""))

        # Activity: Garmin on most days, Apple Watch on the others, iPhone always (fewer steps).
        base_steps = 9800 + 2500 * math.sin(i / 5) + (2500 if weekend else 0) + rng.gauss(0, 1800)
        steps = max(1800, base_steps)
        source = "apple_watch" if apple_day else "garmin"
        active_min = max(5, steps / 260 + rng.gauss(0, 8))
        daily += [("steps", day, source, steps),
                  ("distance_km", day, source, steps * 0.00074),
                  ("active_kcal", day, source, steps * 0.045 + rng.gauss(0, 40)),
                  ("floors", day, source, max(0, rng.gauss(11, 5))),
                  ("active_min", day, source, active_min),
                  ("steps", day, "iphone", steps * 0.72),
                  ("hr_min", day, source, 48 + rng.gauss(0, 2)),
                  ("hr_max", day, source, 138 + rng.gauss(0, 12))]
        resting = 58 - 3 * progress + rng.gauss(0, 1.6)
        if apple_day:
            daily += [("resting_hr", day, "apple_watch", resting + 1),
                      ("hrv_sdnn", day, "apple_watch", 52 + rng.gauss(0, 9))]
        else:
            daily += [("resting_hr", day, "garmin", resting),
                      ("hrv_rmssd", day, "garmin", 41 + 6 * progress + rng.gauss(0, 5)),
                      ("body_battery_max", day, "garmin", min(100, 82 + rng.gauss(0, 9))),
                      ("body_battery_min", day, "garmin", max(5, 22 + rng.gauss(0, 7))),
                      ("stress_avg", day, "garmin", max(10, 31 + rng.gauss(0, 7))),
                      ("readiness", day, "garmin", min(100, max(5, 62 + rng.gauss(0, 15)))),
                      ("spo2", day, "garmin", min(100, 95.5 + rng.gauss(0, 0.8))),
                      ("resp_rate", day, "garmin", 14.2 + rng.gauss(0, 0.6))]
        if day.weekday() == 6:
            measurements.append(("vo2max", 46.5 + 2 * progress, _at(day, 12), "garmin", ""))

        # Sleep: one night per day from the watch that was worn.
        asleep = 412 + 35 * math.sin(i / 6) + (25 if weekend else 0) + rng.gauss(0, 28)
        bed = _at(day - timedelta(days=1), 22, 50) + timedelta(minutes=rng.gauss(15, 25))
        awake = max(8, rng.gauss(32, 10))
        deep = asleep * (0.17 + rng.gauss(0, 0.02))
        rem = asleep * (0.22 + rng.gauss(0, 0.02))
        store.upsert_sleep(db, day, "apple_watch" if apple_day else "garmin", {
            "bed_start": bed, "bed_end": bed + timedelta(minutes=asleep + awake),
            "asleep_min": asleep, "deep_min": deep, "rem_min": rem,
            "light_min": asleep - deep - rem, "awake_min": awake,
            "score": None if apple_day else min(100, round(74 + (asleep - 420) / 6 + rng.gauss(0, 5))),
            "hr_avg": resting + 3, "rr_avg": 14 + rng.gauss(0, 0.5)})

        # Trainings: three to four per week; some recorded by both Garmin and the phone.
        if day.weekday() in (1, 3, 5) or (day.weekday() == 6 and rng.random() < 0.5):
            workout_no += 1
            kind = {1: "laufen", 3: "kraft", 5: "radfahren", 6: "wandern"}[day.weekday()]
            begin = _at(day, 18 if not weekend else 10, 5)
            minutes = {"laufen": 42, "kraft": 50, "radfahren": 95, "wandern": 150}[kind] + rng.gauss(0, 8)
            km = {"laufen": 7.8, "kraft": 0, "radfahren": 36, "wandern": 11}[kind] * (1 + rng.gauss(0, 0.08))
            data = {"kind": kind, "started_at": begin, "ended_at": begin + timedelta(minutes=minutes),
                    "duration_min": minutes, "distance_km": km or None,
                    "energy_kcal": minutes * {"laufen": 11, "kraft": 6, "radfahren": 9, "wandern": 6}[kind],
                    "hr_avg": {"laufen": 152, "kraft": 112, "radfahren": 128, "wandern": 104}[kind] + rng.gauss(0, 4),
                    "hr_max": {"laufen": 174, "kraft": 148, "radfahren": 162, "wandern": 131}[kind]}
            store.upsert_workout(db, "apple_watch" if apple_day else "garmin", f"demo{workout_no}", data)
            if kind == "laufen":
                store.upsert_workout(db, "iphone", f"demo-iphone{workout_no}",
                                     dict(data, started_at=begin + timedelta(minutes=1)))
    store.add_measurements(db, measurements)
    store.set_daily_many(db, daily)
    db.execute("INSERT INTO settings (key, value) VALUES ('height_cm', '181') "
               "ON CONFLICT(key) DO NOTHING")
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datenordner")
    parser.add_argument("--tage", type=int, default=365)
    args = parser.parse_args()
    path = Path(args.datenordner) / "gesundheit.sqlite3"
    init_db(path)
    conn = connect(path)
    try:
        fill(conn, util.today(), args.tage)
    finally:
        conn.close()
    print(f"Beispieldaten für {args.tage} Tage in {path} geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
