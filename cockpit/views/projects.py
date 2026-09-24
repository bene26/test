"""Projects with their tasks, meetings and decision register."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import data, forms, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("projects", __name__, url_prefix="/projekte")

PROJECT_FIELDS = {
    "name": forms.Text("Name", required=True, max_len=150),
    "code": forms.Text("Kürzel", max_len=20),
    "client": forms.Text("Auftraggeber", max_len=150),
    "status": forms.Choice("Status", util.PROJECT_STATUS),
    "priority": forms.Choice("Priorität", util.PRIORITY),
    "start_date": forms.Date("Start"),
    "end_date": forms.Date("Ende"),
    "notes": forms.Text("Notizen", max_len=5000, multiline=True),
}


def _values(values):
    if values["start_date"] and values["end_date"] and values["end_date"] < values["start_date"]:
        raise forms.ValidationError("Das Ende liegt vor dem Start.")
    return (values["name"], values["code"], values["client"], values["status"] or "aktiv",
            int(values["priority"] or 2), values["start_date"], values["end_date"],
            values["notes"])


@bp.route("")
def index():
    db = get_db()
    today = util.today().isoformat()
    projects = db.execute(
        "SELECT p.*, "
        f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {data.OPEN_SQL}) "
        "  AS open_tasks, "
        f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {data.OPEN_SQL} "
        "  AND t.due_date < ?) AS overdue, "
        "(SELECT MIN(starts_at) FROM meetings m WHERE m.project_id = p.id AND m.starts_at >= ?) "
        "  AS next_meeting "
        "FROM projects p ORDER BY p.status = 'abgeschlossen', p.priority, p.name",
        (today, today),
    ).fetchall()
    return render_template("projects/index.html", projects=projects)


@bp.route("/neu", methods=["POST"])
def create():
    values = parse_or_flash(PROJECT_FIELDS)
    if values is None:
        return redirect(url_for("projects.index"))
    db = get_db()
    try:
        row = _values(values)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("projects.index"))
    now = util.stamp()
    cur = db.execute(
        "INSERT INTO projects (name, code, client, status, priority, start_date, end_date, "
        "notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*row, now, now))
    db.commit()
    flash("Projekt angelegt.", "ok")
    return redirect(url_for("projects.detail", project_id=cur.lastrowid))


@bp.route("/<int:project_id>", methods=["GET", "POST"])
def detail(project_id):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        abort(404)
    if request.method == "POST":
        values = parse_or_flash(PROJECT_FIELDS)
        if values is not None:
            try:
                row = _values(values)
            except forms.ValidationError as exc:
                flash(str(exc), "error")
            else:
                db.execute(
                    "UPDATE projects SET name = ?, code = ?, client = ?, status = ?, priority = ?, "
                    "start_date = ?, end_date = ?, notes = ?, updated_at = ? WHERE id = ?",
                    (*row, util.stamp(), project_id))
                db.commit()
                flash("Gespeichert.", "ok")
        return redirect(url_for("projects.detail", project_id=project_id))
    today = util.today()
    meetings = db.execute(
        "SELECT m.*, f.name AS firm_name FROM meetings m LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.project_id = ? ORDER BY m.starts_at DESC LIMIT 100", (project_id,)).fetchall()
    decisions = db.execute(
        "SELECT d.*, m.title AS meeting_title, m.starts_at FROM decisions d "
        "JOIN meetings m ON m.id = d.meeting_id WHERE d.project_id = ? ORDER BY d.number",
        (project_id,)).fetchall()
    return render_template(
        "projects/detail.html", project=project, meetings=meetings, decisions=decisions,
        tasks=data.find_tasks(db, today, project=str(project_id)),
        assignees=data.assignee_options(db), projects=data.project_options(db, project_id),
    )


@bp.route("/<int:project_id>/loeschen", methods=["POST"])
def delete(project_id):
    db = get_db()
    used = db.execute(
        "SELECT (SELECT COUNT(*) FROM tasks WHERE project_id = ?) + "
        "(SELECT COUNT(*) FROM meetings WHERE project_id = ?)", (project_id, project_id)
    ).fetchone()[0]
    if used:
        flash("Das Projekt hat noch Aufgaben oder Meetings. Setze es stattdessen auf "
              "„Abgeschlossen“.", "error")
        return redirect(url_for("projects.detail", project_id=project_id))
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    flash("Projekt gelöscht.", "ok")
    return redirect(url_for("projects.index"))
