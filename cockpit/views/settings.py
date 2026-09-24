"""Reminder times, channel test, password change and database download."""

import io
import os
import sqlite3
import tempfile
from pathlib import Path

from flask import (Blueprint, current_app, flash, g, redirect, render_template, send_file,
                   url_for)

from .. import auth, data, forms, notify, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("settings", __name__, url_prefix="/einstellungen")

REMINDER_FIELDS = {
    "reminders_enabled": forms.Checkbox("Erinnerungen aktiv"),
    "digest_time": forms.Time("Morgen-Zusammenfassung", required=True),
    "weekly_planning_time": forms.Time("Wochenplanung (Mo–Mi)", required=True),
    "weekly_review_time": forms.Time("Wochenabschluss (Fr)", required=True),
    "prep_time": forms.Time("Meetings vorbereiten (Vortag)", required=True),
    "monthly_time": forms.Time("Monatsbericht", required=True),
    "stale_days": forms.Integer("Ohne Update nach", required=True, min_value=1, max_value=60),
}


@bp.route("")
def index():
    db = get_db()
    backups_dir = Path(current_app.config["DATA_DIR"]) / "backups"
    backups = sorted(backups_dir.glob("cockpit-*.sqlite3"), reverse=True) \
        if backups_dir.exists() else []
    return render_template(
        "settings.html", settings=data.settings(db),
        ntfy=notify.ntfy_configured(), smtp=notify.smtp_configured(),
        reminder_email=notify.reminder_email_configured(),
        base_url=current_app.config["BASE_URL"],
        backups=[{"name": b.name, "size": b.stat().st_size} for b in backups],
        scheduler=current_app.config["SCHEDULER"],
    )


@bp.route("/erinnerungen", methods=["POST"])
def save_reminders():
    values = parse_or_flash(REMINDER_FIELDS)
    if values is not None:
        db = get_db()
        for key, value in values.items():
            stored = "1" if value is True else "0" if value is False else str(value)
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, stored))
        db.commit()
        flash("Erinnerungen gespeichert.", "ok")
    return redirect(url_for("settings.index"))


@bp.route("/test", methods=["POST"])
def test_notification():
    channels = notify.remind("Testnachricht", "Die Erinnerungen vom Projekt-Cockpit kommen an.",
                             current_app.config["BASE_URL"])
    if channels:
        flash("Testnachricht gesendet über: " + ", ".join(
            {"ntfy": "Push (ntfy)", "email": "E-Mail"}[c] for c in channels) + ".", "ok")
    else:
        flash("Es wurde nichts gesendet. Entweder ist kein Kanal eingerichtet oder der Versand "
              "ist fehlgeschlagen (Details im Container-Log).", "error")
    return redirect(url_for("settings.index"))


@bp.route("/passwort", methods=["POST"])
def change_password():
    values = parse_or_flash({
        "current": forms.Text("Aktuelles Passwort", required=True, max_len=200),
        "new": forms.Text("Neues Passwort", required=True, max_len=200),
        "new2": forms.Text("Neues Passwort wiederholen", required=True, max_len=200),
    })
    if values is not None:
        db = get_db()
        try:
            auth.change_password(db, g.user["id"], values["current"], values["new"],
                                 values["new2"])
        except forms.ValidationError as exc:
            flash(str(exc), "error")
        else:
            db.commit()
            flash("Passwort geändert. Andere Geräte wurden abgemeldet.", "ok")
    return redirect(url_for("settings.index"))


@bp.route("/sicherung")
def download_backup():
    """Consistent copy of the live database for download."""
    db = get_db()
    fd, tmp = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    try:
        dest = sqlite3.connect(tmp)
        try:
            db.backup(dest)
        finally:
            dest.close()
        payload = io.BytesIO(Path(tmp).read_bytes())
    finally:
        os.unlink(tmp)
    return send_file(payload, mimetype="application/vnd.sqlite3", as_attachment=True,
                     download_name=f"projekt-cockpit-{util.today()}.sqlite3")
