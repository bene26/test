"""Analyses for the person shown: periods, best values, weekdays, calendar, relationships."""

from datetime import timedelta

from flask import Blueprint, g, render_template, request

from .. import auswertung, charts, util
from ..auswertung import GROUPS, KEYS
from ..db import get_db
from . import PERIODS

bp = Blueprint("auswertungen", __name__, url_prefix="/auswertungen")


def _choice(name: str, default: str, allowed) -> str:
    value = request.args.get(name, default)
    return value if value in allowed else default


def _int_choice(name: str, default: int, allowed) -> int:
    try:
        value = int(request.args.get(name, default))
    except ValueError:
        return default
    return value if value in allowed else default


def _groups(keys: list[str]) -> list[tuple[str, list[str]]]:
    present = set(keys)
    return [(label, [k for k in group if k in present]) for label, group in GROUPS
            if any(k in present for k in group)]


@bp.route("")
def index():
    db = get_db()
    person = g.person
    today = util.today()
    year_back = today - timedelta(days=400)
    keys = auswertung.available(db, person["id"], year_back, today) or ["steps"]
    key = _choice("wert", "steps" if "steps" in keys else keys[0], keys)
    days = _int_choice("zeitraum", 30, PERIODS)
    meta = KEYS[key]
    cmp = auswertung.compare_periods(db, person["id"], key, days, today)
    overlay = charts.multi_line(cmp["overlay"], cmp["start"], cmp["end"],
                                "" if meta.unit in ("h", "Uhr") else meta.unit, meta.decimals,
                                f"{meta.label}: Zeiträume im Vergleich")
    rec = auswertung.records(db, person["id"], key, person, today)
    year_points = auswertung.series(db, person["id"], key, today - timedelta(days=370), today)
    profile = auswertung.weekday_profile(year_points)
    highlight = "min" if meta.good == "down" else "max"
    weekday_chart = charts.columns(util.WEEKDAYS, profile, meta.unit if meta.unit not in ("h", "Uhr") else "",
                                   meta.decimals, f"{meta.label} je Wochentag", highlight)
    present = [(i, v) for i, v in enumerate(profile) if v is not None]
    best_day = None
    if present:
        pick = (min if meta.good == "down" else max)(present, key=lambda iv: iv[1])
        best_day = auswertung.WEEKDAYS_LONG[pick[0]]
    heat = charts.heatmap({p["day"]: p["value"] for p in year_points}, today,
                          meta.unit if meta.unit not in ("h", "Uhr") else "", meta.decimals,
                          f"{meta.label} im letzten Jahr", good=meta.good or "up")
    return render_template(
        "auswertungen.html", key=key, meta=meta, groups=_groups(keys), days=days,
        periods=PERIODS, cmp=cmp, overlay=overlay, rec=rec, weekday_chart=weekday_chart,
        best_day=best_day, heat=heat, fmt=auswertung.fmt)


RANGES = {90: "90 Tage", 180: "6 Monate", 365: "1 Jahr"}


@bp.route("/zusammenhaenge")
def zusammenhaenge():
    db = get_db()
    person = g.person
    today = util.today()
    days = _int_choice("zeitraum", 180, RANGES)
    start = today - timedelta(days=days - 1)
    keys = auswertung.available(db, person["id"], start, today)
    found = auswertung.insights(db, person["id"], today, days)
    default_x, default_y, default_lag = ((found[0]["xkey"], found[0]["ykey"], found[0]["lag"])
                                         if found else ("schlaf_dauer", "resting_hr", 0))
    xkey = _choice("x", default_x, KEYS)
    ykey = _choice("y", default_y, KEYS)
    lag = _int_choice("versatz", default_lag if "x" not in request.args else 0, (0, 1))
    rel = auswertung.relationship(db, person["id"], xkey, ykey, start, today, lag)
    xm, ym = rel["x"], rel["y"]

    def tip(x, y, day):
        when = util.fmt_day(day)
        if lag:
            when += f" → {util.fmt_day(util.to_date(day) + timedelta(days=lag))}"
        return f"{when}: {auswertung.fmt(xkey, x)} · {auswertung.fmt(ykey, y)}"

    scatter = charts.scatter([(x, y, tip(x, y, d)) for x, y, d in rel["points"]],
                             (xm.label, "" if xm.unit == "Uhr" else xm.unit, xm.decimals),
                             (ym.label, "" if ym.unit == "Uhr" else ym.unit, ym.decimals),
                             fit=rel["fit"] if rel["r"] is not None and abs(rel["r"]) >= 0.1 else None)
    return render_template(
        "zusammenhaenge.html", found=found, rel=rel, scatter=scatter, xkey=xkey, ykey=ykey,
        lag=lag, groups=_groups(keys or list(KEYS)), days=days, ranges=RANGES)
