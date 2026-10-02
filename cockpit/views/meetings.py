"""Meetings: agenda from templates, live protocol, decisions, actions, versions."""

import json
import logging
import re
from datetime import timedelta

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

from .. import data, forms, notify, util
from ..db import get_db
from ..meeting_types import AUTO_KINDS, MEETING_TYPES
from ..meeting_types import label as type_label
from . import parse_or_flash
from .tasks import check_refs, create_task

bp = Blueprint("meetings", __name__, url_prefix="/meetings")
log = logging.getLogger("cockpit")

EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}")

HEADER_FIELDS = {
    "title": forms.Text("Titel", max_len=150),
    "project_id": forms.Integer("Projekt", min_value=1),
    "firm_id": forms.Integer("Firma", min_value=1),
    "date": forms.Date("Datum", required=True),
    "time": forms.Time("Uhrzeit", required=True),
    "duration_min": forms.Integer("Dauer", min_value=5, max_value=600),
    "location": forms.Text("Ort / Link", max_len=300),
    "participants": forms.Text("Teilnehmende", max_len=3000, multiline=True),
}


def _load(db, meeting_id):
    row = db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.id = ?", (meeting_id,)).fetchone()
    if not row:
        abort(404)
    return row


def _default_title(db, kind, project_id, firm_id):
    parts = [type_label(kind)]
    if firm_id:
        parts.append(db.execute("SELECT name FROM firms WHERE id = ?", (firm_id,)).fetchone()[0])
    if project_id:
        parts.append(db.execute("SELECT name FROM projects WHERE id = ?",
                                (project_id,)).fetchone()[0])
    return " · ".join(parts)


def _insert_meeting(db, kind, values, previous_id=None) -> int:
    check_refs(db, project_id=values["project_id"])
    if values["firm_id"] and not db.execute("SELECT 1 FROM firms WHERE id = ?",
                                            (values["firm_id"],)).fetchone():
        raise forms.ValidationError("Die Firma gibt es nicht.")
    now = util.stamp()
    title = values["title"] or _default_title(db, kind, values["project_id"], values["firm_id"])
    cur = db.execute(
        "INSERT INTO meetings (type, title, project_id, firm_id, starts_at, duration_min, "
        "location, participants, previous_meeting_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, title, values["project_id"], values["firm_id"],
         f"{values['date']} {values['time']}",
         values["duration_min"] or MEETING_TYPES[kind]["duration"], values["location"],
         values["participants"], previous_id, now, now),
    )
    meeting_id = cur.lastrowid
    for position, (item_title, auto) in enumerate(MEETING_TYPES[kind]["agenda"], start=1):
        db.execute("INSERT INTO agenda_items (meeting_id, position, title, auto) "
                   "VALUES (?, ?, ?, ?)", (meeting_id, position, item_title, auto))
    return meeting_id


def recipients(participants: str) -> list[str]:
    seen, result = set(), []
    for address in EMAIL_IN_TEXT.findall(participants or ""):
        if address.lower() not in seen:
            seen.add(address.lower())
            result.append(address)
    return result


def _agenda(db, meeting_id):
    return db.execute("SELECT * FROM agenda_items WHERE meeting_id = ? ORDER BY position, id",
                      (meeting_id,)).fetchall()


def _decisions(db, meeting_id):
    return db.execute("SELECT * FROM decisions WHERE meeting_id = ? ORDER BY number",
                      (meeting_id,)).fetchall()


def _followup(db, meeting_id):
    return db.execute("SELECT id, starts_at FROM meetings WHERE previous_meeting_id = ? "
                      "ORDER BY starts_at LIMIT 1", (meeting_id,)).fetchone()


def build_snapshot(db, meeting, version: int) -> dict:
    today = util.today()
    agenda = []
    for item in _agenda(db, meeting["id"]):
        entry = {"title": item["title"], "notes": item["notes"]}
        if item["auto"]:
            table = data.auto_table(db, meeting, item["auto"], today)
            entry["table"] = {k: table[k] for k in ("columns", "rows", "empty")}
        agenda.append(entry)
    actions = data.find_tasks(db, today, status="all", meeting_id=meeting["id"])
    followup = _followup(db, meeting["id"])
    return {
        "version": version,
        "title": meeting["title"],
        "type_label": type_label(meeting["type"]),
        "project": meeting["project_name"] or "",
        "firm": meeting["firm_name"] or "",
        "when": util.fmt_datetime(meeting["starts_at"]),
        "duration_min": meeting["duration_min"],
        "location": meeting["location"],
        "participants": [line.strip() for line in meeting["participants"].splitlines()
                         if line.strip()],
        "agenda": agenda,
        "decisions": [{"code": f"E-{d['number']:02d}", "text": d["text"]}
                      for d in _decisions(db, meeting["id"])],
        "actions": [{"code": f"#{t['id']}", "title": t["title"], "assignee": t["assignee"],
                     "due": util.fmt_date(t["due_date"])} for t in actions],
        "next_meeting": util.fmt_datetime(followup["starts_at"]) if followup else "",
        "finalized_at": util.fmt_datetime(util.now()),
    }


def snapshot_text(s: dict) -> str:
    lines = [f"PROTOKOLL: {s['title']}", f"{s['type_label']} · {s['when']} ({s['duration_min']} min)"]
    if s["project"]:
        lines.append(f"Projekt: {s['project']}")
    if s["firm"]:
        lines.append(f"Firma: {s['firm']}")
    if s["location"]:
        lines.append(f"Ort: {s['location']}")
    lines.append(f"Version {s['version']}, abgeschlossen am {s['finalized_at']}")
    lines += ["", "TEILNEHMENDE"] + [f"- {p}" for p in s["participants"] or ["–"]]
    lines += ["", "TAGESORDNUNG"]
    for number, item in enumerate(s["agenda"], start=1):
        lines.append(f"{number}. {item['title']}")
        table = item.get("table")
        if table:
            if table["rows"]:
                for row in table["rows"]:
                    lines.append("   " + " | ".join(cell for cell in row if cell))
            else:
                lines.append(f"   {table['empty']}")
        if item["notes"]:
            lines += ["   " + line for line in item["notes"].splitlines()]
        lines.append("")
    lines.append("ENTSCHEIDUNGEN")
    lines += [f"{d['code']}  {d['text']}" for d in s["decisions"]] or ["–"]
    lines += ["", "MASSNAHMEN"]
    lines += [f"{a['code']}  {a['title']} · {a['assignee'] or 'offen'}"
              + (f" · bis {a['due']}" if a["due"] else "") for a in s["actions"]] or ["–"]
    if s["next_meeting"]:
        lines += ["", f"Nächster Termin: {s['next_meeting']}"]
    return "\n".join(lines) + "\n"


def _require_open(meeting):
    if meeting["protocol_status"] != "offen":
        flash("Das Protokoll ist abgeschlossen. Für Änderungen zuerst „Korrektur beginnen“.",
              "error")
        return redirect(url_for("meetings.detail", meeting_id=meeting["id"]))
    return None


@bp.route("")
def index():
    db = get_db()
    now = util.now()
    upcoming = data.meetings_between(db, now.date(), now.date() + timedelta(days=30))
    closed = db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.protocol_status = 'abgeschlossen' ORDER BY m.starts_at DESC LIMIT 50"
    ).fetchall()
    later = db.execute(
        "SELECT COUNT(*) FROM meetings WHERE starts_at >= ?",
        ((now.date() + timedelta(days=31)).isoformat(),)).fetchone()[0]
    return render_template(
        "meetings/index.html", upcoming=upcoming, missing=data.missing_protocols(db, now),
        closed=closed, later=later, projects=data.project_options(db),
        firms=db.execute("SELECT id, name FROM firms WHERE active = 1 ORDER BY name").fetchall(),
        preset_type=request.args.get("typ", "jourfixe"),
        preset_project=request.args.get("projekt", type=int),
        preset_firm=request.args.get("firma", type=int),
    )


@bp.route("/neu", methods=["POST"])
def create():
    spec = {"type": forms.Choice("Art", MEETING_TYPES, required=True), **HEADER_FIELDS}
    values = parse_or_flash(spec)
    if values is None:
        return redirect(url_for("meetings.index"))
    db = get_db()
    try:
        meeting_id = _insert_meeting(db, values["type"], values)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("meetings.index"))
    db.commit()
    return redirect(url_for("meetings.detail", meeting_id=meeting_id))


@bp.route("/<int:meeting_id>")
def detail(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    versions = db.execute(
        "SELECT version, finalized_at, sent_to FROM protocol_versions WHERE meeting_id = ? "
        "ORDER BY version DESC", (meeting_id,)).fetchall()
    common = {"meeting": meeting, "versions": versions, "type_label": type_label(meeting["type"]),
              "recipients": recipients(meeting["participants"]),
              "smtp": notify.smtp_configured(), "followup": _followup(db, meeting_id)}
    if meeting["protocol_status"] == "abgeschlossen":
        latest = db.execute(
            "SELECT snapshot_json FROM protocol_versions WHERE meeting_id = ? "
            "ORDER BY version DESC LIMIT 1", (meeting_id,)).fetchone()
        return render_template("meetings/closed.html",
                               snapshot=json.loads(latest["snapshot_json"]), **common)
    today = util.today()
    agenda = []
    for item in _agenda(db, meeting_id):
        table = data.auto_table(db, meeting, item["auto"], today) if item["auto"] else None
        agenda.append({"item": item, "table": table})
    return render_template(
        "meetings/edit.html", agenda=agenda, decisions=_decisions(db, meeting_id),
        actions=data.find_tasks(db, today, status="all", meeting_id=meeting_id),
        assignees=data.assignee_options(db), projects=data.project_options(db,
                                                                            meeting["project_id"]),
        firms=db.execute("SELECT id, name FROM firms ORDER BY name").fetchall(),
        auto_kinds=AUTO_KINDS, suggested_next=_suggest_next(meeting), **common,
    )


def _suggest_next(meeting):
    start = util.to_datetime(meeting["starts_at"])
    step = 14 if meeting["type"] in ("management",) else 7
    return start + timedelta(days=step)


def _save_editor(db, meeting, extra_allowed=frozenset()):
    items = _agenda(db, meeting["id"])
    spec = dict(HEADER_FIELDS)
    for item in items:
        spec[f"title_{item['id']}"] = forms.Text("Tagesordnungspunkt", required=True, max_len=200)
        spec[f"note_{item['id']}"] = forms.Text("Notizen", max_len=20000, multiline=True)
    values = forms.parse(request.form, spec, extra_allowed)
    check_refs(db, project_id=values["project_id"])
    if values["firm_id"] and not db.execute("SELECT 1 FROM firms WHERE id = ?",
                                            (values["firm_id"],)).fetchone():
        raise forms.ValidationError("Die Firma gibt es nicht.")
    db.execute(
        "UPDATE meetings SET title = ?, project_id = ?, firm_id = ?, starts_at = ?, "
        "duration_min = ?, location = ?, participants = ?, updated_at = ? WHERE id = ?",
        (values["title"] or meeting["title"], values["project_id"], values["firm_id"],
         f"{values['date']} {values['time']}", values["duration_min"] or meeting["duration_min"],
         values["location"], values["participants"], util.stamp(), meeting["id"]),
    )
    for item in items:
        db.execute("UPDATE agenda_items SET title = ?, notes = ? WHERE id = ?",
                   (values[f"title_{item['id']}"], values[f"note_{item['id']}"], item["id"]))
    return values


@bp.route("/<int:meeting_id>", methods=["POST"])
def save(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    autosave = bool(request.headers.get("X-Autosave"))
    if meeting["protocol_status"] != "offen":
        if autosave:
            return {"error": "Protokoll ist abgeschlossen."}, 409
        return _require_open(meeting)
    try:
        _save_editor(db, meeting)
    except forms.ValidationError as exc:
        if autosave:
            return {"error": str(exc)}, 400
        flash(str(exc), "error")
        return redirect(url_for("meetings.detail", meeting_id=meeting_id))
    db.commit()
    if autosave:
        return "", 204
    flash("Gespeichert.", "ok")
    return redirect(url_for("meetings.detail", meeting_id=meeting_id))


@bp.route("/<int:meeting_id>/punkte", methods=["POST"])
def add_item(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    values = parse_or_flash({"title": forms.Text("Tagesordnungspunkt", required=True,
                                                 max_len=200)})
    if values:
        position = db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM agenda_items "
                              "WHERE meeting_id = ?", (meeting_id,)).fetchone()[0]
        db.execute("INSERT INTO agenda_items (meeting_id, position, title) VALUES (?, ?, ?)",
                   (meeting_id, position, values["title"]))
        db.commit()
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="agenda"))


@bp.route("/<int:meeting_id>/punkte/<int:item_id>/loeschen", methods=["POST"])
def delete_item(meeting_id, item_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    db.execute("DELETE FROM agenda_items WHERE id = ? AND meeting_id = ?", (item_id, meeting_id))
    db.commit()
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="agenda"))


@bp.route("/<int:meeting_id>/entscheidungen", methods=["POST"])
def add_decision(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    values = parse_or_flash({"text": forms.Text("Entscheidung", required=True, max_len=2000,
                                                multiline=True)})
    if values:
        number = db.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM decisions "
                            "WHERE project_id IS ?", (meeting["project_id"],)).fetchone()[0]
        db.execute("INSERT INTO decisions (meeting_id, project_id, number, text, created_at) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (meeting_id, meeting["project_id"], number, values["text"], util.stamp()))
        db.commit()
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="entscheidungen"))


@bp.route("/<int:meeting_id>/entscheidungen/<int:decision_id>/loeschen", methods=["POST"])
def delete_decision(meeting_id, decision_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    db.execute("DELETE FROM decisions WHERE id = ? AND meeting_id = ?", (decision_id, meeting_id))
    db.commit()
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="entscheidungen"))


@bp.route("/<int:meeting_id>/massnahmen", methods=["POST"])
def add_action(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    values = parse_or_flash({
        "title": forms.Text("Maßnahme", required=True, max_len=200),
        "assignee": forms.Assignee("Zuständig"),
        "due_date": forms.Date("Bis wann"),
    })
    if values:
        values["project_id"] = meeting["project_id"]
        try:
            task_id = create_task(db, values, meeting_id=meeting_id)
        except forms.ValidationError as exc:
            flash(str(exc), "error")
        else:
            db.commit()
            flash(f"Maßnahme #{task_id} angelegt und in die Aufgaben übernommen.", "ok")
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="massnahmen"))


@bp.route("/<int:meeting_id>/folgetermin", methods=["POST"])
def followup(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    values = parse_or_flash({"date": forms.Date("Datum", required=True),
                             "time": forms.Time("Uhrzeit", required=True)})
    if values is None:
        return redirect(url_for("meetings.detail", meeting_id=meeting_id))
    values.update(title=meeting["title"], project_id=meeting["project_id"],
                  firm_id=meeting["firm_id"], duration_min=meeting["duration_min"],
                  location=meeting["location"], participants=meeting["participants"])
    new_id = _insert_meeting(db, meeting["type"], values, previous_id=meeting_id)
    db.commit()
    flash(f"Folgetermin am {util.fmt_datetime(values['date'] + ' ' + values['time'])} angelegt.",
          "ok")
    return redirect(url_for("meetings.detail", meeting_id=meeting_id, _anchor="folgetermin")
                    if meeting["protocol_status"] == "offen"
                    else url_for("meetings.detail", meeting_id=new_id))


@bp.route("/<int:meeting_id>/abschliessen", methods=["POST"])
def finalize(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    blocked = _require_open(meeting)
    if blocked:
        return blocked
    try:
        values = _save_editor(db, meeting, extra_allowed={"send"})
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("meetings.detail", meeting_id=meeting_id))
    meeting = _load(db, meeting_id)
    version = meeting["version"] + 1
    snapshot = build_snapshot(db, meeting, version)
    db.execute("INSERT INTO protocol_versions (meeting_id, version, snapshot_json, finalized_at) "
               "VALUES (?, ?, ?, ?)",
               (meeting_id, version, json.dumps(snapshot, ensure_ascii=False), util.stamp()))
    db.execute("UPDATE meetings SET protocol_status = 'abgeschlossen', version = ?, "
               "updated_at = ? WHERE id = ?", (version, util.stamp(), meeting_id))
    db.commit()
    flash(f"Protokoll abgeschlossen (Version {version}).", "ok")
    if request.form.get("send") == "1":
        _send(db, meeting_id, snapshot, recipients(values["participants"]))
    return redirect(url_for("meetings.detail", meeting_id=meeting_id))


def _send(db, meeting_id, snapshot, to):
    if not notify.smtp_configured():
        flash("E-Mail-Versand ist nicht eingerichtet (siehe Einstellungen).", "error")
        return
    if not to:
        flash("Keine E-Mail-Adressen bei den Teilnehmenden eingetragen.", "error")
        return
    try:
        notify.send_email(to, f"Protokoll: {snapshot['title']} ({snapshot['when']})",
                          snapshot_text(snapshot))
    except Exception as exc:
        log.warning("Protokoll-Versand fehlgeschlagen: %s", type(exc).__name__)
        flash("Das Protokoll konnte nicht versendet werden. Bitte E-Mail-Einstellungen prüfen.",
              "error")
        return
    db.execute("UPDATE protocol_versions SET sent_to = ? WHERE meeting_id = ? AND version = ?",
               (", ".join(to), meeting_id, snapshot["version"]))
    db.commit()
    flash(f"Protokoll an {len(to)} Empfänger versendet.", "ok")


@bp.route("/<int:meeting_id>/senden", methods=["POST"])
def resend(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    row = db.execute("SELECT snapshot_json FROM protocol_versions WHERE meeting_id = ? "
                     "ORDER BY version DESC LIMIT 1", (meeting_id,)).fetchone()
    if not row or meeting["protocol_status"] != "abgeschlossen":
        flash("Es gibt noch kein abgeschlossenes Protokoll.", "error")
    else:
        _send(db, meeting_id, json.loads(row["snapshot_json"]),
              recipients(meeting["participants"]))
    return redirect(url_for("meetings.detail", meeting_id=meeting_id))


@bp.route("/<int:meeting_id>/korrektur", methods=["POST"])
def correction(meeting_id):
    db = get_db()
    _load(db, meeting_id)
    db.execute("UPDATE meetings SET protocol_status = 'offen', updated_at = ? WHERE id = ?",
               (util.stamp(), meeting_id))
    db.commit()
    flash("Korrektur begonnen. Beim nächsten Abschluss entsteht eine neue Version.", "ok")
    return redirect(url_for("meetings.detail", meeting_id=meeting_id))


@bp.route("/<int:meeting_id>/druck")
def print_view(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    version = request.args.get("version", type=int)
    row = None
    if version:
        row = db.execute("SELECT snapshot_json FROM protocol_versions WHERE meeting_id = ? "
                         "AND version = ?", (meeting_id, version)).fetchone()
        if not row:
            abort(404)
    elif meeting["protocol_status"] == "abgeschlossen":
        row = db.execute("SELECT snapshot_json FROM protocol_versions WHERE meeting_id = ? "
                         "ORDER BY version DESC LIMIT 1", (meeting_id,)).fetchone()
    snapshot = json.loads(row["snapshot_json"]) if row else build_snapshot(db, meeting, 0)
    return render_template("meetings/print.html", snapshot=snapshot, meeting=meeting,
                           draft=row is None)


@bp.route("/<int:meeting_id>/loeschen", methods=["POST"])
def delete(meeting_id):
    db = get_db()
    meeting = _load(db, meeting_id)
    if meeting["version"] > 0:
        flash("Meetings mit abgeschlossenem Protokoll können nicht gelöscht werden.", "error")
        return redirect(url_for("meetings.detail", meeting_id=meeting_id))
    db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    db.commit()
    flash("Meeting gelöscht.", "ok")
    return redirect(url_for("meetings.index"))
