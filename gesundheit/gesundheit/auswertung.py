"""Analyses: periods against each other, best values and streaks, weekday patterns,
relationships between values, comparisons between persons, and reports.

Every value that can be analysed has a key here: all metrics from katalog.METRICS plus a few
derived from sleep and training. Values per day always follow the source order (store.py).
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

from . import bewertung, store, util
from .katalog import METRICS, NO_CHART


@dataclass(frozen=True)
class Key:
    key: str
    label: str
    unit: str
    decimals: int
    good: str        # up, down or ""
    agg: str         # how days add up over a period: sum or mean
    step: float      # "per … more" in relationship texts
    step_label: str
    goal_field: str = ""   # person column with the daily goal


def _metric_key(m) -> Key:
    steps = {"steps": (1000, "1.000 Schritte"), "active_min": (10, "10 Minuten"),
             "active_kcal": (100, "100 kcal"), "distance_km": (1, "1 km"), "floors": (5, "5 Etagen"),
             "stress_avg": (10, "10 Punkte Stress"), "weight": (1, "1 kg")}
    step, step_label = steps.get(m.key, (1, f"1 {m.unit}".strip()))
    goal = {"steps": "goal_steps", "active_min": "goal_active_min",
            "active_kcal": "goal_active_kcal"}.get(m.key, "")
    return Key(m.key, m.label, m.unit, m.decimals, m.good, "sum" if m.agg == "sum" else "mean",
               step, step_label, goal)


KEYS: dict[str, Key] = {m.key: _metric_key(m) for m in METRICS.values() if m.key not in NO_CHART}
KEYS.update({
    "schlaf_dauer": Key("schlaf_dauer", "Schlafdauer", "h", 1, "up", "mean", 1, "1 Stunde Schlaf",
                        "goal_sleep_min"),
    "schlaf_bewertung": Key("schlaf_bewertung", "Schlafbewertung", "", 0, "up", "mean", 10,
                            "10 Punkte Schlafbewertung"),
    "tiefschlaf": Key("tiefschlaf", "Tiefschlaf", "min", 0, "up", "mean", 15, "15 Minuten Tiefschlaf"),
    "rem_schlaf": Key("rem_schlaf", "REM-Schlaf", "min", 0, "up", "mean", 15, "15 Minuten REM"),
    "zubettgehen": Key("zubettgehen", "Zubettgehen", "Uhr", 2, "", "mean", 1, "1 Stunde später ins Bett"),
    "training_min": Key("training_min", "Trainingsminuten", "min", 0, "up", "sum", 30,
                        "30 Minuten Training"),
    "whtr": Key("whtr", "Taille zu Größe", "", 2, "down", "mean", 0.05,
                "0,05 Taille zu Größe"),
    "whr": Key("whr", "Taille zu Hüfte", "", 2, "down", "mean", 0.05, "0,05 Taille zu Hüfte"),
})
GROUPS = [
    ("Aktivität", ["steps", "active_min", "active_kcal", "distance_km", "floors", "training_min"]),
    ("Schlaf", ["schlaf_dauer", "schlaf_bewertung", "tiefschlaf", "rem_schlaf", "zubettgehen"]),
    ("Herz und Erholung", ["resting_hr", "hrv_rmssd", "hrv_sdnn", "spo2", "resp_rate",
                           "body_battery_max", "stress_avg", "readiness", "vo2max"]),
    ("Körper", ["weight", "fat_ratio", "muscle_mass", "fat_mass", "hydration", "bone_mass",
                "visceral_fat", "bmr"]),
    ("Blutdruck und mehr", ["bp_sys", "bp_dia", "pulse", "temperature", "pwv", "hr_min", "hr_max"]),
    ("Umfänge", ["circ_waist", "circ_belly", "circ_hip", "whtr", "whr", "circ_chest", "circ_neck",
                 "circ_shoulders", "circ_arm_l", "circ_arm_r", "circ_thigh_l", "circ_thigh_r",
                 "circ_calf_l", "circ_calf_r"]),
    ("Analyse in der Praxis", ["phase_angle", "bcm", "ecm", "ecm_bcm", "cell_share", "ecw", "icw",
                               "bia_r", "bia_xc"]),
]


def fmt(key: str, value) -> str:
    """Value with unit, clock time for bedtimes."""
    meta = KEYS[key]
    if value is None:
        return "–"
    if meta.unit == "Uhr":
        minutes = round(value * 60) % 1440
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    if meta.unit == "h":
        return util.fmt_minutes(value * 60)
    return util.fmt_num(value, meta.decimals) + (f" {meta.unit}" if meta.unit else "")


def series(db, pid: int, key: str, start, end) -> list[dict]:
    """[{day, value, source}] for any analysis key, sorted by day."""
    start, end = util.to_date(start), util.to_date(end)
    if key in METRICS:
        return store.daily_series(db, pid, key, start, end)
    if key in ("whtr", "whr"):
        return _ratio(db, pid, key, start, end)
    if key == "training_min":
        totals = {d.isoformat(): 0.0 for d in util.days(start, end)}
        for w in store.workouts(db, pid, start, end):
            totals[w["day"]] = totals.get(w["day"], 0.0) + (w["duration_min"] or 0)
        first = _first_day(db, pid)
        return [{"day": d, "value": v, "source": ""} for d, v in sorted(totals.items())
                if first and d >= first]
    nights = store.sleep_series(db, pid, start, end)
    result = []
    for n in nights:
        if key == "schlaf_dauer":
            value = n["asleep_min"] / 60 if n["asleep_min"] else None
        elif key == "schlaf_bewertung":
            value = n["score"]
        elif key == "tiefschlaf":
            value = n["deep_min"]
        elif key == "rem_schlaf":
            value = n["rem_min"]
        else:  # zubettgehen: hours since midnight, after midnight counted as 24+
            dt = util.to_datetime(n["bed_start"])
            value = None
            if dt:
                value = dt.hour + dt.minute / 60
                if value < 12:
                    value += 24
        if value is not None:
            result.append({"day": n["night"], "value": float(value), "source": n["source"]})
    return result


def height(db, pid: int) -> float | None:
    """Height from the profile, else the latest measured one."""
    row = db.execute("SELECT height_cm FROM persons WHERE id = ?", (pid,)).fetchone()
    if row and row["height_cm"]:
        return row["height_cm"]
    measured = store.latest(db, pid, "height")
    return measured["value"] if measured else None


def _ratio(db, pid, key, start, end) -> list[dict]:
    """Waist to height (needs a height) or waist to hip (both on the same day)."""
    waist = store.daily_series(db, pid, "circ_waist", start, end)
    if key == "whtr":
        h = height(db, pid)
        return [{"day": p["day"], "value": p["value"] / h, "source": p["source"]}
                for p in waist] if h else []
    hips = {p["day"]: p["value"] for p in store.daily_series(db, pid, "circ_hip", start, end)}
    return [{"day": p["day"], "value": p["value"] / hips[p["day"]], "source": p["source"]}
            for p in waist if hips.get(p["day"])]


def _first_day(db, pid) -> str | None:
    row = db.execute("SELECT MIN(day) FROM (SELECT MIN(day) AS day FROM daily_values WHERE "
                     "person_id = ? UNION ALL SELECT MIN(day) FROM workouts WHERE person_id = ?)",
                     (pid, pid)).fetchone()
    return row[0] if row else None


def available(db, pid: int, start, end) -> list[str]:
    """Keys that have at least a few values in the period (for the pickers)."""
    return [k for k in KEYS if len(series(db, pid, k, start, end)) >= 3]


# ---------- Periods ----------

def _period_summary(points, meta: Key, days: int) -> dict:
    values = [p["value"] for p in points]
    result = store.summary(values)
    result["total"] = sum(values) if values else None
    result["days"] = days
    return result


def change(current, previous) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def compare_periods(db, pid: int, key: str, days: int, end: date) -> dict:
    meta = KEYS[key]
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    year_end = end - timedelta(days=364)   # 52 weeks back: same weekdays
    year_start = start - timedelta(days=364)
    cur = series(db, pid, key, start, end)
    prev = series(db, pid, key, prev_start, prev_end)
    year = series(db, pid, key, year_start, year_end)
    result = {"meta": meta, "start": start, "end": end, "prev_start": prev_start,
              "prev_end": prev_end, "year_start": year_start, "year_end": year_end,
              "current": _period_summary(cur, meta, days),
              "previous": _period_summary(prev, meta, days),
              "year": _period_summary(year, meta, days)}
    result["change_prev"] = change(result["current"]["avg"], result["previous"]["avg"])
    result["change_year"] = change(result["current"]["avg"], result["year"]["avg"])
    result["trend_prev"] = bewertung.trend_class(result["change_prev"], meta.good)
    result["trend_year"] = bewertung.trend_class(result["change_year"], meta.good)

    def shifted(points, offset, label_from):
        out = []
        for p in points:
            day = util.to_date(p["day"])
            out.append({"day": (day + timedelta(days=offset)).isoformat(), "value": p["value"],
                        "label": f"{util.fmt_day(day)}{label_from}"})
        return out

    result["overlay"] = [
        {"label": "Dieser Zeitraum", "cls": "p-jetzt", "points": cur},
        {"label": "Zeitraum davor", "cls": "p-davor", "points": shifted(prev, days, ""),
         "dashed": True},
        {"label": "Vor einem Jahr", "cls": "p-vorjahr", "points": shifted(year, 364, ""),
         "dashed": True},
    ]
    return result


def records(db, pid: int, key: str, person: dict, today: date) -> dict:
    """Best and worst day of all time, all-time average, goal streaks."""
    meta = KEYS[key]
    points = series(db, pid, key, date(2000, 1, 1), today)
    if not points:
        return {"count": 0}
    best = (max if meta.good != "down" else min)(points, key=lambda p: p["value"])
    worst = (min if meta.good != "down" else max)(points, key=lambda p: p["value"])
    result = {"count": len(points), "first": points[0]["day"], "best": best, "worst": worst,
              "avg": sum(p["value"] for p in points) / len(points)}
    goal = person.get(meta.goal_field) if meta.goal_field else None
    if goal and key == "schlaf_dauer":
        goal = goal / 60
    if goal:
        reached = {p["day"] for p in points if p["value"] >= goal}
        longest, run, run_end, longest_end = 0, 0, None, None
        day = util.to_date(points[0]["day"])
        while day <= today:
            if day.isoformat() in reached:
                run += 1
                run_end = day
                if run > longest:
                    longest, longest_end = run, run_end
            else:
                run = 0
            day += timedelta(days=1)
        current = 0
        day = today if today.isoformat() in reached else today - timedelta(days=1)
        while day.isoformat() in reached:
            current += 1
            day -= timedelta(days=1)
        result.update(goal=goal, reached_days=len(reached), longest=longest,
                      longest_end=longest_end, current=current,
                      reached_share=len(reached) / len(points) * 100)
    return result


WEEKDAYS_LONG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def weekday_profile(points: list[dict]) -> list[float | None]:
    buckets: list[list[float]] = [[] for _ in range(7)]
    for p in points:
        buckets[util.to_date(p["day"]).weekday()].append(p["value"])
    return [sum(b) / len(b) if b else None for b in buckets]


# ---------- Relationships ----------

def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return slope, my - slope * mx


def strength(r: float | None) -> tuple[str, str]:
    if r is None:
        return "keiner", "Zu wenige Werte"
    a = abs(r)
    if a < 0.1:
        return "keiner", "kein erkennbarer Zusammenhang"
    if a < 0.3:
        return "schwach", "schwacher Zusammenhang"
    if a < 0.5:
        return "mittel", "mittlerer Zusammenhang"
    return "stark", "starker Zusammenhang"


def pairs(db, pid: int, xkey: str, ykey: str, start, end, lag: int = 0) -> list[tuple]:
    """(x, y, day of x) for days where x has a value and y has one `lag` days later."""
    start, end = util.to_date(start), util.to_date(end)
    xs = {p["day"]: p["value"] for p in series(db, pid, xkey, start, end)}
    ys = {p["day"]: p["value"] for p in series(db, pid, ykey, start, end + timedelta(days=lag))}
    out = []
    for day, x in sorted(xs.items()):
        target = (util.to_date(day) + timedelta(days=lag)).isoformat()
        if target in ys:
            out.append((x, ys[target], day))
    return out


def relationship(db, pid: int, xkey: str, ykey: str, start, end, lag: int = 0) -> dict:
    data = pairs(db, pid, xkey, ykey, start, end, lag)
    xs = [d[0] for d in data]
    ys = [d[1] for d in data]
    r = pearson(xs, ys)
    fit = linear_fit(xs, ys)
    level, text = strength(r)
    xm, ym = KEYS[xkey], KEYS[ykey]
    effect = None
    if fit and r is not None and abs(r) >= 0.1:
        delta = fit[0] * xm.step
        unit = "min" if ym.unit == "h" else ym.unit
        amount = abs(delta * 60) if ym.unit == "h" else abs(delta)
        effect = (f"Pro {xm.step_label} mehr: im Schnitt {util.fmt_num(amount, max(ym.decimals, 1))}"
                  f"{' ' + unit if unit and unit != 'Uhr' else ''} {'mehr' if delta > 0 else 'weniger'} "
                  f"{ym.label}" if ym.unit != "Uhr" else None)
    return {"x": xm, "y": ym, "lag": lag, "n": len(data), "r": r, "fit": fit, "level": level,
            "text": text, "effect": effect, "points": data}


# (x, y, lag, title, sentence if positive, sentence if negative)
PRESETS = [
    ("schlaf_dauer", "resting_hr", 0, "Schlaf und Ruhepuls",
     "Nach längeren Nächten ist dein Ruhepuls eher höher.",
     "Nach längeren Nächten ist dein Ruhepuls niedriger."),
    ("schlaf_dauer", "hrv_rmssd", 0, "Schlaf und HRV",
     "Nach längeren Nächten ist deine Herzfrequenzvariabilität höher, ein Zeichen guter Erholung.",
     "Nach längeren Nächten ist deine Herzfrequenzvariabilität eher niedriger."),
    ("schlaf_dauer", "hrv_sdnn", 0, "Schlaf und HRV",
     "Nach längeren Nächten ist deine Herzfrequenzvariabilität höher.",
     "Nach längeren Nächten ist deine Herzfrequenzvariabilität eher niedriger."),
    ("steps", "schlaf_dauer", 1, "Bewegung und Schlaf",
     "An Tagen mit mehr Schritten schläfst du in der Nacht danach länger.",
     "An Tagen mit mehr Schritten schläfst du in der Nacht danach kürzer."),
    ("active_min", "schlaf_bewertung", 1, "Aktive Minuten und Schlafqualität",
     "Mehr aktive Minuten gehen mit einer besseren Schlafbewertung in der Nacht danach einher.",
     "Nach aktiven Tagen ist deine Schlafbewertung eher schlechter."),
    ("training_min", "readiness", 1, "Training und Bereitschaft am nächsten Tag",
     "Nach Trainingstagen ist deine Trainingsbereitschaft eher höher.",
     "Nach viel Training ist deine Trainingsbereitschaft am nächsten Tag niedriger. Erholung einplanen."),
    ("training_min", "body_battery_max", 1, "Training und Body Battery",
     "Nach Trainingstagen lädt deine Body Battery am nächsten Tag höher auf.",
     "Nach viel Training lädt deine Body Battery am nächsten Tag weniger auf."),
    ("training_min", "resting_hr", 1, "Training und Ruhepuls am nächsten Tag",
     "Nach viel Training ist dein Ruhepuls am nächsten Tag höher, der Körper arbeitet noch.",
     "Nach Trainingstagen ist dein Ruhepuls am nächsten Tag niedriger."),
    ("stress_avg", "schlaf_bewertung", 1, "Stress und Schlaf",
     "Nach stressigen Tagen schläfst du trotzdem gut.",
     "Nach stressigen Tagen ist deine Schlafbewertung schlechter."),
    ("zubettgehen", "schlaf_dauer", 0, "Zubettgehen und Schlafdauer",
     "Wenn du später ins Bett gehst, schläfst du trotzdem länger.",
     "Je später du ins Bett gehst, desto kürzer schläfst du."),
    ("zubettgehen", "schlaf_bewertung", 0, "Zubettgehen und Schlafqualität",
     "Spätere Nächte haben bei dir eher bessere Bewertungen.",
     "Je später du ins Bett gehst, desto schlechter ist die Schlafbewertung."),
    ("schlaf_dauer", "bp_sys", 0, "Schlaf und Blutdruck",
     "Nach längeren Nächten ist dein Blutdruck am Morgen eher höher.",
     "Nach längeren Nächten ist dein Blutdruck niedriger."),
    ("steps", "resting_hr", 0, "Bewegung und Ruhepuls",
     "An Tagen mit vielen Schritten ist der Ruhepuls eher höher.",
     "An Tagen mit vielen Schritten ist der Ruhepuls niedriger."),
]


def insights(db, pid: int, end: date, days: int = 180, minimum: float = 0.25) -> list[dict]:
    start = end - timedelta(days=days - 1)
    found = []
    seen_titles = set()
    for xkey, ykey, lag, title, positive, negative in PRESETS:
        if title in seen_titles:
            continue
        rel = relationship(db, pid, xkey, ykey, start, end, lag)
        if rel["n"] < 20 or rel["r"] is None or abs(rel["r"]) < minimum:
            continue
        seen_titles.add(title)
        found.append({**rel, "title": title, "sentence": positive if rel["r"] > 0 else negative,
                      "xkey": xkey, "ykey": ykey})
    return sorted(found, key=lambda f: -abs(f["r"]))


# ---------- Persons ----------

def compare_persons(db, people: list[dict], key: str, start: date, end: date) -> list[dict]:
    meta = KEYS[key]
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    rows = []
    for person in people:
        points = series(db, person["id"], key, start, end)
        prev = series(db, person["id"], key, prev_start, prev_end)
        summary = _period_summary(points, meta, days)
        prev_summary = _period_summary(prev, meta, days)
        goal = person.get(meta.goal_field) if meta.goal_field else None
        if goal and key == "schlaf_dauer":
            goal = goal / 60
        rows.append({"person": person, "points": points, "summary": summary,
                     "change": change(summary["avg"], prev_summary["avg"]),
                     "trend": bewertung.trend_class(change(summary["avg"], prev_summary["avg"]),
                                                    meta.good),
                     "goal": goal,
                     "goal_share": summary["avg"] / goal * 100 if goal and summary["avg"] else None,
                     "goal_days": sum(1 for p in points if goal and p["value"] >= goal)})
    return rows


def ranking(rows: list[dict], meta: Key) -> list[dict]:
    """Persons with values, best first (sum per period for sums, else the average)."""
    measure = "total" if meta.agg == "sum" else "avg"
    ranked = [r for r in rows if r["summary"][measure] is not None]
    reverse = meta.good != "down"
    ranked.sort(key=lambda r: r["summary"][measure], reverse=reverse)
    best = ranked[0]["summary"][measure] if ranked else None
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
        r["measure"] = r["summary"][measure]
        r["bar"] = (r["measure"] / best * 100) if best and reverse else (
            best / r["measure"] * 100 if r["measure"] else 0)
    return ranked


RADAR_AXES = [("steps", "Schritte"), ("active_min", "Minuten"),
              ("active_kcal", "Kalorien"), ("schlaf_dauer", "Schlaf"), ("training", "Trainings")]


def radar_values(db, person: dict, start: date, end: date) -> list[float | None]:
    days = (end - start).days + 1
    values = []
    for key, _label in RADAR_AXES:
        if key == "training":
            count = len(store.workouts(db, person["id"], start, end))
            goal = person["goal_workouts"]
            values.append(count / (days / 7) / goal if goal else None)
            continue
        points = series(db, person["id"], key, start, end)
        avg = sum(p["value"] for p in points) / len(points) if points else None
        goal = person.get(KEYS[key].goal_field)
        if key == "schlaf_dauer" and goal:
            goal = goal / 60
        values.append(avg / goal if avg is not None and goal else None)
    return values


# ---------- Reports ----------

def report_period(kind: str, anchor: date) -> tuple[date, date, date, date]:
    """(start, end, previous start, previous end) for a week (Mon–Sun) or month."""
    if kind == "monat":
        start = anchor.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
    else:
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)
    return start, end, prev_start, prev_end


def report(db, person: dict, kind: str, anchor: date) -> dict:
    pid = person["id"]
    start, end, prev_start, prev_end = report_period(kind, anchor)
    days = (end - start).days + 1

    def block(key):
        cur = series(db, pid, key, start, end)
        prev = series(db, pid, key, prev_start, prev_end)
        meta = KEYS[key]
        c, p = _period_summary(cur, meta, days), _period_summary(prev, meta, days)
        return {"key": key, "meta": meta, "cur": c, "prev": p, "points": cur,
                "change": change(c["avg"], p["avg"]),
                "trend": bewertung.trend_class(change(c["avg"], p["avg"]), meta.good)}

    figures = [block(k) for k in ("steps", "active_min", "active_kcal", "schlaf_dauer",
                                  "schlaf_bewertung", "resting_hr", "hrv_rmssd", "hrv_sdnn",
                                  "weight", "fat_ratio")]
    figures = [f for f in figures if f["cur"]["count"]]
    weight = series(db, pid, "weight", start, end)
    readings = [r for r in store.readings(db, pid, ("bp_sys", "bp_dia", "pulse"), start, end)
                if "bp_sys" in r["values"] and "bp_dia" in r["values"]]
    protocol: dict[str, dict] = {}
    for r in sorted(readings, key=lambda r: r["measured_at"]):
        hour = int(r["measured_at"][11:13])
        slot = "morgens" if hour < 12 else "abends" if hour >= 17 else "mittags"
        protocol.setdefault(r["day"], {"morgens": [], "mittags": [], "abends": []})[slot].append(r)

    def bp_avg(items):
        if not items:
            return None
        s = sum(i["values"]["bp_sys"] for i in items) / len(items)
        d = sum(i["values"]["bp_dia"] for i in items) / len(items)
        return {"sys": s, "dia": d, "count": len(items), "category": bewertung.bp_category(s, d),
                "raised": bewertung.home_bp_raised(s, d)}

    morning = [r for r in readings if int(r["measured_at"][11:13]) < 12]
    evening = [r for r in readings if int(r["measured_at"][11:13]) >= 17]
    workouts = store.workouts(db, pid, start, end)
    nights = store.sleep_series(db, pid, start, end)
    steps = series(db, pid, "steps", start, end)
    return {
        "kind": kind, "start": start, "end": end, "prev_start": prev_start, "prev_end": prev_end,
        "days": days, "figures": figures, "weight": weight,
        "weight_change": (weight[-1]["value"] - weight[0]["value"]) if len(weight) > 1 else None,
        "bp": {"all": bp_avg(readings), "morning": bp_avg(morning), "evening": bp_avg(evening)},
        "protocol": sorted(protocol.items()), "workouts": workouts,
        "workout_minutes": sum(w["duration_min"] or 0 for w in workouts),
        "nights": nights, "steps": steps,
        "goal_days": sum(1 for p in steps if p["value"] >= person["goal_steps"]),
        "best_steps": max(steps, key=lambda p: p["value"]) if steps else None,
    }
