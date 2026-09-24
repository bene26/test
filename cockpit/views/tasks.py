"""Tasks: list with filters, quick entry, bulk editing, CSV export."""

import csv
import io
import re

from flask import Blueprint, Response, abort, flash, render_template, request, url_for

from .. import data, forms, util
from ..db import get_db
from . import back, parse_or_flash

bp = Blueprint("tasks", __name__, url_prefix="/aufgaben")

PRESETS = {
    "ueberfaellig": "Überfällig",
    "heute": "Heute fällig",
    "woche": "Diese Woche fällig",
    "ohne_update": "Ohne Update",
    "ohne_termin": "Ohne Termin",
}
STATUS_FILTERS = {"open": "Alle offenen", "done": "Erledigt/abgenommen", "all": "Alle",
                  **util.TASK_STATUS}

TASK_FIELDS = {
    "title": forms.Text("Titel", required=True, max_len=200),
    "project_id": forms.Integer("Projekt", min_value=1),
    "assignee": forms.Assignee("Zuständig"),
    "due_date": forms.Date("Fällig"),
    "start_date": forms.Date("Start"),
    "effort_hours": forms.Number("Aufwand", min_value=0, max_value=10000),
    "priority": forms.Choice("Priorität", util.PRIORITY),
    "status": forms.Choice("Status", util.TASK_STATUS),
    "waiting_for": forms.Text("Wartet auf", max_len=120),
    "description": forms.Text("Beschreibung", max_len=5000, multiline=True),
}
QUICK_FIELDS = {k: TASK_FIELDS[k] for k in
                ("title", "project_id", "assignee", "due_date", "effort_hours")}

BULK_ACTIONS = {
    "status": "Status setzen",
    "verschieben": "Fälligkeit +7 Tage",
    "faellig": "Fällig am …",
    "zuweisen": "Zuweisen an …",
    "projekt": "Projekt setzen …",
    "bestaetigen": "Stand bestätigen",
    "loeschen": "Löschen",
}


def check_refs(db, project_id=None, person_id=None, firm_id=None, meeting_id=None):
    checks = (("projects", project_id, "Das Projekt"), ("people", person_id, "Die Person"),
              ("firms", firm_id, "Die Firma"), ("meetings", meeting_id, "Das Meeting"))
    for table, ident, label in checks:
        if ident is not None and not db.execute(
                f"SELECT 1 FROM {table} WHERE id = ?", (ident,)).fetchone():
            raise forms.ValidationError(f"{label} gibt es nicht.")


def create_task(db, values: dict, meeting_id=None) -> int:
    person_id, firm_id = values.get("assignee") or (None, None)
    check_refs(db, values.get("project_id"), person_id, firm_id, meeting_id)
    now = util.stamp()
    cur = db.execute(
        "INSERT INTO tasks (project_id, title, description, person_id, firm_id, effort_hours, "
        "start_date, due_date, priority, meeting_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (values.get("project_id"), values["title"], values.get("description", ""),
         person_id, firm_id, values.get("effort_hours"), values.get("start_date"),
         values.get("due_date"), int(values.get("priority") or 2), meeting_id, now, now),
    )
    return cur.lastrowid


def read_filters(args) -> dict:
    project = args.get("projekt", "")
    assignee_raw = args.get("zustaendig", "")
    assignee = None
    if assignee_raw == "none":
        assignee = "none"
    elif re.fullmatch(r"[pf]:\d{1,9}", assignee_raw):
        ident = int(assignee_raw[2:])
        assignee = (ident, None) if assignee_raw[0] == "p" else (None, ident)
    else:
        assignee_raw = ""
    status = args.get("status", "open")
    preset = args.get("ansicht", "")
    return {
        "project": project if project == "none" or project.isdigit() else "",
        "assignee": assignee,
        "assignee_raw": assignee_raw,
        "status": status if status in STATUS_FILTERS else "open",
        "preset": preset if preset in PRESETS else "",
        "query": args.get("q", "").strip()[:100],
    }


def _load(db, task_id):
    row = db.execute(data.TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
    if not row:
        abort(404)
    return data.task_dict(row, util.today())


@bp.route("")
def index():
    db = get_db()
    today = util.today()
    f = read_filters(request.args)
    stale_days = int(data.settings(db)["stale_days"])
    tasks = data.find_tasks(db, today, status=f["status"], project=f["project"],
                            assignee=f["assignee"], preset=f["preset"], query=f["query"],
                            stale_days=stale_days, limit=1000)
    return render_template(
        "tasks/index.html", tasks=tasks, filters=f, presets=PRESETS,
        status_filters=STATUS_FILTERS, bulk_actions=BULK_ACTIONS,
        assignees=data.assignee_options(db), projects=data.project_options(db),
        current_url=request.full_path.rstrip("?"),
        export_url=url_for("tasks.export", **request.args),
    )


@bp.route("/neu", methods=["POST"])
def create():
    values = parse_or_flash(QUICK_FIELDS)
    if values is None:
        return back(url_for("tasks.index"))
    db = get_db()
    try:
        task_id = create_task(db, values)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return back(url_for("tasks.index"))
    db.commit()
    flash(f"Aufgabe #{task_id} angelegt.", "ok")
    return back(url_for("tasks.index"))


@bp.route("/<int:task_id>", methods=["GET", "POST"])
def edit(task_id):
    db = get_db()
    task = _load(db, task_id)
    if request.method == "POST":
        values = parse_or_flash(TASK_FIELDS)
        if values is None:
            return back(url_for("tasks.edit", task_id=task_id))
        person_id, firm_id = values["assignee"]
        try:
            check_refs(db, values["project_id"], person_id, firm_id)
        except forms.ValidationError as exc:
            flash(str(exc), "error")
            return back(url_for("tasks.edit", task_id=task_id))
        status = values["status"] or task["status"]
        db.execute(
            "UPDATE tasks SET title = ?, project_id = ?, person_id = ?, firm_id = ?, "
            "due_date = ?, start_date = ?, effort_hours = ?, priority = ?, status = ?, "
            "waiting_for = ?, description = ?, updated_at = ?, done_at = ? WHERE id = ?",
            (values["title"], values["project_id"], person_id, firm_id, values["due_date"],
             values["start_date"], values["effort_hours"], int(values["priority"] or 2),
             status, values["waiting_for"], values["description"], util.stamp(),
             _done_at(task, status), task_id),
        )
        db.commit()
        flash("Gespeichert.", "ok")
        return back(url_for("tasks.edit", task_id=task_id))
    meeting = None
    if task["meeting_id"]:
        meeting = db.execute("SELECT id, title, starts_at FROM meetings WHERE id = ?",
                             (task["meeting_id"],)).fetchone()
    return render_template(
        "tasks/edit.html", task=task, meeting=meeting,
        assignees=data.assignee_options(db, task["assignee_value"]),
        projects=data.project_options(db, task["project_id"]),
        next_url=util.safe_next(request.args.get("next"), url_for("tasks.index")),
    )


def _done_at(task, new_status):
    if new_status in util.DONE_STATUSES:
        return task["done_at"] or util.stamp()
    return None


@bp.route("/<int:task_id>/status", methods=["POST"])
def set_status(task_id):
    values = parse_or_flash({"status": forms.Choice("Status", util.TASK_STATUS, required=True)})
    db = get_db()
    task = _load(db, task_id)
    if values:
        db.execute("UPDATE tasks SET status = ?, updated_at = ?, done_at = ? WHERE id = ?",
                   (values["status"], util.stamp(), _done_at(task, values["status"]), task_id))
        db.commit()
    return back(url_for("tasks.index"))


@bp.route("/<int:task_id>/bestaetigen", methods=["POST"])
def confirm(task_id):
    db = get_db()
    _load(db, task_id)
    db.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (util.stamp(), task_id))
    db.commit()
    flash(f"Stand von #{task_id} bestätigt.", "ok")
    return back(url_for("tasks.index"))


@bp.route("/<int:task_id>/loeschen", methods=["POST"])
def delete(task_id):
    db = get_db()
    _load(db, task_id)
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    flash(f"Aufgabe #{task_id} gelöscht.", "ok")
    return back(url_for("tasks.index"))


@bp.route("/sammel", methods=["POST"])
def bulk():
    values = parse_or_flash({
        "ids": forms.IdList("Aufgaben", required=True),
        "action": forms.Choice("Aktion", BULK_ACTIONS, required=True),
        "bulk_status": forms.Choice("Status", util.TASK_STATUS),
        "bulk_due": forms.Date("Fällig am"),
        "bulk_assignee": forms.Assignee("Zuständig"),
        "bulk_project": forms.Integer("Projekt", min_value=1),
    })
    if values is None:
        return back(url_for("tasks.index"))
    db = get_db()
    ids = values["ids"]
    marks = ",".join("?" * len(ids))
    now = util.stamp()
    action = values["action"]
    try:
        if action == "status":
            if not values["bulk_status"]:
                raise forms.ValidationError("Bitte einen Status wählen.")
            done_at = now if values["bulk_status"] in util.DONE_STATUSES else None
            db.execute(f"UPDATE tasks SET status = ?, updated_at = ?, "
                       f"done_at = CASE WHEN ? IS NULL THEN NULL ELSE COALESCE(done_at, ?) END "
                       f"WHERE id IN ({marks})",
                       (values["bulk_status"], now, done_at, done_at, *ids))
        elif action == "verschieben":
            base = util.today().isoformat()
            db.execute(f"UPDATE tasks SET due_date = date(COALESCE(due_date, ?), '+7 days'), "
                       f"updated_at = ? WHERE id IN ({marks})", (base, now, *ids))
        elif action == "faellig":
            if not values["bulk_due"]:
                raise forms.ValidationError("Bitte ein Datum wählen.")
            db.execute(f"UPDATE tasks SET due_date = ?, updated_at = ? WHERE id IN ({marks})",
                       (values["bulk_due"], now, *ids))
        elif action == "zuweisen":
            person_id, firm_id = values["bulk_assignee"]
            check_refs(db, person_id=person_id, firm_id=firm_id)
            db.execute(f"UPDATE tasks SET person_id = ?, firm_id = ?, updated_at = ? "
                       f"WHERE id IN ({marks})", (person_id, firm_id, now, *ids))
        elif action == "projekt":
            if not values["bulk_project"]:
                raise forms.ValidationError("Bitte ein Projekt wählen.")
            check_refs(db, project_id=values["bulk_project"])
            db.execute(f"UPDATE tasks SET project_id = ?, updated_at = ? WHERE id IN ({marks})",
                       (values["bulk_project"], now, *ids))
        elif action == "bestaetigen":
            db.execute(f"UPDATE tasks SET updated_at = ? WHERE id IN ({marks})", (now, *ids))
        elif action == "loeschen":
            db.execute(f"DELETE FROM tasks WHERE id IN ({marks})", ids)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return back(url_for("tasks.index"))
    db.commit()
    flash(f"{BULK_ACTIONS[action].rstrip(' …')}: {len(ids)} Aufgabe(n).", "ok")
    return back(url_for("tasks.index"))


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    # Keep spreadsheet programs from evaluating cell content as a formula.
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text
    return text


@bp.route("/export.csv")
def export():
    db = get_db()
    f = read_filters(request.args)
    tasks = data.find_tasks(db, util.today(), status=f["status"], project=f["project"],
                            assignee=f["assignee"], preset=f["preset"], query=f["query"])
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Nr.", "Titel", "Projekt", "Zuständig", "Status", "Priorität", "Fällig",
                     "Start", "Aufwand (h)", "Wartet auf", "Beschreibung", "Erstellt",
                     "Aktualisiert"])
    for t in tasks:
        writer.writerow([_csv_cell(v) for v in (
            t["id"], t["title"], t["project_name"], t["assignee"], t["status_label"],
            util.PRIORITY[t["priority"]], util.fmt_date(t["due_date"]),
            util.fmt_date(t["start_date"]),
            "" if t["effort_hours"] is None else str(t["effort_hours"]).replace(".", ","),
            t["waiting_for"], t["description"], t["created_at"], t["updated_at"])])
    filename = f"aufgaben-{util.today()}.csv"
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})

