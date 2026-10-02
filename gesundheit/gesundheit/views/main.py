"""Overview, history of a single value, search for the card file, health check."""

from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from .. import bewertung, charts, jobs, settings, store, util
from ..db import get_db
from ..katalog import METRICS, NO_CHART
from . import PERIODS, period

bp = Blueprint("main", __name__)


def tile(db, metric: str, today, compare_days: int = 30) -> dict | None:
    """Latest value with change against about `compare_days` ago and a small trend line."""
    meta = METRICS[metric]
    current = store.latest(db, metric)
    if not current:
        return None
    day = util.to_date(current["day"])
    before = store.latest(db, metric, until=day - timedelta(days=compare_days))
    change = current["value"] - before["value"] if before else None
    history = store.daily_series(db, metric, today - timedelta(days=29), today)
    return {
        "metric": metric, "label": meta.label, "unit": meta.unit, "decimals": meta.decimals,
        "value": current["value"], "day": current["day"], "source": current["source"],
        "change": change, "trend": bewertung.trend_class(change, meta.good),
        "stale": (today - day).days > 7,
        "spark": charts.spark([p["value"] for p in history]),
        "url": url_for("main.history", metric=metric),
    }


def today_value(db, metric: str, today):
    series = store.daily_series(db, metric, today, today)
    return series[-1]["value"] if series else None


def has_any_data(db) -> bool:
    return any(db.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in store.HEALTH_TABLES)


@bp.route("/")
def index():
    db = get_db()
    today = util.today()
    goals = settings.get_all(db)
    last_night = store.sleep_series(db, today - timedelta(days=1), today)
    night = last_night[-1] if last_night else None
    rings = [
        {"key": "schritte", "label": "Schritte", "value": today_value(db, "steps", today),
         "goal": goals["goal_steps"], "decimals": 0, "unit": "",
         "url": url_for("main.history", metric="steps")},
        {"key": "minuten", "label": "Aktive Minuten", "value": today_value(db, "active_min", today),
         "goal": goals["goal_active_min"], "decimals": 0, "unit": "min",
         "url": url_for("main.history", metric="active_min")},
        {"key": "kalorien", "label": "Aktivkalorien",
         "value": today_value(db, "active_kcal", today), "goal": goals["goal_active_kcal"],
         "decimals": 0, "unit": "kcal", "url": url_for("main.history", metric="active_kcal")},
        {"key": "schlaf", "label": "Schlaf letzte Nacht",
         "value": night["asleep_min"] if night else None, "goal": goals["goal_sleep_min"],
         "decimals": 0, "unit": "min", "url": url_for("bereiche.schlaf"), "dauer": True},
    ]
    for ring in rings:
        ring["svg"] = charts.ring(ring["value"], ring["goal"], ring["key"])
        ring["percent"] = (round(ring["value"] / ring["goal"] * 100)
                           if ring["value"] is not None and ring["goal"] else None)

    hrv = "hrv_rmssd" if store.latest(db, "hrv_rmssd") else "hrv_sdnn"
    tiles = [t for t in (tile(db, m, today) for m in
                         ("weight", "resting_hr", hrv, "spo2", "body_battery_max", "vo2max"))
             if t]
    bp_readings = store.readings(db, ("bp_sys", "bp_dia", "pulse"), today - timedelta(days=90),
                                 today)
    bp_last = next((r for r in bp_readings if "bp_sys" in r["values"] and "bp_dia" in r["values"]),
                   None)
    bp_info = None
    if bp_last:
        sys_v, dia_v = bp_last["values"]["bp_sys"], bp_last["values"]["bp_dia"]
        bp_info = {"reading": bp_last, "category": bewertung.bp_category(sys_v, dia_v)}

    week_start = today - timedelta(days=6)
    week_steps = store.daily_series(db, "steps", week_start, today)
    week_sleep = store.sleep_series(db, week_start, today)
    week = {
        "steps": charts.bars(week_steps, week_start, today, "", 0, "Schritte der letzten 7 Tage",
                             goal=goals["goal_steps"]),
        "steps_avg": store.summary([p["value"] for p in week_steps])["avg"],
        "sleep_avg": store.summary([n["asleep_min"] for n in week_sleep
                                    if n["asleep_min"]])["avg"],
        "workouts": store.workouts(db, week_start, today),
    }
    connections = {row["provider"]: row for row in
                   db.execute("SELECT provider, last_sync, last_ok, last_error FROM connections")}
    imports = db.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 1").fetchone()
    return render_template(
        "index.html", now=util.now(), rings=rings, tiles=tiles, bp_info=bp_info, night=night,
        week=week, connections=connections, last_import=imports, empty=not has_any_data(db),
        syncing=jobs.busy("withings") or jobs.busy("garmin") or jobs.busy("apple"))


@bp.route("/abgleichen", methods=["POST"])
def sync_now():
    jobs.sync_all(current_app._get_current_object())
    flash("Abgleich gestartet. Neue Werte erscheinen in ein bis zwei Minuten.", "ok")
    return redirect(url_for("main.index"))


@bp.route("/verlauf/<metric>")
def history(metric):
    if metric not in METRICS or metric in NO_CHART:
        abort(404)
    meta = METRICS[metric]
    db = get_db()
    days, start, end = period()
    series = store.daily_series(db, metric, start, end)
    stats = store.summary([p["value"] for p in series])
    goal = None
    goals = settings.get_all(db)
    if metric == "steps":
        goal = goals["goal_steps"]
    elif metric == "active_min":
        goal = goals["goal_active_min"]
    elif metric == "active_kcal":
        goal = goals["goal_active_kcal"]
    elif metric == "weight" and goals["goal_weight_dg"]:
        goal = goals["goal_weight_dg"] / 10
    if meta.chart == "bar":
        chart = charts.bars(series, start, end, meta.unit, meta.decimals, meta.label, goal=goal)
    else:
        chart = charts.line(series, start, end, meta.unit, meta.decimals, meta.label, goal=goal,
                            limits=(meta.lo, meta.hi))
    per_source = store.per_source(db, metric, start, end)
    sources_seen = sorted({s for by in per_source.values() for s in by},
                          key=store.priority(db, meta.family).index)
    return render_template(
        "verlauf.html", meta=meta, chart=chart, stats=stats, days=days, periods=PERIODS,
        rows=list(reversed(series))[:120], per_source=per_source, sources_seen=sources_seen,
        latest=store.latest(db, metric), goal=goal)


# Pages and values for the card file (Strg+K), see komponenten.js.
PAGES = [
    ("main.index", "Übersicht", "Heute, Ringe, Kennzahlen"),
    ("bereiche.koerper", "Körper", "Gewicht, Fett, Muskeln, BMI"),
    ("bereiche.herz", "Herz und Kreislauf", "Blutdruck, Ruhepuls, HRV, EKG"),
    ("bereiche.schlaf", "Schlaf", "Dauer, Phasen, Bewertung"),
    ("bereiche.aktivitaet", "Aktivität", "Schritte, Trainings, Body Battery"),
    ("quellen.index", "Quellen", "Withings, Garmin, Apple Health"),
    ("einstellungen.index", "Einstellungen", "Darstellung, Ziele, Passwort"),
    ("daten.index", "Daten", "Export und Löschen"),
]


def _fold(text: str) -> str:
    return (text.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u")
            .replace("ß", "ss"))


@bp.route("/suche.json")
def search():
    query = _fold(request.args.get("q", "")[:100].strip())
    hits = []
    if len(query) >= 2:
        for endpoint, title, hint in PAGES:
            if query in _fold(title) or query in _fold(hint):
                hits.append({"titel": title, "gruppe": "Seiten", "hinweis": hint,
                             "url": url_for(endpoint)})
        for key, meta in METRICS.items():
            if key not in NO_CHART and query in _fold(meta.label):
                hits.append({"titel": meta.label, "gruppe": "Werte",
                             "hinweis": f"Verlauf{' in ' + meta.unit if meta.unit else ''}",
                             "url": url_for("main.history", metric=key)})
    return jsonify({"treffer": hits[:12]})


@bp.route("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return {"status": "ok"}
