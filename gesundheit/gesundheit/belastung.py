"""Training load per day, and fitness, fatigue and form, the way endurance coaches read them.

Load ("Belastung") per day is the training impulse after Banister: minutes x heart rate reserve
x 0.64 x e^(1.92 x heart rate reserve). Trainings without a pulse count as moderate (reserve
0.5), active minutes outside trainings as light (reserve 0.3). Fitness is the 42-day and
fatigue the 7-day exponentially weighted average of the load; form is fitness minus fatigue.
Days without any value count as rest days. Everything here is orientation, not a diagnosis.
"""

import math
import statistics
from datetime import timedelta

from . import persons, store, util

FITNESS_DAYS = 42
FATIGUE_DAYS = 7
MODERATE = 0.5
LIGHT = 0.3
# Form bands (fitness minus fatigue): (lower bound, label, sentence)
STATES = [
    (15, "sehr frisch", "Lange erholt, die Fitness sinkt schon wieder etwas."),
    (5, "frisch", "Gut erholt, bereit für etwas Hartes."),
    (-10, "ausgeglichen", "Belastung und Erholung halten sich die Waage."),
    (-30, "im Aufbau", "Mehr Belastung als Erholung. So wächst die Fitness, wenn Pausen folgen."),
    (-math.inf, "überlastet", "Deutlich mehr Belastung als sonst. Zeit für ruhigere Tage."),
]
SCALE = (-40, 25)   # form range shown on the belastet ... frisch scale


def impulse(minutes, reserve) -> float:
    if not minutes or minutes <= 0:
        return 0.0
    reserve = min(max(reserve, 0.0), 1.0)
    return minutes * reserve * 0.64 * math.exp(1.92 * reserve)


def heart_limits(db, pid: int, person: dict, day) -> tuple[float, float]:
    """(resting, maximum) heart rate: resting from the last 30 days, maximum from the age
    formula or the highest training pulse of the last year, whichever is higher."""
    day = util.to_date(day)
    rest_values = [p["value"] for p in store.daily_series(db, pid, "resting_hr",
                                                          day - timedelta(days=30), day)]
    rest = statistics.median(rest_values) if rest_values else 60.0
    seen = [w["hr_max"] for w in store.workouts(db, pid, day - timedelta(days=365), day)
            if w["hr_max"]]
    age = persons.age(person, day)
    formula = 220 - age if age else None
    observed = max(seen) if seen else None
    if formula and observed:
        maximum = max(formula, observed)
    else:
        maximum = formula or (observed if observed and observed >= 150 else 190)
    return rest, max(maximum, rest + 40)


def daily(db, pid: int, person: dict, start, end) -> dict[str, float]:
    """{day: load} for every day in the period that has activity data or a training."""
    start, end = util.to_date(start), util.to_date(end)
    rest, maximum = heart_limits(db, pid, person, end)
    loads: dict[str, float] = {}
    trained: dict[str, float] = {}
    for w in store.workouts(db, pid, start, end):
        minutes = w["duration_min"] or 0
        if w["hr_avg"]:
            reserve = (w["hr_avg"] - rest) / (maximum - rest)
        else:
            reserve = MODERATE
        loads[w["day"]] = loads.get(w["day"], 0.0) + impulse(minutes, reserve)
        trained[w["day"]] = trained.get(w["day"], 0.0) + minutes
    for p in store.daily_series(db, pid, "active_min", start, end):
        outside = max(0.0, p["value"] - trained.get(p["day"], 0.0))
        loads[p["day"]] = loads.get(p["day"], 0.0) + impulse(outside, LIGHT)
    return {day: round(value, 1) for day, value in sorted(loads.items())}


def state(form_value: float) -> tuple[str, str]:
    for bound, label, sentence in STATES:
        if form_value >= bound:
            return label, sentence
    return STATES[-1][1], STATES[-1][2]  # pragma: no cover


def form(db, pid: int, person: dict, today=None, history: int = 180) -> dict | None:
    """Fitness, fatigue and form on a day, with the course over the last weeks.
    None while there is too little data (fewer than 21 days with values in six weeks)."""
    today = util.to_date(today) or util.today()
    start = today - timedelta(days=history)
    loads = daily(db, pid, person, start, today)
    recent = [d for d in loads if d > (today - timedelta(days=FITNESS_DAYS)).isoformat()]
    if len(recent) < 21:
        return None
    fitness = fatigue = 0.0
    course = []
    for day in util.days(start, today):
        load = loads.get(day.isoformat(), 0.0)
        fitness += (load - fitness) / FITNESS_DAYS
        fatigue += (load - fatigue) / FATIGUE_DAYS
        course.append({"day": day.isoformat(), "fitness": fitness, "fatigue": fatigue,
                       "form": fitness - fatigue, "load": load})
    value = fitness - fatigue
    label, sentence = state(value)
    lo, hi = SCALE
    week_ago = course[-8] if len(course) >= 8 else course[0]
    return {
        "fitness": round(fitness), "fatigue": round(fatigue), "form": round(value),
        "label": label, "sentence": sentence,
        "position": round(min(max((value - lo) / (hi - lo), 0.0), 1.0) * 100),
        "week_change": round(value - week_ago["form"]),
        "course": course[-56:],
    }
