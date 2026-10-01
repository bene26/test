"""Reports: project status for management, protocol archive, exports."""

import logging
import re
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import data, forms, notify, quotas, reports, util
from ..db import get_db
from . import csv_response, parse_or_flash
from .times import month_range

log = logging.getLogger("cockpit")

bp = Blueprint("reports", __name__, url_prefix="/berichte")


def _months(today, count=13):
    first = today.replace(day=1)
    result = []
    for _ in range(count):
        result.append((first.strftime("%Y-%m"), reports.month_label(first)))
        first = (first - timedelta(days=1)).replace(day=1)
    return result


@bp.route("")
def index():
    db = get_db()
    today = util.today()
    project_id = request.args.get("projekt", type=int)
    month = request.args.get("monat", "")
    where, params = ["m.protocol_status = 'abgeschlossen'"], []
    if project_id:
        where.append("m.project_id = ?")
        params.append(project_id)
    if re.fullmatch(r"\d{4}-\d{2}", month):
        first, last = month_range(month, today)
        where.append("m.starts_at >= ? AND m.starts_at < ?")
        params += [first.isoformat(), (last + timedelta(days=1)).isoformat()]
    protocols = db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name, "
        "(SELECT sent_to FROM protocol_versions v WHERE v.meeting_id = m.id "
        " ORDER BY v.version DESC LIMIT 1) AS sent_to FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE " + " AND ".join(where) + " ORDER BY m.starts_at DESC LIMIT 200", params).fetchall()
    return render_template("reports/index.html", protocols=protocols, months=_months(today),
                           projects=data.project_options(db), project_id=project_id,
                           month=month, this_month=today.strftime("%Y-%m"))


@bp.route("/status")
def status():
    db = get_db()
    today = util.today()
    first, last = month_range(request.args.get("monat"), today)
    project_id = request.args.get("projekt", type=int)
    items = reports.build(db, today, first, last, project_id)
    return render_template("reports/status.html", reports=items, first=first, last=last,
                           title=reports.month_label(first), lights=reports.LIGHTS,
                           project_id=project_id, month=first.strftime("%Y-%m"),
                           smtp=notify.smtp_configured(), fmt=quotas.fmt_amount)


@bp.route("/status/senden", methods=["POST"])
def send_status():
    values = parse_or_flash({
        "monat": forms.Text("Monat", required=True, max_len=7),
        "projekt": forms.Integer("Projekt", min_value=1),
        "recipients": forms.Text("Empfänger", required=True, max_len=2000, multiline=True),
    })
    if values is None:
        return redirect(url_for("reports.index"))
    target = url_for("reports.status", monat=values["monat"], projekt=values["projekt"])
    addresses = [a for a in re.split(r"[\s,;]+", values["recipients"]) if a]
    bad = [a for a in addresses if len(a) > 254 or not forms.EMAIL_RE.match(a)]
    if bad or not addresses or len(addresses) > 20:
        flash("Bitte bis zu 20 gültige E-Mail-Adressen angeben, getrennt durch Komma.", "error")
        return redirect(target)
    if not notify.smtp_configured():
        flash("E-Mail-Versand ist nicht eingerichtet (siehe Einstellungen).", "error")
        return redirect(target)
    db = get_db()
    today = util.today()
    first, last = month_range(values["monat"], today)
    items = reports.build(db, today, first, last, values["projekt"])
    try:
        notify.send_email(addresses, f"Projektstatus {reports.month_label(first)}",
                          reports.as_text(items, first))
    except Exception as exc:
        log.warning("Statusbericht-Versand fehlgeschlagen: %s", type(exc).__name__)
        flash("Der Bericht konnte nicht versendet werden. Bitte E-Mail-Einstellungen prüfen.",
              "error")
        return redirect(target)
    flash(f"Statusbericht an {len(addresses)} Empfänger versendet.", "ok")
    return redirect(target)


@bp.route("/kontingente.csv")
def quotas_csv():
    db = get_db()
    rows = quotas.orders(db, util.today())
    return csv_response(
        f"kontingente-{util.today()}.csv",
        ["Firma", "Bestellnummer", "Bezeichnung", "Projekt", "Einheit", "Menge", "Abgerechnet",
         "Eingereicht", "Frei", "Gültig ab", "Gültig bis", "Aktiv", "Hinweise"],
        ([o["firm_name"], o["number"], o["title"], o["project_name"] or "",
          quotas.UNIT_SHORT[o["unit"]], util.fmt_number(o["amount"]),
          util.fmt_number(o["billed"]), util.fmt_number(o["pending"]),
          util.fmt_number(o["remaining"]), util.fmt_date(o["valid_from"]),
          util.fmt_date(o["valid_to"]), "ja" if o["active"] else "nein",
          "; ".join(o["warnings"])] for o in rows))
