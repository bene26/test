"""Fill a database with a year of made-up health data for three persons (screenshots, trying
things out).

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

from gesundheit import persons, store, util  # noqa: E402
from gesundheit.db import connect, init_db  # noqa: E402

# Three household members with different devices and habits. Each carries a few patterns
# for the findings: Anna trains too hard and stepped up her last week, Ben's blood pressure is
# raised, his bedtime irregular and his Sundays quiet, Lena is on a step streak.
PROFILES = {
    "Anna": {"color": "pink", "birth_year": 1986, "height_cm": 181, "watch": "garmin",
             "watch_share": 0.85, "steps": 9800, "sleep": 412, "weight": (82.4, -3.6),
             "fat": (22.5, -2.2), "resting": (58, -3), "bp": (131, 84), "goal_steps": 10000,
             "goal_weight_dg": 785, "goal_weight_days": 120, "workout_hr": 152,
             "hard_last_week": True,
             "sports": {1: "laufen", 3: "kraft", 5: "radfahren", 6: "wandern"}},
    "Ben": {"color": "blau", "birth_year": 1984, "height_cm": 188, "watch": "apple_watch",
            "watch_share": 0.95, "steps": 7600, "sleep": 395, "weight": (91.0, 1.2),
            "fat": (24.0, 0.6), "resting": (63, 1), "bp": (140, 90), "goal_steps": 8000,
            "bed_spread": 75, "sunday": 0.45,
            "sports": {2: "radfahren", 6: "laufen"}},
    "Lena": {"color": "gruen", "birth_year": 2010, "height_cm": 164, "watch": "garmin",
             "watch_share": 0.9, "steps": 11800, "sleep": 470, "weight": (52.0, 1.5),
             "fat": None, "resting": (61, -2), "bp": None, "goal_steps": 12000,
             "streak": 9, "workout_hr": 128,
             "sports": {0: "ballsport", 2: "schwimmen", 4: "ballsport"}},
}


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute))


def fill(db, pid: int, today: date, days: int = 365, seed: int = 7, profile: dict | None = None):
    profile = profile or PROFILES["Anna"]
    rng = random.Random(seed)
    start = today - timedelta(days=days - 1)
    measurements, daily = [], []
    workout_no = 0
    main_watch = profile["watch"]
    other_watch = "apple_watch" if main_watch == "garmin" else "garmin"
    for i, day in enumerate(util.days(start, today)):
        progress = i / max(days - 1, 1)
        weekend = day.weekday() >= 5
        back = (today - day).days
        hard_week = profile.get("hard_last_week") and back < 7
        source = main_watch if rng.random() < profile["watch_share"] else other_watch
        # Scale: most mornings; the same weighing also arrives via Apple Health.
        if rng.random() < 0.7:
            base, drift = profile["weight"]
            weight = base + drift * progress + 0.6 * math.sin(i / 9) + rng.gauss(0, 0.25)
            at = _at(day, 7, rng.randint(0, 25))
            group = f"demo{i}"
            rows = [("weight", weight), ("pulse", 62 + rng.gauss(0, 3))]
            if profile["fat"]:
                fbase, fdrift = profile["fat"]
                fat = fbase + fdrift * progress + rng.gauss(0, 0.3)
                rows += [("fat_ratio", fat), ("fat_mass", weight * fat / 100),
                         ("muscle_mass", weight * 0.745 + rng.gauss(0, 0.2)),
                         ("hydration", weight * 0.545), ("bone_mass", 3.2),
                         ("fat_free_mass", weight * (1 - fat / 100)),
                         ("visceral_fat", 9 - 2 * progress), ("bmr", 1780 - 40 * progress)]
            measurements += [(m, v, at, "withings", group) for m, v in rows]
            measurements.append(("weight", weight, at, "apple_withings", ""))
        if profile["bp"]:
            for hour in (7, 21):
                if rng.random() < 0.7:
                    at = _at(day, hour, rng.randint(30, 50))
                    sys_v = profile["bp"][0] - 6 * progress + rng.gauss(0, 5) + (3 if hour == 21 else 0)
                    dia_v = profile["bp"][1] - 3 * progress + rng.gauss(0, 3.5)
                    group = f"bd{i}{hour}"
                    measurements += [("bp_sys", sys_v, at, "withings", group),
                                     ("bp_dia", dia_v, at, "withings", group),
                                     ("pulse", 64 + rng.gauss(0, 4), at, "withings", group)]
            if day.day == 3:
                at = _at(day, 19, 12)
                measurements += [("ekg_afib", 0 if rng.random() < 0.9 else 2, at, "withings", f"ecg{i}"),
                                 ("ekg_puls", 63 + rng.gauss(0, 3), at, "withings", f"ecg{i}")]
            if day.weekday() == 0:
                measurements.append(("pwv", 7.4 + rng.gauss(0, 0.3), _at(day, 7, 5), "withings", ""))
        if rng.random() < 0.05:
            measurements.append(("temperature", 36.6 + rng.gauss(0, 0.25), _at(day, 8), "withings", ""))

        # Sleep first: a short night makes the next day a little worse (relationships to find).
        asleep = profile["sleep"] + 35 * math.sin(i / 6) + (25 if weekend else 0) + rng.gauss(0, 28)
        bed = _at(day - timedelta(days=1), 22, 50) + timedelta(
            minutes=rng.gauss(15, profile.get("bed_spread", 25) if back < 30 else 25))
        late = (bed - _at(day - timedelta(days=1), 22, 50)).total_seconds() / 3600
        asleep -= late * 25
        sleep_factor = (asleep - profile["sleep"]) / 60
        awake = max(8, rng.gauss(32, 10))
        deep = asleep * (0.17 + rng.gauss(0, 0.02))
        rem = asleep * (0.22 + rng.gauss(0, 0.02))
        store.upsert_sleep(db, pid, day, source, {
            "bed_start": bed, "bed_end": bed + timedelta(minutes=asleep + awake),
            "asleep_min": asleep, "deep_min": deep, "rem_min": rem,
            "light_min": asleep - deep - rem, "awake_min": awake,
            "score": None if source == "apple_watch" else min(100, round(74 + (asleep - 420) / 6 + rng.gauss(0, 5))),
            "hr_avg": profile["resting"][0] + 3, "rr_avg": 14 + rng.gauss(0, 0.5)})

        steps = max(1800, profile["steps"] + 2500 * math.sin(i / 5) + (2500 if weekend else 0)
                    + 600 * sleep_factor + rng.gauss(0, 1800))
        if day.weekday() == 6:
            steps *= profile.get("sunday", 1)
        if back < profile.get("streak", 0):
            steps = max(steps, profile["goal_steps"] * (1.04 + rng.random() * 0.2))
        active_min = max(5, steps / 260 + rng.gauss(0, 8))
        daily += [("steps", day, source, steps),
                  ("distance_km", day, source, steps * 0.00074),
                  ("active_kcal", day, source, steps * 0.045 + rng.gauss(0, 40)),
                  ("floors", day, source, max(0, rng.gauss(11, 5))),
                  ("active_min", day, source, active_min),
                  ("steps", day, "iphone", steps * 0.72),
                  ("hr_min", day, source, 48 + rng.gauss(0, 2)),
                  ("hr_max", day, source, 138 + rng.gauss(0, 12))]
        base, drift = profile["resting"]
        resting = base + drift * progress - 1.6 * sleep_factor + rng.gauss(0, 1.3)
        if hard_week:
            resting += 3 + (7 - back) * 0.6  # the body notices the harder week
        if source == "apple_watch":
            daily += [("resting_hr", day, "apple_watch", resting + 1),
                      ("hrv_sdnn", day, "apple_watch", 52 + 6 * sleep_factor + rng.gauss(0, 7))]
        else:
            daily += [("resting_hr", day, "garmin", resting),
                      ("hrv_rmssd", day, "garmin", 41 + 6 * progress + 5 * sleep_factor + rng.gauss(0, 4)),
                      ("body_battery_max", day, "garmin", min(100, 80 + 8 * sleep_factor + rng.gauss(0, 7))),
                      ("body_battery_min", day, "garmin", max(5, 22 + rng.gauss(0, 7))),
                      ("stress_avg", day, "garmin", max(10, 31 - 3 * sleep_factor + rng.gauss(0, 7))),
                      ("readiness", day, "garmin", min(100, max(5, 62 + 10 * sleep_factor + rng.gauss(0, 12)))),
                      ("spo2", day, "garmin", min(100, 95.5 + rng.gauss(0, 0.8))),
                      ("resp_rate", day, "garmin", 14.2 + rng.gauss(0, 0.6))]
        if day.weekday() == 6 and main_watch == "garmin":
            measurements.append(("vo2max", 46.5 + 2 * progress, _at(day, 12), "garmin", ""))

        kind = profile["sports"].get(day.weekday())
        if hard_week and not kind:
            kind = "laufen"
        if kind:
            workout_no += 1
            begin = _at(day, 18 if not weekend else 10, 5)
            minutes = {"laufen": 42, "kraft": 50, "radfahren": 95, "wandern": 150,
                       "ballsport": 75, "schwimmen": 45}[kind] + rng.gauss(0, 8)
            if hard_week:
                minutes *= 1.4
            km = {"laufen": 7.8, "radfahren": 36, "wandern": 11, "schwimmen": 1.6}.get(kind, 0)
            data = {"kind": kind, "started_at": begin, "ended_at": begin + timedelta(minutes=minutes),
                    "duration_min": minutes, "distance_km": km * (1 + rng.gauss(0, 0.08)) or None,
                    "energy_kcal": minutes * 8,
                    "hr_avg": profile.get("workout_hr", 135) + rng.gauss(0, 7), "hr_max": 168}
            store.upsert_workout(db, pid, source, f"demo{workout_no}", data)
            if kind == "laufen":
                store.upsert_workout(db, pid, "iphone", f"demo-iphone{workout_no}",
                                     dict(data, started_at=begin + timedelta(minutes=1)))
    store.add_measurements(db, pid, measurements)
    store.set_daily_many(db, pid, daily)
    db.commit()


def fill_household(db, today: date, days: int = 365) -> list[int]:
    """Create (or reuse) the three example persons and fill them. Returns their ids."""
    ids = []
    for seed, (name, profile) in enumerate(PROFILES.items(), start=7):
        row = db.execute("SELECT id FROM persons WHERE name = ?", (name,)).fetchone()
        pid = row["id"] if row else persons.create(
            db, name, profile["color"], birth_year=profile["birth_year"],
            height_cm=profile["height_cm"], goal_steps=profile["goal_steps"],
            goal_weight_dg=profile.get("goal_weight_dg"),
            goal_weight_date=(today + timedelta(days=profile["goal_weight_days"])).isoformat()
            if profile.get("goal_weight_days") else None)
        fill(db, pid, today, days, seed, profile)
        ids.append(pid)
    db.commit()
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datenordner")
    parser.add_argument("--tage", type=int, default=365)
    args = parser.parse_args()
    path = Path(args.datenordner) / "gesundheit.sqlite3"
    init_db(path)
    conn = connect(path)
    try:
        fill_household(conn, util.today(), args.tage)
    finally:
        conn.close()
    print(f"Beispieldaten für {len(PROFILES)} Personen und {args.tage} Tage in {path} geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
