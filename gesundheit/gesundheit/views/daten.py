"""Your data: overview per source, CSV export, retention, deleting."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for

from .. import forms, settings, store, util
from ..db import get_db
from ..katalog import METRICS, SOURCES, WORKOUT_KINDS, source_label
from . import csv_response, parse_or_flash
from .einstellungen import RETENTION

bp = Blueprint("daten", __name__, url_prefix="/daten")
EXPORTS = {"werte": "Messwerte und Tageswerte", "schlaf": "Schlaf", "trainings": "Trainings"}


@bp.route("")
def index():
    db = get_db()
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in store.HEALTH_TABLES}
    return render_template("daten.html", overview=store.sources_overview(db), counts=counts,
                           exports=EXPORTS, retention=RETENTION,
                           retention_days=settings.get(db, "retention_days"))


@bp.route("/export/<name>.csv")
def export(name):
    if name not in EXPORTS:
        abort(404)
    db = get_db()
    stamp = util.today().isoformat()
    if name == "werte":
        def rows():
            for r in db.execute("SELECT metric, value, measured_at, source FROM measurements "
                                "ORDER BY measured_at"):
                meta = METRICS.get(r["metric"])
                yield (r["measured_at"][:10], r["measured_at"][11:16], meta.label if meta else
                       r["metric"], util.csv_number(r["value"]), meta.unit if meta else "",
                       "Einzelwert", source_label(r["source"]))
            for r in db.execute("SELECT metric, day, value, source FROM daily_values "
                                "ORDER BY day"):
                meta = METRICS.get(r["metric"])
                yield (r["day"], "", meta.label if meta else r["metric"],
                       util.csv_number(r["value"]), meta.unit if meta else "", "Tageswert",
                       source_label(r["source"]))
        return csv_response(f"gesundheit-werte-{stamp}.csv",
                            ["Datum", "Uhrzeit", "Wert", "Zahl", "Einheit", "Art", "Quelle"],
                            rows())
    if name == "schlaf":
        rows = ((r["night"], r["bed_start"] or "", r["bed_end"] or "", r["asleep_min"],
                 r["deep_min"], r["light_min"], r["rem_min"], r["awake_min"], r["score"],
                 util.csv_number(r["hr_avg"]), util.csv_number(r["rr_avg"]),
                 source_label(r["source"]))
                for r in db.execute("SELECT * FROM sleep ORDER BY night"))
        return csv_response(f"gesundheit-schlaf-{stamp}.csv",
                            ["Nacht auf", "Im Bett ab", "Aufgestanden", "Schlaf (min)",
                             "Tief (min)", "Leicht (min)", "REM (min)", "Wach (min)",
                             "Bewertung", "Puls", "Atemfrequenz", "Quelle"], rows)
    rows = ((r["started_at"], r["ended_at"] or "", WORKOUT_KINDS.get(r["kind"], r["kind"]),
             util.csv_number(r["duration_min"]), util.csv_number(r["distance_km"]),
             util.csv_number(r["energy_kcal"]), util.csv_number(r["hr_avg"]),
             util.csv_number(r["hr_max"]), source_label(r["source"]))
            for r in db.execute("SELECT * FROM workouts ORDER BY started_at"))
    return csv_response(f"gesundheit-trainings-{stamp}.csv",
                        ["Beginn", "Ende", "Art", "Dauer (min)", "Strecke (km)", "kcal",
                         "Puls Durchschnitt", "Puls max", "Quelle"], rows)


@bp.route("/aufbewahrung", methods=["POST"])
def save_retention():
    values = parse_or_flash({"tage": forms.Choice("Aufbewahrung", RETENTION, required=True)})
    if values is not None:
        db = get_db()
        days = int(values["tage"])
        settings.put(db, "retention_days", days)
        removed = store.apply_retention(db, days)
        db.commit()
        flash(f"Aufbewahrung: {RETENTION[days]}."
              + (f" {removed} ältere Werte wurden gelöscht." if removed else ""), "ok")
    return redirect(url_for("daten.index") + "#aufbewahrung")


def _vacuum(db):
    db.commit()
    db.execute("VACUUM")


@bp.route("/loeschen/quelle", methods=["POST"])
def delete_source():
    values = parse_or_flash({"quelle": forms.Choice("Quelle", SOURCES, required=True)})
    if values is not None:
        db = get_db()
        removed = store.delete_source(db, values["quelle"])
        _vacuum(db)
        flash(f"{removed} Werte von „{source_label(values['quelle'])}“ gelöscht.", "ok")
    return redirect(url_for("daten.index"))


@bp.route("/loeschen/alles", methods=["POST"])
def delete_everything():
    values = parse_or_flash({"bestaetigung": forms.Text("Bestätigung", required=True,
                                                        max_len=20)})
    if values is not None:
        if values["bestaetigung"].strip().upper() != "LÖSCHEN":
            flash("Zur Bestätigung bitte genau LÖSCHEN eintippen.", "error")
        else:
            db = get_db()
            removed = store.delete_all(db)
            _vacuum(db)
            current_app.logger.info("Alle Gesundheitsdaten gelöscht.")
            flash(f"Alles gelöscht: {removed} Werte, alle Verbindungen und Importe. Dein Konto "
                  "bleibt bestehen.", "ok")
    return redirect(url_for("daten.index"))
