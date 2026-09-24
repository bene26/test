"""Internal people and external firms."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import data, forms, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("team", __name__, url_prefix="/team")

PERSON_FIELDS = {
    "name": forms.Text("Name", required=True, max_len=120),
    "role": forms.Text("Rolle", max_len=80),
    "email": forms.Email("E-Mail"),
    "weekly_hours": forms.Number("Wochenstunden", min_value=1, max_value=80),
    "availability": forms.Integer("Verfügbarkeit", min_value=10, max_value=100),
    "firm_id": forms.Integer("Firma", min_value=1),
    "active": forms.Checkbox("Aktiv"),
}

FIRM_FIELDS = {
    "name": forms.Text("Name", required=True, max_len=150),
    "contract_type": forms.Choice("Vertragsart", util.CONTRACT_TYPES, required=True),
    "contact_name": forms.Text("Ansprechpartner", max_len=120),
    "contact_email": forms.Email("E-Mail"),
    "contact_phone": forms.Text("Telefon", max_len=40),
    "notes": forms.Text("Notizen", max_len=5000, multiline=True),
    "active": forms.Checkbox("Aktiv"),
}


def _check_person_firm(db, firm_id):
    """External staff may only be planned individually under Arbeitnehmerüberlassung."""
    if firm_id is None:
        return
    firm = db.execute("SELECT contract_type FROM firms WHERE id = ?", (firm_id,)).fetchone()
    if not firm:
        raise forms.ValidationError("Die Firma gibt es nicht.")
    if firm["contract_type"] != "anue":
        raise forms.ValidationError(
            "Personen externer Firmen können nur bei Arbeitnehmerüberlassung einzeln geplant "
            "werden. Bei Werk- oder Dienstvertrag gehen Aufgaben an die Firma.")


def _person_row(values):
    return (values["name"], values["role"], values["email"], values["weekly_hours"] or 40,
            (values["availability"] or 80) / 100, values["firm_id"])


@bp.route("")
def index():
    db = get_db()
    people = db.execute(
        "SELECT pe.*, f.name AS firm_name, "
        f"(SELECT COUNT(*) FROM tasks t WHERE t.person_id = pe.id AND t.status IN {data.OPEN_SQL}) "
        "  AS open_tasks "
        "FROM people pe LEFT JOIN firms f ON f.id = pe.firm_id "
        "ORDER BY pe.active DESC, f.name IS NOT NULL, f.name, pe.name").fetchall()
    firms = db.execute(
        "SELECT f.*, "
        f"(SELECT COUNT(*) FROM tasks t WHERE t.firm_id = f.id AND t.status IN {data.OPEN_SQL}) "
        "  AS open_tasks "
        "FROM firms f ORDER BY f.active DESC, f.name").fetchall()
    anue_firms = [f for f in firms if f["contract_type"] == "anue"]
    return render_template("team/index.html", people=people, firms=firms, anue_firms=anue_firms)


@bp.route("/personen/neu", methods=["POST"])
def create_person():
    values = parse_or_flash(PERSON_FIELDS)
    if values is None:
        return redirect(url_for("team.index"))
    db = get_db()
    try:
        _check_person_firm(db, values["firm_id"])
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("team.index"))
    now = util.stamp()
    db.execute(
        "INSERT INTO people (name, role, email, weekly_hours, availability, firm_id, active, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (*_person_row(values), now, now))
    db.commit()
    flash(f"{values['name']} angelegt.", "ok")
    return redirect(url_for("team.index"))


@bp.route("/personen/<int:person_id>", methods=["GET", "POST"])
def person(person_id):
    db = get_db()
    row = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not row:
        abort(404)
    if request.method == "POST":
        values = parse_or_flash(PERSON_FIELDS)
        if values is not None:
            try:
                _check_person_firm(db, values["firm_id"])
            except forms.ValidationError as exc:
                flash(str(exc), "error")
            else:
                db.execute(
                    "UPDATE people SET name = ?, role = ?, email = ?, weekly_hours = ?, "
                    "availability = ?, firm_id = ?, active = ?, updated_at = ? WHERE id = ?",
                    (*_person_row(values), int(values["active"]), util.stamp(), person_id))
                db.commit()
                flash("Gespeichert.", "ok")
        return redirect(url_for("team.person", person_id=person_id))
    anue_firms = db.execute("SELECT id, name FROM firms WHERE contract_type = 'anue' "
                            "ORDER BY name").fetchall()
    tasks = data.find_tasks(db, util.today(), assignee=(person_id, None))
    return render_template("team/person.html", person=row, anue_firms=anue_firms, tasks=tasks)


@bp.route("/personen/<int:person_id>/loeschen", methods=["POST"])
def delete_person(person_id):
    db = get_db()
    if db.execute("SELECT 1 FROM tasks WHERE person_id = ? LIMIT 1", (person_id,)).fetchone():
        flash("Die Person hat noch Aufgaben. Setze sie stattdessen auf inaktiv.", "error")
        return redirect(url_for("team.person", person_id=person_id))
    db.execute("DELETE FROM people WHERE id = ?", (person_id,))
    db.commit()
    flash("Person gelöscht.", "ok")
    return redirect(url_for("team.index"))


@bp.route("/firmen/neu", methods=["POST"])
def create_firm():
    values = parse_or_flash(FIRM_FIELDS)
    if values is None:
        return redirect(url_for("team.index"))
    db = get_db()
    if db.execute("SELECT 1 FROM firms WHERE name = ?", (values["name"],)).fetchone():
        flash("Eine Firma mit diesem Namen gibt es schon.", "error")
        return redirect(url_for("team.index"))
    now = util.stamp()
    db.execute(
        "INSERT INTO firms (name, contract_type, contact_name, contact_email, contact_phone, "
        "notes, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (values["name"], values["contract_type"], values["contact_name"],
         values["contact_email"], values["contact_phone"], values["notes"], now, now))
    db.commit()
    flash(f"{values['name']} angelegt.", "ok")
    return redirect(url_for("team.index"))


@bp.route("/firmen/<int:firm_id>", methods=["GET", "POST"])
def firm(firm_id):
    db = get_db()
    row = db.execute("SELECT * FROM firms WHERE id = ?", (firm_id,)).fetchone()
    if not row:
        abort(404)
    if request.method == "POST":
        values = parse_or_flash(FIRM_FIELDS)
        if values is not None:
            staff = db.execute("SELECT COUNT(*) FROM people WHERE firm_id = ?",
                               (firm_id,)).fetchone()[0]
            clash = db.execute("SELECT 1 FROM firms WHERE name = ? AND id != ?",
                               (values["name"], firm_id)).fetchone()
            if staff and values["contract_type"] != "anue":
                flash("Dieser Firma sind noch Personen zugeordnet. Die Vertragsart kann erst "
                      "geändert werden, wenn die Personen entfernt sind.", "error")
            elif clash:
                flash("Eine Firma mit diesem Namen gibt es schon.", "error")
            else:
                db.execute(
                    "UPDATE firms SET name = ?, contract_type = ?, contact_name = ?, "
                    "contact_email = ?, contact_phone = ?, notes = ?, active = ?, updated_at = ? "
                    "WHERE id = ?",
                    (values["name"], values["contract_type"], values["contact_name"],
                     values["contact_email"], values["contact_phone"], values["notes"],
                     int(values["active"]), util.stamp(), firm_id))
                db.commit()
                flash("Gespeichert.", "ok")
        return redirect(url_for("team.firm", firm_id=firm_id))
    today = util.today()
    meetings = db.execute(
        "SELECT m.*, p.name AS project_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id WHERE m.firm_id = ? "
        "ORDER BY m.starts_at DESC LIMIT 50", (firm_id,)).fetchall()
    staff = db.execute("SELECT * FROM people WHERE firm_id = ? ORDER BY name",
                       (firm_id,)).fetchall()
    return render_template("team/firm.html", firm=row, meetings=meetings, staff=staff,
                           tasks=data.find_tasks(db, today, assignee=(None, firm_id)))


@bp.route("/firmen/<int:firm_id>/loeschen", methods=["POST"])
def delete_firm(firm_id):
    db = get_db()
    used = db.execute(
        "SELECT (SELECT COUNT(*) FROM tasks WHERE firm_id = ?) + "
        "(SELECT COUNT(*) FROM people WHERE firm_id = ?) + "
        "(SELECT COUNT(*) FROM meetings WHERE firm_id = ?)", (firm_id, firm_id, firm_id)
    ).fetchone()[0]
    if used:
        flash("Die Firma hat noch Aufgaben, Personen oder Meetings. Setze sie stattdessen auf "
              "inaktiv.", "error")
        return redirect(url_for("team.firm", firm_id=firm_id))
    db.execute("DELETE FROM firms WHERE id = ?", (firm_id,))
    db.commit()
    flash("Firma gelöscht.", "ok")
    return redirect(url_for("team.index"))
