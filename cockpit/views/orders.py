"""Orders with quotas of external firms and their service records."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import data, forms, quotas, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("orders", __name__, url_prefix="/bestellungen")

ORDER_FIELDS = {
    "number": forms.Text("Bestellnummer", max_len=40),
    "title": forms.Text("Bezeichnung", required=True, max_len=150),
    "project_id": forms.Integer("Projekt", min_value=1),
    "unit": forms.Choice("Einheit", quotas.UNITS, required=True),
    "amount": forms.Number("Menge", required=True, min_value=0.25, max_value=999999),
    "hours_per_day": forms.Number("Stunden je Personentag", min_value=1, max_value=24),
    "valid_from": forms.Date("Gültig ab"),
    "valid_to": forms.Date("Gültig bis"),
    "notes": forms.Text("Notizen", max_len=2000, multiline=True),
    "active": forms.Checkbox("Aktiv"),
}
RECORD_FIELDS = {
    "period_start": forms.Date("Zeitraum von", required=True),
    "period_end": forms.Date("Zeitraum bis", required=True),
    "amount": forms.Number("Menge", required=True, min_value=0.25, max_value=100000),
    "description": forms.Text("Leistung", max_len=500),
    "status": forms.Choice("Status", quotas.RECORD_STATUS),
}


def _order_row(db, values) -> tuple:
    if values["project_id"] and not db.execute("SELECT 1 FROM projects WHERE id = ?",
                                               (values["project_id"],)).fetchone():
        raise forms.ValidationError("Das Projekt gibt es nicht.")
    if values["valid_from"] and values["valid_to"] and values["valid_to"] < values["valid_from"]:
        raise forms.ValidationError("„Gültig bis“ liegt vor „Gültig ab“.")
    return (values["number"], values["title"], values["project_id"], values["unit"],
            values["amount"], values["hours_per_day"] or 8, values["valid_from"],
            values["valid_to"], values["notes"])


def _record_row(values) -> tuple:
    if values["period_end"] < values["period_start"]:
        raise forms.ValidationError("Das Ende des Zeitraums liegt vor dem Anfang.")
    return (values["period_start"], values["period_end"], values["amount"],
            values["description"], values["status"] or "eingereicht")


@bp.route("/neu/<int:firm_id>", methods=["POST"])
def create(firm_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM firms WHERE id = ?", (firm_id,)).fetchone():
        abort(404)
    values = parse_or_flash(ORDER_FIELDS)
    if values is not None:
        try:
            row = _order_row(db, values)
        except forms.ValidationError as exc:
            flash(str(exc), "error")
        else:
            now = util.stamp()
            cur = db.execute(
                "INSERT INTO orders (number, title, project_id, unit, amount, hours_per_day, "
                "valid_from, valid_to, notes, firm_id, active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)", (*row, firm_id, now, now))
            db.commit()
            flash("Bestellung angelegt.", "ok")
            return redirect(url_for("orders.detail", order_id=cur.lastrowid))
    return redirect(url_for("team.firm", firm_id=firm_id) + "#bestellungen")


@bp.route("/<int:order_id>", methods=["GET", "POST"])
def detail(order_id):
    db = get_db()
    today = util.today()
    o = quotas.order(db, order_id, today)
    if not o:
        abort(404)
    if request.method == "POST":
        values = parse_or_flash(ORDER_FIELDS)
        if values is not None:
            try:
                row = _order_row(db, values)
            except forms.ValidationError as exc:
                flash(str(exc), "error")
            else:
                db.execute(
                    "UPDATE orders SET number = ?, title = ?, project_id = ?, unit = ?, "
                    "amount = ?, hours_per_day = ?, valid_from = ?, valid_to = ?, notes = ?, "
                    "active = ?, updated_at = ? WHERE id = ?",
                    (*row, int(values["active"]), util.stamp(), order_id))
                db.commit()
                flash("Gespeichert.", "ok")
        return redirect(url_for("orders.detail", order_id=order_id))
    records = db.execute("SELECT * FROM service_records WHERE order_id = ? "
                         "ORDER BY period_start DESC, id DESC", (order_id,)).fetchall()
    tasks = data.find_tasks(db, today, assignee=(None, o["firm_id"]),
                            project=str(o["project_id"]) if o["project_id"] else None)
    return render_template("orders/detail.html", o=o, records=records, tasks=tasks,
                           projects=data.project_options(db, o["project_id"]),
                           units=quotas.UNITS, record_status=quotas.RECORD_STATUS,
                           fmt=quotas.fmt_amount)


@bp.route("/<int:order_id>/loeschen", methods=["POST"])
def delete(order_id):
    db = get_db()
    row = db.execute("SELECT firm_id FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        abort(404)
    if db.execute("SELECT 1 FROM service_records WHERE order_id = ? LIMIT 1",
                  (order_id,)).fetchone():
        flash("Zu dieser Bestellung gibt es Leistungsnachweise. Setze sie stattdessen auf "
              "inaktiv.", "error")
        return redirect(url_for("orders.detail", order_id=order_id))
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    db.commit()
    flash("Bestellung gelöscht.", "ok")
    return redirect(url_for("team.firm", firm_id=row["firm_id"]) + "#bestellungen")


@bp.route("/<int:order_id>/nachweise", methods=["POST"])
def add_record(order_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone():
        abort(404)
    values = parse_or_flash(RECORD_FIELDS)
    if values is not None:
        try:
            row = _record_row(values)
        except forms.ValidationError as exc:
            flash(str(exc), "error")
        else:
            now = util.stamp()
            db.execute(
                "INSERT INTO service_records (period_start, period_end, amount, description, "
                "status, order_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (*row, order_id, now, now))
            db.commit()
            flash("Leistungsnachweis eingetragen.", "ok")
    return redirect(url_for("orders.detail", order_id=order_id) + "#nachweise")


@bp.route("/nachweise/<int:record_id>/status", methods=["POST"])
def record_status(record_id):
    db = get_db()
    row = db.execute("SELECT order_id FROM service_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        abort(404)
    values = parse_or_flash({"status": forms.Choice("Status", quotas.RECORD_STATUS,
                                                    required=True)})
    if values is not None:
        db.execute("UPDATE service_records SET status = ?, updated_at = ? WHERE id = ?",
                   (values["status"], util.stamp(), record_id))
        db.commit()
        flash(f"Status: {quotas.RECORD_STATUS[values['status']]}.", "ok")
    return redirect(url_for("orders.detail", order_id=row["order_id"]) + "#nachweise")


@bp.route("/nachweise/<int:record_id>/loeschen", methods=["POST"])
def delete_record(record_id):
    db = get_db()
    row = db.execute("SELECT order_id FROM service_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        abort(404)
    db.execute("DELETE FROM service_records WHERE id = ?", (record_id,))
    db.commit()
    flash("Leistungsnachweis gelöscht.", "ok")
    return redirect(url_for("orders.detail", order_id=row["order_id"]) + "#nachweise")
