"""Outlook: how the values of the person shown could go on, positive and negative."""

from flask import Blueprint, g, render_template, request

from .. import ausblick, util
from ..db import get_db

bp = Blueprint("ausblick", __name__, url_prefix="/ausblick")


@bp.route("")
def index():
    try:
        weeks = int(request.args.get("wochen", ausblick.DEFAULT_HORIZON))
    except ValueError:
        weeks = ausblick.DEFAULT_HORIZON
    if weeks not in ausblick.HORIZONS:
        weeks = ausblick.DEFAULT_HORIZON
    outlooks = ausblick.all_outlooks(get_db(), g.person["id"], g.person, util.today(), weeks)
    return render_template("ausblick.html", outlooks=outlooks, weeks=weeks,
                           horizons=ausblick.HORIZONS, horizon_in=ausblick.HORIZONS_IN[weeks])
