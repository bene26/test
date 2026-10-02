"""Goal forecasts: how likely a goal is reached, with the way the number comes about.

Two kinds, both a normal distribution around a simple projection:
- weight by the goal date (or in eight weeks): the trend of the last 60 days carried forward;
  the spread grows with the noise around the trend, the uncertainty of the trend itself and a
  little room for changed habits (0.25 kg per week, growing with the square root of time);
- steps this month: what is done plus the usual day for every day left, spread by the usual
  day-to-day variation.
The page recomputes the chance in the browser when the slider moves (same formula).
"""

import calendar
import math
import statistics
from datetime import timedelta

from markupsafe import Markup, escape

from . import auswertung, store, util

HABIT_DRIFT_KG_PER_WEEK = 0.25
BELL_W, BELL_H = 300, 120


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def chance(mean: float, sd: float, goal: float, direction: str) -> float:
    """Probability (0..1) to end at or below the goal ("down") or at or above it ("up")."""
    if sd <= 0:
        return 1.0 if (mean <= goal if direction == "down" else mean >= goal) else 0.0
    z = (goal - mean) / sd
    return normal_cdf(z) if direction == "down" else 1 - normal_cdf(z)


def bell(mean: float, sd: float, goal: float, direction: str, lo: float, hi: float) -> Markup:
    """The distribution as an SVG curve with the goal side filled (redrawn by the page)."""
    def x(v):
        return (v - lo) / (hi - lo) * BELL_W

    def pdf(v):
        return math.exp(-0.5 * ((v - mean) / sd) ** 2)

    steps = 80
    points = [(lo + (hi - lo) * i / steps) for i in range(steps + 1)]
    curve = " L".join(f"{x(v):.1f} {BELL_H - pdf(v) * (BELL_H - 8):.1f}" for v in points)
    g = min(max(goal, lo), hi)
    if direction == "down":
        edge = [v for v in points if v < g] + [g]
    else:
        edge = [g] + [v for v in points if v > g]
    area = ("M" + f"{x(edge[0]):.1f} {BELL_H} L"
            + " L".join(f"{x(v):.1f} {BELL_H - pdf(v) * (BELL_H - 8):.1f}" for v in edge)
            + f" L{x(edge[-1]):.1f} {BELL_H} Z")
    gx = x(g)
    return Markup(
        f'<svg class="glocke" viewBox="0 0 {BELL_W} {BELL_H}" preserveAspectRatio="none" '
        f'aria-hidden="true" focusable="false">'
        f'<path class="glocke-flaeche" data-glocke-flaeche d="{area}"/>'
        f'<path class="glocke-linie" d="M{curve}" vector-effect="non-scaling-stroke"/>'
        f'<path class="glocke-ziel" data-glocke-ziel d="M{gx:.1f} 0 V{BELL_H}" '
        f'vector-effect="non-scaling-stroke"/></svg>')


def verdict(probability: float) -> str:
    return ("unwahrscheinlich" if probability < 20 else "eher nicht" if probability < 45 else
            "gut möglich" if probability < 70 else "sehr wahrscheinlich")


def _result(kind, title, question, mean, sd, goal, direction, unit, decimals, step, parts,
            note, need) -> dict:
    """need: (base, span, unit, decimals, label): what it takes per time unit, recomputed in
    the browser as (goal - base) / span."""
    lo, hi = mean - 3.2 * sd, mean + 3.2 * sd
    lo, hi = min(lo, goal - sd * 0.5), max(hi, goal + sd * 0.5)
    # slider ends on whole steps, so the browser does not shift the goal
    lo, hi = math.floor(lo / step) * step, math.ceil(hi / step) * step
    p = chance(mean, sd, goal, direction)
    base, span, need_unit, need_decimals, need_label = need
    return {
        "kind": kind, "title": title, "question": question, "probability": round(p * 100),
        "verdict": verdict(p * 100),
        "need": {"base": base, "span": span, "unit": need_unit, "decimals": need_decimals,
                 "label": need_label, "value": (goal - base) / span},
        "mean": mean, "sd": sd, "goal": goal, "direction": direction, "unit": unit,
        "decimals": decimals, "step": step, "lo": lo, "hi": hi, "parts": parts, "note": note,
        "chart": bell(mean, sd, goal, direction, lo, hi),
        "labels": [util.fmt_num(lo, decimals), util.fmt_num(mean, decimals), util.fmt_num(hi, decimals)],
    }


def weight(db, pid: int, person: dict, today) -> dict | None:
    if not person.get("goal_weight_dg"):
        return None
    today = util.to_date(today)
    points = auswertung.series(db, pid, "weight", today - timedelta(days=59), today)
    if len(points) < 8:
        return None
    goal = person["goal_weight_dg"] / 10
    target = util.to_date(person.get("goal_weight_date")) if person.get("goal_weight_date") else None
    passed = bool(target and target <= today)
    dated = bool(target) and not passed
    if not dated:
        target = today + timedelta(weeks=8)
    first = util.to_date(points[0]["day"])
    xs = [(util.to_date(p["day"]) - first).days for p in points]
    ys = [p["value"] for p in points]
    fit = auswertung.linear_fit(xs, ys)
    if not fit:
        return None
    slope, intercept = fit
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    noise = statistics.stdev(residuals) if len(residuals) > 2 else 0.5
    mx = statistics.mean(xs)
    sxx = sum((x - mx) ** 2 for x in xs) or 1
    slope_error = noise / math.sqrt(sxx)
    now_x = (today - first).days
    days = (target - today).days
    current = slope * now_x + intercept
    mean = current + slope * days
    drift = HABIT_DRIFT_KG_PER_WEEK * math.sqrt(days / 7)
    sd = math.sqrt(noise ** 2 + (slope_error * days) ** 2 + drift ** 2)
    direction = "down" if goal < current else "up"
    when = util.fmt_date(target) if dated else "in acht Wochen"
    parts = [
        ("Trend", f"{util.fmt_signed(slope * 7, 2)} kg pro Woche",
         f"Gerade durch {len(points)} Messungen der letzten 60 Tage"),
        ("Zeit", f"{days} Tage", f"bis {util.fmt_date(target)}" + (
            "" if dated else " (Zieldatum vorbei)" if passed else " (kein Zieldatum eingetragen)")),
        ("Erwartet", f"{util.fmt_num(mean, 1)} kg", f"heute laut Trend {util.fmt_num(current, 1)} kg"),
        ("Unsicherheit", f"± {util.fmt_num(sd, 1)} kg",
         f"Tagesschwankung ±{util.fmt_num(noise, 1)}, Unsicherheit des Trends, Spielraum für geänderte Gewohnheiten"),
    ]
    return _result(
        "gewicht", "Zielgewicht", f"{util.fmt_num(goal, 1)} kg {('bis ' + when) if dated else when}?",
        mean, sd, goal, direction, "kg", 1, 0.1, parts,
        "Gerechnet mit einer Normalverteilung um den fortgeschriebenen Trend.",
        (current, max(days / 7, 0.1), "kg pro Woche", 2, "nötig ab heute"))


def steps_month(db, pid: int, person: dict, today) -> dict | None:
    goal_day = person.get("goal_steps")
    if not goal_day:
        return None
    today = util.to_date(today)
    history = [p["value"] for p in store.daily_series(db, pid, "steps", today - timedelta(days=56),
                                                       today - timedelta(days=1))]
    if len(history) < 14:
        return None
    first = today.replace(day=1)
    length = calendar.monthrange(today.year, today.month)[1]
    done = sum(p["value"] for p in store.daily_series(db, pid, "steps", first, today - timedelta(days=1)))
    left = length - today.day + 1   # today counts as open
    usual = statistics.mean(history)
    spread = statistics.stdev(history)
    mean = done + usual * left
    sd = max(spread * math.sqrt(left), 1.0)
    goal = goal_day * length
    month = util.MONTHS_LONG[today.month - 1]
    parts = [
        ("Geschafft", f"{util.fmt_num(done)}", f"Schritte vom 1. bis gestern"),
        ("Übrig", f"{left} Tage", f"ein üblicher Tag: {util.fmt_num(usual)} Schritte (letzte 8 Wochen)"),
        ("Erwartet", f"{util.fmt_num(mean)}", "Schritte am Monatsende"),
        ("Unsicherheit", f"± {util.fmt_num(sd)}",
         f"Tage schwanken um ±{util.fmt_num(spread)}, über {left} Tage wächst das mit der Wurzel"),
    ]
    return _result(
        "schritte", f"Schritte im {month}", f"{util.fmt_num(goal)} Schritte im {month}?",
        mean, sd, goal, "up", "Schritte", 0, max(1000, round(goal / 300, -3)), parts,
        f"Ziel: {util.fmt_num(goal_day)} am Tag × {length} Tage.",
        (done, left, "Schritte am Tag", 0, "nötig ab heute"))


def main(db, pid: int, person: dict, today) -> list[dict]:
    """The forecasts that have enough data: weight first, then steps."""
    return [f for f in (weight(db, pid, person, today), steps_month(db, pid, person, today)) if f]
