"""Appearance (same options as the Projekt-Cockpit), profile and goals, password."""

from flask import Blueprint, flash, g, redirect, render_template, url_for

from .. import auth, forms, settings, themes
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
    return render_template("einstellungen.html", values=settings.get_all(get_db()),
                           retention=RETENTION)


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


@bp.route("/ziele", methods=["POST"])
def save_goals():
    values = parse_or_flash({
        "height_cm": forms.Integer("Größe", min_value=100, max_value=250),
        "goal_steps": forms.Integer("Schritte am Tag", required=True, min_value=500,
                                    max_value=100000),
        "goal_active_min": forms.Integer("Aktive Minuten", required=True, min_value=5,
                                         max_value=600),
        "goal_active_kcal": forms.Integer("Aktivkalorien", required=True, min_value=50,
                                          max_value=5000),
        "goal_sleep_h": forms.Number("Schlaf", required=True, min_value=4, max_value=12),
        "goal_weight": forms.Number("Zielgewicht", min_value=30, max_value=300),
    })
    if values is not None:
        db = get_db()
        settings.put(db, "height_cm", values["height_cm"])
        for key in ("goal_steps", "goal_active_min", "goal_active_kcal"):
            settings.put(db, key, values[key])
        settings.put(db, "goal_sleep_min", round(values["goal_sleep_h"] * 60))
        settings.put(db, "goal_weight_dg",
                     round(values["goal_weight"] * 10) if values["goal_weight"] else None)
        db.commit()
        flash("Profil und Ziele gespeichert.", "ok")
    return redirect(url_for("einstellungen.index") + "#ziele")


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
