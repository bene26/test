"""Compare persons: lines side by side, table, ranking, goal radar, weekly challenge."""

from datetime import timedelta

from flask import Blueprint, g, render_template, request

from .. import auswertung, charts, util
from ..auswertung import GROUPS, KEYS, RADAR_AXES
from ..db import get_db
from . import PERIODS
from .auswertungen import _choice, _groups, _int_choice

bp = Blueprint("vergleich", __name__, url_prefix="/vergleich")
CHALLENGES = [("steps", "Schritte"), ("active_min", "Aktive Minuten"),
              ("distance_km", "Strecke"), ("training_min", "Trainingsminuten")]


@bp.route("")
def index():
    db = get_db()
    today = util.today()
    days = _int_choice("zeitraum", 30, PERIODS)
    start = today - timedelta(days=days - 1)
    wanted = set(request.args.getlist("p"))
    people = [p for p in g.persons if not wanted or str(p["id"]) in wanted] or g.persons
    keys = sorted({k for p in g.persons for k in auswertung.available(db, p["id"], start, today)},
                  key=list(KEYS).index) or ["steps"]
    key = _choice("wert", "steps" if "steps" in keys else keys[0], keys)
    meta = KEYS[key]
    rows = auswertung.compare_persons(db, people, key, start, today)
    unit = "" if meta.unit in ("h", "Uhr") else meta.unit
    lines = charts.multi_line(
        [{"label": r["person"]["name"], "cls": f"p-{r['person']['color']}", "points": r["points"]}
         for r in rows], start, today, unit, meta.decimals, f"{meta.label} je Person")
    ranked = auswertung.ranking([dict(r) for r in rows], meta)
    radar = charts.radar([label for _k, label in RADAR_AXES],
                         [{"label": p["name"], "cls": f"p-{p['color']}",
                           "values": auswertung.radar_values(db, p, start, today)} for p in people])
    week_start = today - timedelta(days=today.weekday())
    challenges = []
    for ckey, label in CHALLENGES:
        cmeta = KEYS[ckey]
        board = auswertung.ranking([dict(r) for r in auswertung.compare_persons(
            db, people, ckey, week_start, today)], cmeta)
        if board and any(r["measure"] for r in board):
            challenges.append({"key": ckey, "label": label, "meta": cmeta, "board": board})
    return render_template(
        "vergleich.html", key=key, meta=meta, groups=_groups(keys), days=days, periods=PERIODS,
        people=people, wanted={str(p["id"]) for p in people}, rows=rows, lines=lines,
        ranked=ranked, radar=radar, challenges=challenges, week_start=week_start,
        fmt=auswertung.fmt, all_groups=GROUPS)
