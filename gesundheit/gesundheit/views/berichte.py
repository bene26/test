"""Reports: a week or a month of one person, for reading, printing or the doctor."""

from datetime import timedelta

from flask import Blueprint, g, render_template, request

from .. import auswertung, bewertung, charts, util
from ..db import get_db

bp = Blueprint("berichte", __name__, url_prefix="/berichte")
KINDS = {"woche": "Woche", "monat": "Monat"}


@bp.route("")
def index():
    db = get_db()
    person = g.person
    kind = request.args.get("art", "woche")
    kind = kind if kind in KINDS else "woche"
    try:
        anchor = util.to_date(request.args.get("datum")) or util.today()
    except ValueError:
        anchor = util.today()
    if not 2000 <= anchor.year <= 2100:
        anchor = util.today()
    rep = auswertung.report(db, person, kind, anchor)
    start, end = rep["start"], rep["end"]
    previous = rep["prev_start"]
    following = end + timedelta(days=1)
    bp_days = []
    for day, slots in rep["protocol"]:
        items = slots["morgens"] + slots["mittags"] + slots["abends"]
        bp_days.append({"day": day, "source": items[0]["source"],
                        "sys": sum(i["values"]["bp_sys"] for i in items) / len(items),
                        "dia": sum(i["values"]["bp_dia"] for i in items) / len(items)})
    figures_charts = {
        "steps": charts.bars(rep["steps"], start, end, "", 0, "Schritte",
                             goal=person["goal_steps"]),
        "sleep": charts.sleep(rep["nights"], start, end, person["goal_sleep_min"]),
        "weight": charts.line(rep["weight"], start, end, "kg", 1, "Gewicht", trend=False)
        if len(rep["weight"]) > 1 else None,
        "bp": charts.blood_pressure(bp_days, start, end, bewertung.bp_category) if bp_days else None,
    }
    title = (f"Woche {start.isocalendar()[1]} · {util.fmt_date(start)} bis {util.fmt_date(end)}"
             if kind == "woche" else f"{util.MONTHS_LONG[start.month - 1]} {start.year}")
    return render_template(
        "bericht.html", rep=rep, kind=kind, kinds=KINDS, title=title, charts=figures_charts,
        previous=previous, following=following if following <= util.today() else None,
        fmt=auswertung.fmt, bp_note=bewertung.BP_NOTE, created=util.now())
