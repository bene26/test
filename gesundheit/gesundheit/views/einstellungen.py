"""Appearance (same options as the Projekt-Cockpit) and password. Goals: see personen.py."""

from flask import Blueprint, flash, g, redirect, render_template, url_for

from .. import auth, forms, themes
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("einstellungen", __name__, url_prefix="/einstellungen")

APPEARANCE_FIELDS = {
    "theme": forms.Choice("Design", themes.THEMES, required=True),
    **{key: forms.Choice(themes.LABELS[key], options)
       for key, (_attr, options) in themes.APPEARANCE.items()},
}
RETENTION = {0: "Unbegrenzt", 365: "1 Jahr", 730: "2 Jahre", 1825: "5 Jahre", 3650: "10 Jahre"}


@bp.route("")
def index():
    return render_template("einstellungen.html")


@bp.route("/darstellung", methods=["POST"])
def save_theme():
    values = parse_or_flash(APPEARANCE_FIELDS)
    if values is not None:
        look = themes.clean_look({k: values[k] or "" for k in themes.APPEARANCE})
        db = get_db()
        db.execute("UPDATE users SET theme = ?, appearance = ? WHERE id = ?",
                   (values["theme"], themes.dump_look(look), g.user["id"]))
        db.commit()
        g.user["theme"] = values["theme"]
        g.user["appearance"] = themes.dump_look(look)
        flash(f"Darstellung gespeichert: {themes.THEMES[values['theme']]['label']}.", "ok")
    return redirect(url_for("einstellungen.index") + "#darstellung")


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
    return redirect(url_for("einstellungen.index") + "#passwort")
