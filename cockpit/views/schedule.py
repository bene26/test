"""Timeline: phases, milestones and dependencies, as a Gantt chart."""

from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import data, forms, schedule, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("schedule", __name__, url_prefix="/zeitplan")

KINDS = {"phase": "Vorgang", "milestone": "Meilenstein"}

ITEM_FIELDS = {
    "project_id": forms.Integer("Projekt", required=True, min_value=1),
    "kind": forms.Choice("Art", KINDS, required=True),
    "title": forms.Text("Bezeichnung", required=True, max_len=150),
    "start_date": forms.Date("Start", required=True),
    "end_date": forms.Date("Ende"),
    "progress": forms.Integer("Fortschritt", min_value=0, max_value=100),
    "reached": forms.Checkbox("Erreicht"),
    "assignee": forms.Assignee("Zuständig"),
    "push": forms.Checkbox("Nachfolger mitverschieben"),
}
LINK_FIELDS = {
    "pred_id": forms.Integer("Vorgänger", required=True, min_value=1),
    "lag_days": forms.Integer("Puffer", min_value=-365, max_value=365),
}


def _row(db, values) -> tuple:
    if not db.execute("SELECT 1 FROM projects WHERE id = ?", (values["project_id"],)).fetchone():
        raise forms.ValidationError("Das Projekt gibt es nicht.")
    person_id, firm_id = values["assignee"]
    for table, ident in (("people", person_id), ("firms", firm_id)):
        if ident and not db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (ident,)).fetchone():
            raise forms.ValidationError("Die zuständige Person oder Firma gibt es nicht.")
    start = values["start_date"]
    if values["kind"] == "milestone":
        end = start
        progress = 100 if values["reached"] else 0
    else:
        end = values["end_date"] or start
        if end < start:
            raise forms.ValidationError("Das Ende liegt vor dem Start.")
        if (util.to_date(end) - util.to_date(start)).days > 3 * 366:
            raise forms.ValidationError("Ein Vorgang darf höchstens drei Jahre dauern.")
        progress = values["progress"] or 0
    return (values["project_id"], values["kind"], values["title"], start, end, progress,
            person_id, firm_id)


def _item_options(db, exclude=None):
    groups = {}
    for it in schedule.items(db):
        if it["id"] == exclude:
            continue
        label = f"{it['title']} ({util.fmt_date(it['end'])})"
        groups.setdefault(it["project_label"], []).append((it["id"], label))
    return list(groups.items())


@bp.route("")
def index():
    db = get_db()
    today = util.today()
    project_id = request.args.get("projekt", type=int)
    project = None
    if project_id:
        project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            abort(404)
    show_links = request.args.get("pfeile") != "0"
    ov = schedule.overview(db, today, project_id)
    conflict_ids = {c["link"]["id"] for c in ov["conflicts"]}
    chart = schedule.gantt(ov["items"], ov["links"], conflict_ids, today, show_links)
    external = []
    if project_id:
        own = {i["id"] for i in ov["items"]}
        for link in ov["links"]:
            if (link["pred_id"] in own) != (link["succ_id"] in own):
                external.append({"link": link, "pred": ov["by_id"][link["pred_id"]],
                                 "succ": ov["by_id"][link["succ_id"]],
                                 "conflict": link["id"] in conflict_ids})
    return render_template(
        "schedule/index.html", project=project, ov=ov, chart=chart, show_links=show_links,
        external=external, today=today, kinds=KINDS,
        projects=data.project_options(db, project_id),
        assignees=data.assignee_options(db),
        progress=schedule.project_progress(ov["items"]) if project_id else None,
    )


@bp.route("/neu", methods=["POST"])
def create():
    values = parse_or_flash(ITEM_FIELDS)
    target = url_for("schedule.index", projekt=request.form.get("project_id", type=int))
    if values is None:
        return redirect(target)
    db = get_db()
    try:
        row = _row(db, values)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(target)
    now = util.stamp()
    db.execute(
        "INSERT INTO schedule_items (project_id, kind, title, start_date, end_date, progress, "
        "person_id, firm_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (*row, now, now))
    db.commit()
    flash(f"{KINDS[values['kind']]} „{values['title']}“ angelegt.", "ok")
    return redirect(url_for("schedule.index", projekt=values["project_id"]))


@bp.route("/<int:item_id>", methods=["GET", "POST"])
def edit(item_id):
    db = get_db()
    it = schedule.item(db, item_id)
    if not it:
        abort(404)
    if request.method == "POST":
        values = parse_or_flash(ITEM_FIELDS)
        if values is not None:
            try:
                row = _row(db, values)
            except forms.ValidationError as exc:
                flash(str(exc), "error")
            else:
                db.execute(
                    "UPDATE schedule_items SET project_id = ?, kind = ?, title = ?, "
                    "start_date = ?, end_date = ?, progress = ?, person_id = ?, firm_id = ?, "
                    "updated_at = ? WHERE id = ?", (*row, util.stamp(), item_id))
                moved = schedule.push_successors(db, item_id) if values["push"] else []
                db.commit()
                message = "Gespeichert."
                if moved:
                    message += " Mitverschoben: " + ", ".join(m["title"] for m in moved) + "."
                flash(message, "ok")
        return redirect(url_for("schedule.edit", item_id=item_id))
    by_id = {i["id"]: i for i in schedule.items(db)}
    links = schedule.all_links(db)
    conflict_ids = {c["link"]["id"] for c in schedule.conflicts(by_id, links)}
    preds = [{"link": l, "item": by_id[l["pred_id"]], "conflict": l["id"] in conflict_ids}
             for l in links if l["succ_id"] == item_id]
    succs = [{"link": l, "item": by_id[l["succ_id"]], "conflict": l["id"] in conflict_ids}
             for l in links if l["pred_id"] == item_id]
    return render_template(
        "schedule/edit.html", it=it, preds=preds, succs=succs, kinds=KINDS,
        options=_item_options(db, exclude=item_id), projects=data.project_options(db, it["project_id"]),
        assignees=data.assignee_options(db, it["assignee_value"]),
    )


@bp.route("/<int:item_id>/loeschen", methods=["POST"])
def delete(item_id):
    db = get_db()
    it = schedule.item(db, item_id)
    if not it:
        abort(404)
    db.execute("DELETE FROM schedule_items WHERE id = ?", (item_id,))
    db.commit()
    flash(f"„{it['title']}“ gelöscht.", "ok")
    return redirect(url_for("schedule.index", projekt=it["project_id"]))


@bp.route("/<int:item_id>/vorgaenger", methods=["POST"])
def add_link(item_id):
    db = get_db()
    it = schedule.item(db, item_id)
    if not it:
        abort(404)
    values = parse_or_flash(LINK_FIELDS)
    if values is not None:
        pred_id = values["pred_id"]
        if pred_id == item_id:
            flash("Ein Eintrag kann nicht von sich selbst abhängen.", "error")
        elif not schedule.item(db, pred_id):
            flash("Den Vorgänger gibt es nicht.", "error")
        elif db.execute("SELECT 1 FROM schedule_links WHERE pred_id = ? AND succ_id = ?",
                        (pred_id, item_id)).fetchone():
            flash("Diese Abhängigkeit gibt es schon.", "error")
        elif schedule.would_cycle(db, pred_id, item_id):
            flash("Das ergäbe einen Kreis: Der Vorgänger hängt schon von diesem Eintrag ab.",
                  "error")
        else:
            db.execute("INSERT INTO schedule_links (pred_id, succ_id, lag_days) VALUES (?, ?, ?)",
                       (pred_id, item_id, values["lag_days"] or 0))
            db.commit()
            flash("Abhängigkeit angelegt.", "ok")
    return redirect(url_for("schedule.edit", item_id=item_id))


@bp.route("/abhaengigkeiten/<int:link_id>/loeschen", methods=["POST"])
def delete_link(link_id):
    db = get_db()
    link = db.execute("SELECT * FROM schedule_links WHERE id = ?", (link_id,)).fetchone()
    if not link:
        abort(404)
    db.execute("DELETE FROM schedule_links WHERE id = ?", (link_id,))
    db.commit()
    flash("Abhängigkeit entfernt.", "ok")
    return redirect(util.safe_next(request.form.get("next"),
                                   url_for("schedule.edit", item_id=link["succ_id"])))


@bp.route("/abhaengigkeiten/<int:link_id>/aufloesen", methods=["POST"])
def resolve(link_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM schedule_links WHERE id = ?", (link_id,)).fetchone():
        abort(404)
    moved = schedule.resolve(db, link_id)
    db.commit()
    if moved:
        flash("Verschoben: " + ", ".join(
            f"{m['title']} (ab {util.fmt_date(m['start'])})" for m in moved) + ".", "ok")
    else:
        flash("Kein Konflikt mehr, nichts verschoben.", "ok")
    return redirect(util.safe_next(request.form.get("next"), url_for("schedule.index")))


def due_soon(ov, today, days=42):
    """Upcoming milestones within `days`, for the dashboard."""
    limit = today + timedelta(days=days)
    return [m for m in ov["upcoming"] if m["end"] <= limit]
