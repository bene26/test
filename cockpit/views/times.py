"""Project hours (Ist-Aufwand) per person, project and day, entered per week.

Only internal staff and staff under Arbeitnehmerüberlassung. Work of firms
under Werk- or Dienstvertrag is booked as service records on their orders.
"""

import re
from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import forms, util
from ..db import get_db
from . import csv_response, parse_or_flash

bp = Blueprint("times", __name__, url_prefix="/zeiten")

CELL_RE = re.compile(r"h_(\d{1,9})_(\d{4}-\d{2}-\d{2})")
WEEK_RE = re.compile(r"(\d{4})-W(\d{2})")


def parse_week(value, today: date) -> date:
    """Monday of an ISO week given as '2026-W41'; the current week otherwise."""
    match = WEEK_RE.fullmatch(value or "")
    if match:
        try:
            return date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            pass
    return util.week_start(today)


def _people(db):
    return db.execute(
        "SELECT pe.id, pe.name, pe.weekly_hours, f.name AS firm_name FROM people pe "
        "LEFT JOIN firms f ON f.id = pe.firm_id WHERE pe.active = 1 "
        "ORDER BY f.name IS NOT NULL, f.name, pe.name").fetchall()


def week_hours(db, monday: date, person_id=None) -> list:
    sunday = monday + timedelta(days=6)
    sql = ("SELECT person_id, project_id, work_date, hours FROM time_entries "
           "WHERE work_date BETWEEN ? AND ?")
    params = [monday.isoformat(), sunday.isoformat()]
    if person_id:
        sql += " AND person_id = ?"
        params.append(person_id)
    return db.execute(sql, params).fetchall()


@bp.route("")
def index():
    db = get_db()
    today = util.today()
    people = _people(db)
    person_id = request.args.get("person", type=int)
    person = next((p for p in people if p["id"] == person_id), people[0] if people else None)
    if person_id and person and person["id"] != person_id:
        row = db.execute("SELECT pe.id, pe.name, pe.weekly_hours, f.name AS firm_name "
                         "FROM people pe LEFT JOIN firms f ON f.id = pe.firm_id "
                         "WHERE pe.id = ?", (person_id,)).fetchone()
        if not row:
            abort(404)
        person = row
    monday = parse_week(request.args.get("woche"), today)
    days = [monday + timedelta(days=i) for i in range(7)]
    grid, project_ids = {}, set()
    if person:
        for r in week_hours(db, monday, person["id"]):
            grid[(r["project_id"], r["work_date"])] = r["hours"]
            project_ids.add(r["project_id"])
    projects = db.execute(
        "SELECT id, name, code FROM projects WHERE status IN ('aktiv', 'geplant') "
        f"OR id IN ({','.join('?' * len(project_ids)) or 'NULL'}) "
        "ORDER BY status = 'abgeschlossen', priority, name", sorted(project_ids)).fetchall()
    rows = []
    for p in projects:
        cells = [{"date": d, "name": f"h_{p['id']}_{d.isoformat()}",
                  "value": grid.get((p["id"], d.isoformat()))} for d in days]
        rows.append({"project": p, "cells": cells,
                     "total": sum(c["value"] or 0 for c in cells)})
    day_totals = [sum(grid.get((p["id"], d.isoformat()), 0) for p in projects) for d in days]
    previous = monday - timedelta(days=7)
    has_previous = bool(person and week_hours(db, previous, person["id"]))
    return render_template(
        "times/index.html", people=people, person=person, monday=monday, days=days,
        rows=rows, day_totals=day_totals, total=sum(day_totals), today=today,
        week=util.week_key(monday), prev_week=util.week_key(previous),
        next_week=util.week_key(monday + timedelta(days=7)),
        this_week=util.week_key(today), has_previous=has_previous and not grid,
        fmt=util.fmt_number,
    )


@bp.route("", methods=["POST"])
def save():
    db = get_db()
    spec = {"person_id": forms.Integer("Person", required=True, min_value=1),
            "week": forms.Text("Woche", required=True, max_len=10)}
    for key in request.form:
        if CELL_RE.fullmatch(key):
            spec[key] = forms.Number("Stunden", min_value=0, max_value=24)
    values = parse_or_flash(spec)
    if values is None:
        return redirect(url_for("times.index", person=request.form.get("person_id", type=int),
                                woche=request.form.get("week")))
    person_id = values["person_id"]
    monday = parse_week(values["week"], util.today())
    target = url_for("times.index", person=person_id, woche=util.week_key(monday))
    if not db.execute("SELECT 1 FROM people WHERE id = ?", (person_id,)).fetchone():
        flash("Die Person gibt es nicht.", "error")
        return redirect(target)
    week_days = {(monday + timedelta(days=i)).isoformat() for i in range(7)}
    known = {r[0] for r in db.execute("SELECT id FROM projects")}
    cells, per_day = [], defaultdict(float)
    for key, hours in values.items():
        match = CELL_RE.fullmatch(key)
        if not match:
            continue
        project_id, day = int(match.group(1)), match.group(2)
        if day not in week_days or project_id not in known:
            flash("Das Formular passt nicht zur gewählten Woche. Bitte neu laden.", "error")
            return redirect(target)
        cells.append((project_id, day, hours or 0))
        per_day[day] += hours or 0
    too_much = [d for d, h in per_day.items() if h > 24]
    if too_much:
        flash(f"Am {util.fmt_date(min(too_much))} sind mehr als 24 Stunden eingetragen.", "error")
        return redirect(target)
    now = util.stamp()
    for project_id, day, hours in cells:
        if hours:
            db.execute(
                "INSERT INTO time_entries (person_id, project_id, work_date, hours, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (person_id, project_id, "
                "work_date) DO UPDATE SET hours = excluded.hours, updated_at = excluded.updated_at",
                (person_id, project_id, day, hours, now, now))
        else:
            db.execute("DELETE FROM time_entries WHERE person_id = ? AND project_id = ? "
                       "AND work_date = ?", (person_id, project_id, day))
    db.commit()
    total = sum(r["hours"] for r in week_hours(db, monday, person_id))
    flash(f"Gespeichert: {util.fmt_hours(total)} in KW {util.week_number(monday)}.", "ok")
    return redirect(target)


@bp.route("/vorwoche", methods=["POST"])
def copy_previous():
    values = parse_or_flash({"person_id": forms.Integer("Person", required=True, min_value=1),
                             "week": forms.Text("Woche", required=True, max_len=10)})
    if values is None:
        return redirect(url_for("times.index"))
    db = get_db()
    monday = parse_week(values["week"], util.today())
    person_id = values["person_id"]
    target = url_for("times.index", person=person_id, woche=util.week_key(monday))
    if week_hours(db, monday, person_id):
        flash("Diese Woche hat schon Einträge. Übernommen wird nur in eine leere Woche.", "error")
        return redirect(target)
    now = util.stamp()
    count = 0
    for r in week_hours(db, monday - timedelta(days=7), person_id):
        day = (util.to_date(r["work_date"]) + timedelta(days=7)).isoformat()
        db.execute("INSERT INTO time_entries (person_id, project_id, work_date, hours, "
                   "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (person_id, r["project_id"], day, r["hours"], now, now))
        count += 1
    db.commit()
    flash(f"{count} Einträge aus der Vorwoche übernommen. Bitte prüfen und anpassen.", "ok")
    return redirect(target)


@bp.route("/team")
def team():
    db = get_db()
    today = util.today()
    monday = parse_week(request.args.get("woche"), today)
    days = [monday + timedelta(days=i) for i in range(7)]
    entries = week_hours(db, monday)
    by_person = defaultdict(lambda: defaultdict(float))
    by_project = defaultdict(float)
    for r in entries:
        by_person[r["person_id"]][r["work_date"]] += r["hours"]
        by_project[r["project_id"]] += r["hours"]
    rows = []
    for p in _people(db):
        hours = [by_person[p["id"]].get(d.isoformat(), 0) for d in days]
        rows.append({"person": p, "hours": hours, "total": sum(hours)})
    names = {r["id"]: r for r in db.execute("SELECT id, name, code FROM projects")}
    projects = sorted(({"project": names[pid], "hours": h} for pid, h in by_project.items()),
                      key=lambda x: -x["hours"])
    return render_template(
        "times/team.html", rows=rows, days=days, projects=projects, monday=monday,
        total=sum(by_project.values()), today=today, week=util.week_key(monday),
        prev_week=util.week_key(monday - timedelta(days=7)),
        next_week=util.week_key(monday + timedelta(days=7)), this_week=util.week_key(today),
        fmt=util.fmt_number)


def month_range(value, today: date) -> tuple[date, date]:
    """First and last day of a month given as 'YYYY-MM'; the current month otherwise."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", value or "")
    first = today.replace(day=1)
    if match and 1 <= int(match.group(2)) <= 12 and 2000 <= int(match.group(1)) <= 2100:
        first = date(int(match.group(1)), int(match.group(2)), 1)
    last = date(first.year + (first.month == 12), first.month % 12 + 1, 1) - timedelta(days=1)
    return first, last


@bp.route("/export.csv")
def export():
    db = get_db()
    first, last = month_range(request.args.get("monat"), util.today())
    rows = db.execute(
        "SELECT t.work_date, pe.name AS person, f.name AS firm, p.name AS project, p.code, "
        "t.hours FROM time_entries t JOIN people pe ON pe.id = t.person_id "
        "LEFT JOIN firms f ON f.id = pe.firm_id JOIN projects p ON p.id = t.project_id "
        "WHERE t.work_date BETWEEN ? AND ? ORDER BY t.work_date, pe.name, p.name",
        (first.isoformat(), last.isoformat())).fetchall()
    return csv_response(
        f"projektstunden-{first:%Y-%m}.csv",
        ["Datum", "Person", "Firma (Arbeitnehmerüberlassung)", "Projekt", "Kürzel", "Stunden"],
        ([util.fmt_date(r["work_date"]), r["person"], r["firm"] or "", r["project"], r["code"],
          util.fmt_number(r["hours"])] for r in rows))
