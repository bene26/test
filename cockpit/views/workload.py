"""Workload overview derived from open tasks."""

from flask import Blueprint, render_template, request

from .. import data, quotas, util
from ..db import get_db

bp = Blueprint("workload", __name__, url_prefix="/auslastung")


@bp.route("")
def index():
    weeks = request.args.get("wochen", default=6, type=int)
    weeks = weeks if weeks in (4, 6, 8, 12) else 6
    db = get_db()
    today = util.today()
    return render_template("workload.html", data=data.workload(db, today, weeks),
                           weeks=weeks, levels=data.LEVELS,
                           quota={q["firm_id"]: q for q in quotas.firm_summary(db, today)})
