"""The four topic pages: body, heart and circulation, sleep, activity."""

from datetime import timedelta

from flask import Blueprint, g, render_template

from .. import bewertung, charts, messungen, store, util
from ..db import get_db
from ..katalog import EKG_LABELS, METRICS, WORKOUT_KINDS
from . import PERIODS, period
from .main import tile

bp = Blueprint("bereiche", __name__)


def metric_chart(db, pid, metric, start, end, **kwargs):
    meta = METRICS[metric]
    series = store.daily_series(db, pid, metric, start, end)
    if meta.chart == "bar":
        chart = charts.bars(series, start, end, meta.unit, meta.decimals, meta.label, **kwargs)
    else:
        chart = charts.line(series, start, end, meta.unit, meta.decimals, meta.label,
                            limits=(meta.lo, meta.hi), **kwargs)
    return {"meta": meta, "series": series, "summary": store.summary([p["value"] for p in series]),
            "chart": chart}


def height_cm(db, person):
    if person["height_cm"]:
        return person["height_cm"]
    measured = store.latest(db, person["id"], "height")
    return measured["value"] if measured else None


@bp.route("/koerper")
def koerper():
    db = get_db()
    pid = g.person["id"]
    days, start, end = period()
    today = util.today()
    height = height_cm(db, g.person)
    band = None
    if height:
        meters = height / 100
        band = (18.5 * meters * meters, 24.9 * meters * meters, "Normalgewicht laut BMI")
    goal_dg = g.person["goal_weight_dg"]
    weight = metric_chart(db, pid, "weight", start, end, band=band,
                          goal=goal_dg / 10 if goal_dg else None)
    latest_weight = store.latest(db, pid, "weight")
    bmi = bewertung.bmi(latest_weight["value"] if latest_weight else None, height)
    composition = [t for t in (tile(db, pid, m, today) for m in (
        "fat_ratio", "muscle_mass", "hydration", "bone_mass", "fat_mass", "fat_free_mass",
        "visceral_fat", "bmr")) if t]
    fat = metric_chart(db, pid, "fat_ratio", start, end)
    weighings = store.readings(db, pid, ("weight", "fat_ratio", "muscle_mass", "hydration",
                                    "bone_mass"), start, end)[:40]
    return render_template(
        "koerper.html", days=days, periods=PERIODS, weight=weight, latest_weight=latest_weight,
        circumferences=messungen.circumferences(db, pid, today, max(days, 365)),
        practice=messungen.practice(db, pid, today),
        weight_tile=tile(db, pid, "weight", today), bmi=bmi,
        bmi_category=bewertung.bmi_category(bmi) if bmi else None, height=height,
        composition=composition, fat=fat, weighings=weighings)


@bp.route("/herz")
def herz():
    db = get_db()
    pid = g.person["id"]
    days, start, end = period()
    today = util.today()
    readings = store.readings(db, pid, ("bp_sys", "bp_dia", "pulse"), start, end)
    complete = [r for r in readings if "bp_sys" in r["values"] and "bp_dia" in r["values"]]
    by_day: dict[str, list] = {}
    for r in complete:
        by_day.setdefault(r["day"], []).append(r)
    bp_days = [{"day": day, "source": rows[0]["source"],
                "sys": sum(r["values"]["bp_sys"] for r in rows) / len(rows),
                "dia": sum(r["values"]["bp_dia"] for r in rows) / len(rows)}
               for day, rows in sorted(by_day.items())]
    week = [r for r in complete if util.to_date(r["day"]) > today - timedelta(days=7)]
    bp_week = None
    if week:
        sys_avg = sum(r["values"]["bp_sys"] for r in week) / len(week)
        dia_avg = sum(r["values"]["bp_dia"] for r in week) / len(week)
        bp_week = {"sys": sys_avg, "dia": dia_avg, "count": len(week),
                   "category": bewertung.bp_category(sys_avg, dia_avg),
                   "raised": bewertung.home_bp_raised(sys_avg, dia_avg)}
    for r in complete:
        r["category"] = bewertung.bp_category(r["values"]["bp_sys"], r["values"]["bp_dia"])
    hrv_metric = "hrv_rmssd" if store.latest(db, pid, "hrv_rmssd") else "hrv_sdnn"
    charts_more = [metric_chart(db, pid, m, start, end) for m in ("resting_hr", hrv_metric, "spo2")]
    extra = [t for t in (tile(db, pid, m, today) for m in ("pwv", "temperature", "resp_rate",
                                                       "hr_min", "hr_max")) if t]
    ecg = store.readings(db, pid, ("ekg_afib", "ekg_puls"), today - timedelta(days=365), today)[:20]
    return render_template(
        "herz.html", days=days, periods=PERIODS,
        bp_chart=charts.blood_pressure(bp_days, start, end, bewertung.bp_category),
        bp_week=bp_week, bp_readings=complete[:30], bp_levels=bewertung.BP_LEVELS,
        bp_note=bewertung.BP_NOTE, charts_more=charts_more, extra=extra, ecg=ecg,
        ekg_labels=EKG_LABELS)


@bp.route("/schlaf")
def schlaf():
    db = get_db()
    pid = g.person["id"]
    days, start, end = period()
    goal = g.person["goal_sleep_min"]
    nights = store.sleep_series(db, pid, start, end)
    last = store.sleep_series(db, pid, util.today() - timedelta(days=2), util.today())
    last = last[-1] if last else None
    asleep = [n["asleep_min"] for n in nights if n["asleep_min"]]
    staged = [n for n in nights if n["deep_min"] is not None and n["asleep_min"]]

    def clock_avg(key, shift):
        """Average clock time; shift moves evening times past midnight for bedtimes."""
        minutes = []
        for n in nights:
            dt = util.to_datetime(n[key])
            if dt:
                value = dt.hour * 60 + dt.minute
                minutes.append(value + 1440 if shift and value < 12 * 60 else value)
        if not minutes:
            return None
        avg = round(sum(minutes) / len(minutes)) % 1440
        return f"{avg // 60:02d}:{avg % 60:02d}"

    stats = {
        "avg": sum(asleep) / len(asleep) if asleep else None,
        "goal_nights": sum(1 for v in asleep if goal and v >= goal),
        "nights": len(asleep),
        "bed": clock_avg("bed_start", True),
        "wake": clock_avg("bed_end", False),
        "deep_pct": (sum(n["deep_min"] for n in staged) / sum(n["asleep_min"] for n in staged)
                     * 100) if staged else None,
        "rem_pct": (sum(n["rem_min"] or 0 for n in staged) / sum(n["asleep_min"] for n in staged)
                    * 100) if staged else None,
        "score": (sum(n["score"] for n in nights if n["score"]) /
                  max(1, sum(1 for n in nights if n["score"]))) if any(
                      n["score"] for n in nights) else None,
    }
    stages = None
    if last and last["deep_min"] is not None:
        total = sum(last[k] or 0 for k in ("deep_min", "light_min", "rem_min", "awake_min")) or 1
        stages = [(key, label, last[col], (last[col] or 0) / total * 100)
                  for key, label, col in (("tief", "Tief", "deep_min"),
                                          ("leicht", "Leicht", "light_min"),
                                          ("rem", "REM", "rem_min"), ("wach", "Wach", "awake_min"))]
    return render_template(
        "schlaf.html", days=days, periods=PERIODS, last=last, stages=stages, goal=goal,
        chart=charts.sleep(nights, start, end, goal), stats=stats,
        nights=list(reversed(nights))[:60])


@bp.route("/aktivitaet")
def aktivitaet():
    db = get_db()
    pid = g.person["id"]
    days, start, end = period()
    goals = g.person
    steps = metric_chart(db, pid, "steps", start, end, goal=goals["goal_steps"])
    minutes = metric_chart(db, pid, "active_min", start, end, goal=goals["goal_active_min"])
    totals = {m: store.summary([p["value"] for p in store.daily_series(db, pid, m, start, end)])
              for m in ("active_kcal", "distance_km", "floors")}
    workouts = store.workouts(db, pid, start, end)
    by_kind: dict[str, dict] = {}
    for w in workouts:
        entry = by_kind.setdefault(w["kind"], {"count": 0, "minutes": 0.0, "km": 0.0})
        entry["count"] += 1
        entry["minutes"] += w["duration_min"] or 0
        entry["km"] += w["distance_km"] or 0
    garmin_charts = [c for c in (metric_chart(db, pid, m, start, end) for m in
                                 ("body_battery_max", "stress_avg", "readiness", "vo2max"))
                     if c["series"]]
    return render_template(
        "aktivitaet.html", days=days, periods=PERIODS, steps=steps, minutes=minutes,
        totals=totals, workouts=workouts[:50], by_kind=sorted(
            by_kind.items(), key=lambda kv: kv[1]["count"], reverse=True),
        kinds=WORKOUT_KINDS, garmin_charts=garmin_charts, goals=goals)
