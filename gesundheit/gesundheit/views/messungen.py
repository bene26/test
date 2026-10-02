"""Enter values by hand: the tape measure and the body analysis at the practice, or a CSV file."""

from datetime import datetime, time

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import forms, messungen, util
from ..db import get_db
from ..katalog import METRICS
from . import csv_response, parse_or_flash

bp = Blueprint("messungen", __name__, url_prefix="/messungen")


def _spec(kind: str) -> dict:
    spec = {"datum": forms.Date("Datum", required=True), "uhrzeit": forms.Time("Uhrzeit")}
    for key in messungen.KINDS[kind]["metrics"]:
        m = METRICS[key]
        spec[key] = forms.Number(m.label, min_value=m.lo, max_value=m.hi)
    return spec


@bp.route("")
def index():
    db = get_db()
    return render_template("messungen.html", kinds=messungen.KINDS,
                           entries=messungen.sessions(db, g.person["id"]),
                           today=util.today().isoformat())


@bp.route("/<kind>", methods=["POST"])
def save(kind):
    if kind not in messungen.KINDS:
        abort(404)
    values = parse_or_flash(_spec(kind))
    if values is not None:
        day = util.to_date(values.pop("datum"))
        clock = values.pop("uhrzeit")
        when = datetime.combine(day, time.fromisoformat(clock) if clock else messungen.DEFAULT_TIME)
        if day > util.today():
            flash("Das Datum liegt in der Zukunft.", "error")
        elif not any(v is not None for v in values.values()):
            flash("Bitte mindestens einen Wert eintragen.", "error")
        else:
            db = get_db()
            _group, count = messungen.save(db, g.person["id"], kind, when, values)
            db.commit()
            flash(f"{count} {'Wert' if count == 1 else 'Werte'} vom {util.fmt_date(day)} für "
                  f"{g.person['name']} gespeichert.", "ok")
    return redirect(url_for("messungen.index") + f"#{kind}")


@bp.route("/import", methods=["POST"])
def upload():
    values = parse_or_flash({"art": forms.Choice("Art", messungen.KINDS, required=True)},
                            extra_allowed={"datei"})
    upload = request.files.get("datei")
    if values is None:
        return redirect(url_for("messungen.index") + "#import")
    if not upload or not upload.filename:
        flash("Bitte eine CSV-Datei auswählen.", "error")
        return redirect(url_for("messungen.index") + "#import")
    raw = upload.stream.read(messungen.CSV_MAX_BYTES + 1)
    db = get_db()
    try:
        result = messungen.import_csv(db, g.person["id"], values["art"], raw)
    except messungen.ImportError_ as exc:
        flash(str(exc), "error")
        return redirect(url_for("messungen.index") + "#import")
    db.commit()
    parts = [f"{result['entries']} Einträge mit {result['values']} Werten übernommen"]
    if result["skipped"]:
        parts.append(f"{result['skipped']} Zeilen ohne gültiges Datum oder Wert übersprungen")
    if result["dropped"]:
        parts.append(f"{result['dropped']} Werte außerhalb des möglichen Bereichs oder der "
                     "falschen Art weggelassen")
    if result["unknown"]:
        shown = ", ".join(result["unknown"][:6])
        parts.append(f"unbekannte Spalten ignoriert: {shown}")
    flash(". ".join(parts) + ".", "ok" if result["values"] else "error")
    return redirect(url_for("messungen.index") + "#eintraege")


@bp.route("/loeschen", methods=["POST"])
def delete():
    values = parse_or_flash({"eintrag": forms.Text("Eintrag", required=True, max_len=40)})
    if values is not None:
        db = get_db()
        count = messungen.delete(db, g.person["id"], values["eintrag"])
        db.commit()
        flash(f"Eintrag mit {count} Werten gelöscht." if count else "Eintrag nicht gefunden.",
              "ok" if count else "error")
    return redirect(url_for("messungen.index") + "#eintraege")


@bp.route("/vorlage-<kind>.csv")
def template(kind):
    if kind not in messungen.KINDS:
        abort(404)
    header, example = messungen.template(kind)
    return csv_response(f"vorlage-{kind}.csv", header, [example])
