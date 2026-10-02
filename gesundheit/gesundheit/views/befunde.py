"""Findings: everything the rules found for the person shown, with the calculation."""

from flask import Blueprint, flash, g, render_template, request, url_for

from .. import befunde, belastung, util
from ..db import get_db
from . import back

bp = Blueprint("befunde", __name__, url_prefix="/befunde")


@bp.route("")
def index():
    db = get_db()
    findings = befunde.compute(db, g.person["id"], g.person)
    return render_template("befunde.html", findings=findings,
                           form=belastung.form(db, g.person["id"], g.person),
                           seen=set(befunde.seen(g.person)), now=util.now())


@bp.route("/gesehen", methods=["POST"])
def mark_seen():
    """The toast's "Ansehen" and "Schließen": only keys of current findings are stored."""
    db = get_db()
    current = {f.key for f in befunde.compute(db, g.person["id"], g.person)}
    keys = [k for k in request.form.getlist("key") if k in current]
    if keys:
        befunde.mark_seen(db, g.person["id"], g.person, keys)
        db.commit()
    elif request.form.getlist("key"):
        flash("Dieser Befund ist nicht mehr aktuell.", "info")
    return back(url_for("main.index"))
