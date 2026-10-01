"""Start page with configurable widgets, routine check-off and health check."""

import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import dashboard, data, forms, util
from ..db import get_db
from . import parse_or_flash

bp = Blueprint("main", __name__)

LAYOUT_FIELDS = {
    "order": forms.KeyList("Reihenfolge", dashboard.WIDGETS),
    "show": forms.KeyList("Anzeigen", dashboard.WIDGETS),
    "wide": forms.KeyList("Breit", dashboard.WIDGETS),
    "move": forms.Text("Verschieben", max_len=40),
    "reset": forms.Checkbox("Zurücksetzen"),
    "done": forms.Checkbox("Fertig"),
}


@bp.route("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return "ok", 200, {"Content-Type": "text/plain"}


@bp.route("/", endpoint="dashboard")
def dashboard_view():
    db = get_db()
    now = util.now()
    editing = request.args.get("anpassen") == "1"
    layout = dashboard.load(g.user.get("dashboard", ""))
    ctx = dashboard.context(db, now, layout, request.args, editing)
    return render_template("dashboard.html", layout=layout, widgets=dashboard.WIDGETS,
                           editing=editing, **ctx)


@bp.route("/startseite", methods=["POST"])
def save_layout():
    values = parse_or_flash(LAYOUT_FIELDS)
    if values is None:
        return redirect(url_for("main.dashboard", anpassen=1))
    move = values["move"]
    if move and not re.fullmatch(r"[a-z_]{1,30}:(up|down)", move):
        flash("Ungültige Aktion.", "error")
        return redirect(url_for("main.dashboard", anpassen=1))
    if values["reset"]:
        layout = dashboard.default_layout()
    else:
        layout = dashboard.apply_form(values["order"], set(values["show"]), set(values["wide"]),
                                      move)
    db = get_db()
    db.execute("UPDATE users SET dashboard = ? WHERE id = ?",
               (dashboard.dump(layout), g.user["id"]))
    db.commit()
    if values["done"]:
        flash("Startseite gespeichert.", "ok")
        return redirect(url_for("main.dashboard"))
    if values["reset"]:
        flash("Startseite auf den Standard zurückgesetzt.", "ok")
        return redirect(url_for("main.dashboard"))
    anchor = "#w-" + move.split(":")[0] if move else ""
    return redirect(url_for("main.dashboard", anpassen=1) + anchor)


@bp.route("/routine/<key>/<period>/erledigt", methods=["POST"])
def routine_done(key, period):
    if key not in data.ROUTINES or not re.fullmatch(r"\d{4}-(W\d{2}|\d{2})", period):
        abort(404)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO routine_checks (routine, period, done_at) VALUES (?, ?, ?)",
        (key, period, util.stamp()),
    )
    db.commit()
    flash(f"{data.ROUTINES[key]['label']} erledigt.", "ok")
    return redirect(url_for("main.dashboard"))
