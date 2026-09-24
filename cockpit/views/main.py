"""Start page, routine check-off and health check."""

import re
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, url_for

from .. import data, util
from ..db import get_db

bp = Blueprint("main", __name__)


@bp.route("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return "ok", 200, {"Content-Type": "text/plain"}


@bp.route("/")
def dashboard():
    db = get_db()
    now = util.now()
    today = now.date()
    settings = data.settings(db)
    stale_days = int(settings["stale_days"])
    week_end = util.week_start(today) + timedelta(days=6)
    next_day = util.next_workday(today)

    overdue = data.find_tasks(db, today, preset="ueberfaellig", limit=20)
    due_week = data.find_tasks(db, today, preset="woche", limit=20)
    workload = data.workload(db, today, weeks=2)
    overbooked = [
        {"name": p["name"], "week": w["label"], "percent": c["percent"]}
        for p in workload["people"]
        for w, c in zip(workload["weeks"], p["cells"])
        if c["level"] == "ueber"
    ]
    return render_template(
        "dashboard.html",
        now=now,
        week=util.week_number(today),
        counts=data.counts(db, now, stale_days),
        stale_days=stale_days,
        routines=data.due_routines(db, today),
        overdue=overdue,
        due_week=due_week,
        week_end=week_end,
        missing=data.missing_protocols(db, now),
        meetings_today=data.meetings_between(db, today, today),
        meetings_next=data.meetings_between(db, today + timedelta(days=1), next_day),
        next_day=next_day,
        overbooked=overbooked,
        assignees=data.assignee_options(db),
        projects=data.project_options(db),
    )


@bp.route("/routine/<key>/<period>/erledigt", methods=["POST"])
def routine_done(key, period):
    if key not in data.ROUTINES or not re.fullmatch(r"\d{4}-(W\d{2}|\d{2})", period):
        abort(404)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO routine_checks (routine, period, done_at) VALUES (?, ?, ?)",
        (key, period, util.stamp()),
    )
    db.commit()
    flash(f"{data.ROUTINES[key]['label']} erledigt.", "ok")
    return redirect(url_for("main.dashboard"))
