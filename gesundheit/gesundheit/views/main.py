"""Overview, history of a single value, search for the card file, health check."""

from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from .. import befunde, belastung, bewertung, charts, jobs, store, uebersicht, util
from ..db import get_db
from ..katalog import METRICS, NO_CHART
from . import PERIODS, period

bp = Blueprint("main", __name__)


def tile(db, pid: int, metric: str, today, compare_days: int = 30) -> dict | None:
    """Latest value with change against about `compare_days` ago and a small trend line."""
    meta = METRICS[metric]
    current = store.latest(db, pid, metric)
    if not current:
        return None
    day = util.to_date(current["day"])
    before = store.latest(db, pid, metric, until=day - timedelta(days=compare_days))
    change = current["value"] - before["value"] if before else None
    history = store.daily_series(db, pid, metric, today - timedelta(days=29), today)
    return {
        "metric": metric, "label": meta.label, "unit": meta.unit, "decimals": meta.decimals,
        "value": current["value"], "day": current["day"], "source": current["source"],
        "change": change, "trend": bewertung.trend_class(change, meta.good),
        "stale": (today - day).days > 7,
        "spark": charts.spark_area([p["value"] for p in history]),
        "url": url_for("main.history", metric=metric),
    }


def today_value(db, pid: int, metric: str, today):
    series = store.daily_series(db, pid, metric, today, today)
    return series[-1]["value"] if series else None


def has_any_data(db, pid: int) -> bool:
    return any(db.execute(f"SELECT 1 FROM {t} WHERE person_id = ? LIMIT 1", (pid,)).fetchone()
               for t in store.HEALTH_TABLES)


@bp.route("/")
def index():
    db = get_db()
    person = g.person
    pid = person["id"]
    today = util.today()
    last_night = store.sleep_series(db, pid, today - timedelta(days=1), today)
    night = last_night[-1] if last_night else None
    activity = [
        {"key": "kalorien", "label": "Bewegen", "value": today_value(db, pid, "active_kcal", today),
         "goal": person["goal_active_kcal"], "unit": "kcal", "metric": "active_kcal"},
        {"key": "minuten", "label": "Aktive Minuten",
         "value": today_value(db, pid, "active_min", today),
         "goal": person["goal_active_min"], "unit": "min", "metric": "active_min"},
        {"key": "schritte", "label": "Schritte", "value": today_value(db, pid, "steps", today),
         "goal": person["goal_steps"], "unit": "", "metric": "steps"},
    ]
    for ring in activity:
        ring["percent"] = (round(ring["value"] / ring["goal"] * 100)
                           if ring["value"] is not None and ring["goal"] else None)
        ring["url"] = url_for("main.history", metric=ring["metric"])

    hrv = "hrv_rmssd" if store.latest(db, pid, "hrv_rmssd") else "hrv_sdnn"
    tiles = [t for t in (tile(db, pid, m, today) for m in
                         ("weight", "fat_ratio", "resting_hr", hrv, "spo2", "vo2max")) if t]
    gauges = []
    if night and night["score"]:
        gauges.append(charts.gauge(night["score"], 100, "Schlafbewertung", levels=(60, 80)))
    for metric, label in (("body_battery_max", "Body Battery"),
                          ("readiness", "Trainingsbereitschaft")):
        value = today_value(db, pid, metric, today)
        if value is None:
            value = today_value(db, pid, metric, today - timedelta(days=1))
        if value is not None:
            gauges.append(charts.gauge(round(value), 100, label, levels=(35, 65)))

    bp_readings = store.readings(db, pid, ("bp_sys", "bp_dia", "pulse"),
                                 today - timedelta(days=90), today)
    bp_last = next((r for r in bp_readings if "bp_sys" in r["values"] and "bp_dia" in r["values"]),
                   None)
    bp_info = None
    if bp_last:
        sys_v, dia_v = bp_last["values"]["bp_sys"], bp_last["values"]["bp_dia"]
        bp_info = {"reading": bp_last, "category": bewertung.bp_category(sys_v, dia_v)}

    sleep_donut = None
    if night and night["deep_min"] is not None:
        hours, minutes = divmod(int(round(night["asleep_min"] or 0)), 60)
        sleep_donut = charts.donut(
            [("tief", "Tief", night["deep_min"]), ("leicht", "Leicht", night["light_min"]),
             ("rem", "REM", night["rem_min"]), ("wach", "Wach", night["awake_min"])],
            f"{hours}:{minutes:02d}", "Stunden")

    week_start = today - timedelta(days=6)
    week_steps = store.daily_series(db, pid, "steps", week_start, today)
    week_sleep = store.sleep_series(db, pid, week_start, today)
    week = {
        "steps": charts.bars(week_steps, week_start, today, "", 0, "Schritte der letzten 7 Tage",
                             goal=person["goal_steps"]),
        "steps_avg": store.summary([p["value"] for p in week_steps])["avg"],
        "sleep_avg": store.summary([n["asleep_min"] for n in week_sleep
                                    if n["asleep_min"]])["avg"],
        "workouts": store.workouts(db, pid, week_start, today),
    }
    connections = {row["provider"]: row for row in db.execute(
        "SELECT provider, last_sync, last_ok, last_error FROM connections WHERE person_id = ?",
        (pid,))}
    last_import = db.execute("SELECT * FROM imports WHERE person_id = ? ORDER BY id DESC LIMIT 1",
                             (pid,)).fetchone()
    findings = befunde.compute(db, pid, person, today)
    return render_template(
        "index.html", now=util.now(),
        sky=uebersicht.skyline(db, pid, person, today, request.args.get("zeit")),
        findings=findings, news=befunde.news(findings, person),
        form=belastung.form(db, pid, person, today),
        activity=activity, rings_svg=charts.rings(activity),
        tiles=tiles, gauges=gauges, bp_info=bp_info, night=night, sleep_donut=sleep_donut,
        week=week, connections=connections, last_import=last_import,
        empty=not has_any_data(db, pid),
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
    pid = g.person["id"]
    days, start, end = period()
    series = store.daily_series(db, pid, metric, start, end)
    stats = store.summary([p["value"] for p in series])
    goal = {"steps": g.person["goal_steps"], "active_min": g.person["goal_active_min"],
            "active_kcal": g.person["goal_active_kcal"]}.get(metric)
    if metric == "weight" and g.person["goal_weight_dg"]:
        goal = g.person["goal_weight_dg"] / 10
    if meta.chart == "bar":
        chart = charts.bars(series, start, end, meta.unit, meta.decimals, meta.label, goal=goal)
    else:
        chart = charts.line(series, start, end, meta.unit, meta.decimals, meta.label, goal=goal,
                            limits=(meta.lo, meta.hi))
    per_source = store.per_source(db, pid, metric, start, end)
    order = store.priority(db, meta.family)
    sources_seen = sorted({s for by in per_source.values() for s in by}, key=order.index)
    return render_template(
        "verlauf.html", meta=meta, chart=chart, stats=stats, days=days, periods=PERIODS,
        rows=list(reversed(series))[:120], per_source=per_source, sources_seen=sources_seen,
        latest=store.latest(db, pid, metric), goal=goal)


# Pages and values for the card file (Strg+K), see komponenten.js.
PAGES = [
    ("main.index", "Übersicht", "Heute, Ringe, Kennzahlen"),
    ("bereiche.koerper", "Körper", "Gewicht, Fett, Muskeln, BMI"),
    ("bereiche.herz", "Herz und Kreislauf", "Blutdruck, Ruhepuls, HRV, EKG"),
    ("bereiche.schlaf", "Schlaf", "Dauer, Phasen, Bewertung"),
    ("bereiche.aktivitaet", "Aktivität", "Schritte, Trainings, Body Battery"),
    ("auswertungen.index", "Auswertungen", "Zeiträume, Bestwerte, Wochentage, Kalender"),
    ("auswertungen.zusammenhaenge", "Zusammenhänge", "Schlaf, Puls, Bewegung im Vergleich"),
    ("vergleich.index", "Personen vergleichen", "Nebeneinander, Rangliste, Ziele"),
    ("berichte.index", "Berichte", "Woche und Monat, Blutdruck-Protokoll"),
    ("personen.index", "Personen", "Profile anlegen und bearbeiten"),
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
        for person in g.persons:
            if query in _fold(person["name"]):
                hits.append({"titel": person["name"], "gruppe": "Personen",
                             "hinweis": "Profil bearbeiten",
                             "url": url_for("personen.edit", person_id=person["id"])})
    return jsonify({"treffer": hits[:12]})


@bp.route("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return {"status": "ok"}
