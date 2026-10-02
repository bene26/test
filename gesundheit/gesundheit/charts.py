"""Charts as server-side SVG (no chart library, no inline styles, no scripts).

The plot area stretches to the card width (preserveAspectRatio="none"); lines and dots keep
their thickness through vector-effect="non-scaling-stroke", and dots are zero-length
round-capped paths so they stay round. Axis labels are HTML next to the SVG, so text never
gets distorted. Ticks are evenly spaced and the axis spans exactly first to last tick, so the
labels (flex, space-between) line up with the grid lines.
"""

import math
from datetime import date, timedelta

from markupsafe import Markup, escape

from . import util
from .katalog import source_label

W, H = 1000, 300


def nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start = math.floor(lo / step) * step
    ticks = [start]
    while ticks[-1] < hi - 1e-9:
        ticks.append(ticks[-1] + step)
    return [round(t, 6) for t in ticks]


def _fmt(value, decimals):
    return util.fmt_num(value, decimals)


def _tick_decimals(ticks):
    step = abs(ticks[1] - ticks[0]) if len(ticks) > 1 else 1
    for decimals in (0, 1, 2):
        if abs(step * 10 ** decimals - round(step * 10 ** decimals)) < 1e-6:
            return decimals
    return 2


def day_labels(start: date, end: date) -> list[str]:
    span = (end - start).days
    if span < 4:
        return [util.fmt_day(start), util.fmt_day(end)]
    return [util.fmt_day(start + timedelta(days=round(span * f))) for f in (0, 0.25, 0.5, 0.75, 1)]


class _Axis:
    def __init__(self, start: date, end: date, ticks: list[float]):
        self.start, self.end = start, end
        self.span = max((end - start).days, 1)
        self.lo, self.hi = ticks[0], ticks[-1]
        self.ticks = ticks

    def x(self, day) -> float:
        return (util.to_date(day) - self.start).days / self.span * W

    def y(self, value) -> float:
        return H - (value - self.lo) / (self.hi - self.lo or 1) * H


def _frame(axis: _Axis, body: list[str], label: str, kind: str, y_text=None,
           x_labels=None, legend: str = "") -> Markup:
    decimals = _tick_decimals(axis.ticks)
    y_labels = y_text or [_fmt(t, decimals) for t in reversed(axis.ticks)]
    grid = "".join(f'<line class="grid" x1="0" x2="{W}" y1="{axis.y(t):.1f}" y2="{axis.y(t):.1f}" '
                   f'vector-effect="non-scaling-stroke"/>' for t in axis.ticks)
    if x_labels is None:
        x_labels = day_labels(axis.start, axis.end)
    return Markup(
        f'<figure class="chart chart-{kind}" data-chart>'
        f'<div class="chart-y" aria-hidden="true">{"".join(f"<span>{escape(t)}</span>" for t in y_labels)}</div>'
        f'<div class="chart-plot"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
        f'role="img" aria-label="{escape(label)}" focusable="false">{grid}{"".join(body)}</svg>'
        f'<div class="chart-tip" data-chart-tip hidden></div></div>'
        f'<div class="chart-x" aria-hidden="true">{"".join(f"<span>{escape(t)}</span>" for t in x_labels)}</div>'
        + (f'<figcaption class="chart-legend">{legend}</figcaption>' if legend else "")
        + "</figure>")


def _dot(x, y, tip, cls="dot"):
    return (f'<path class="{cls}" d="M{x:.1f} {y:.1f}h0" vector-effect="non-scaling-stroke" '
            f'data-x="{x / W:.4f}" data-y="{y / H:.4f}" data-tip="{escape(tip)}">'
            f'<title>{escape(tip)}</title></path>')


def empty(text="Für diesen Zeitraum gibt es noch keine Werte.") -> Markup:
    return Markup(f'<div class="chart-empty"><p>{escape(text)}</p></div>')


def _rolling(points, window=7):
    """Mean of the last `window` days for each point (by calendar day)."""
    result = []
    for i, p in enumerate(points):
        day = util.to_date(p["day"])
        values = [q["value"] for q in points[max(0, i - window * 2):i + 1]
                  if (day - util.to_date(q["day"])).days < window]
        result.append(sum(values) / len(values))
    return result


def line(points: list[dict], start: date, end: date, unit: str, decimals: int, label: str,
         band: tuple | None = None, goal: float | None = None, trend: bool = True,
         limits: tuple | None = None) -> Markup:
    """points: [{day, value, source}] sorted by day. limits: the metric's possible range, so
    the axis of a score never goes past 100."""
    if not points:
        return empty()
    values = [p["value"] for p in points]
    lo, hi = min(values), max(values)
    # The goal widens the axis only when it is near the values; a band never does
    # (it is cut to the visible range), so small changes stay visible.
    if goal is not None and abs(goal - (lo + hi) / 2) <= max(hi - lo, abs(hi) * 0.05) * 2:
        lo, hi = min(lo, goal), max(hi, goal)
    pad = (hi - lo) * 0.08 or max(abs(hi) * 0.02, 1)
    low, high = lo - pad, hi + pad
    if limits:
        low, high = max(low, limits[0]), min(high, limits[1])
    ticks = nice_ticks(low, high)
    if limits and ticks[-1] > limits[1] >= hi:
        ticks = [t for t in ticks if t < limits[1]] + [limits[1]]
        if len(ticks) > 2 and ticks[-1] - ticks[-2] < (ticks[1] - ticks[0]) * 0.5:
            ticks.pop(-2)
    axis = _Axis(start, end, ticks)
    body = []
    if band and band[0] < axis.hi and band[1] > axis.lo:
        y1, y2 = axis.y(min(band[1], axis.hi)), axis.y(max(band[0], axis.lo))
        body.append(f'<rect class="band" x="0" y="{y1:.1f}" width="{W}" height="{y2 - y1:.1f}"/>')
    else:
        band = None
    if goal is not None and not axis.lo <= goal <= axis.hi:
        goal = None
    if goal is not None:
        body.append(f'<line class="goal" x1="0" x2="{W}" y1="{axis.y(goal):.1f}" '
                    f'y2="{axis.y(goal):.1f}" vector-effect="non-scaling-stroke"/>')
    coords = [(axis.x(p["day"]), axis.y(p["value"])) for p in points]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    if len(coords) > 1:
        body.append(f'<path class="area" d="{path} L{coords[-1][0]:.1f} {H} L{coords[0][0]:.1f} {H} Z"/>')
        body.append(f'<path class="line" d="{path}" vector-effect="non-scaling-stroke"/>')
    if trend and len(points) >= 14:
        rolling = _rolling(points)
        trend_path = "M" + " L".join(f"{axis.x(p['day']):.1f} {axis.y(v):.1f}"
                                     for p, v in zip(points, rolling))
        body.append(f'<path class="trend" d="{trend_path}" vector-effect="non-scaling-stroke"/>')
    unit_text = f" {unit}" if unit else ""
    body.append('<g class="dots">' + "".join(
        _dot(x, y, f"{util.fmt_day(p['day'])}: {_fmt(p['value'], decimals)}{unit_text} "
                   f"({source_label(p['source'], short=True)})")
        for (x, y), p in zip(coords, points)) + "</g>")
    legend = []
    if trend and len(points) >= 14:
        legend.append('<span class="leg leg-trend">Trend (7 Tage)</span>')
    if band:
        legend.append(f'<span class="leg leg-band">{escape(band[2])}</span>')
    if goal is not None:
        legend.append(f'<span class="leg leg-goal">Ziel {_fmt(goal, decimals)}{escape(unit_text)}</span>')
    kind = "line viele" if len(points) > 60 else "line"
    return _frame(axis, body, label, kind, legend=" ".join(legend))


def bars(points: list[dict], start: date, end: date, unit: str, decimals: int, label: str,
         goal: float | None = None) -> Markup:
    if not points:
        return empty()
    hi = max([p["value"] for p in points] + [goal or 0])
    axis = _Axis(start, end + timedelta(days=1), nice_ticks(0, hi * 1.05 or 1))
    slot = W / axis.span
    width = max(slot * 0.68, 1.2)
    unit_text = f" {unit}" if unit else ""
    body = []
    for p in points:
        x = axis.x(p["day"]) + (slot - width) / 2
        y = axis.y(p["value"])
        reached = goal is not None and p["value"] >= goal
        tip = (f"{util.fmt_day(p['day'])}: {_fmt(p['value'], decimals)}{unit_text} "
               f"({source_label(p['source'], short=True)})")
        body.append(f'<rect class="bar{" reached" if reached else ""}" x="{x:.2f}" y="{y:.1f}" '
                    f'width="{width:.2f}" height="{H - y:.1f}" data-x="{(x + width / 2) / W:.4f}" '
                    f'data-y="{y / H:.4f}" data-tip="{escape(tip)}"><title>{escape(tip)}</title></rect>')
    if goal is not None:
        body.append(f'<line class="goal" x1="0" x2="{W}" y1="{axis.y(goal):.1f}" '
                    f'y2="{axis.y(goal):.1f}" vector-effect="non-scaling-stroke"/>')
    legend = (f'<span class="leg leg-goal">Ziel {_fmt(goal, decimals)}{escape(unit_text)}</span>'
              f'<span class="leg leg-reached">Ziel erreicht</span>') if goal is not None else ""
    return _frame(axis, body, label, "bars", x_labels=day_labels(start, end), legend=legend)


def blood_pressure(days: list[dict], start: date, end: date, category) -> Markup:
    """days: [{day, sys, dia, source}]; one bar from diastolic to systolic per day."""
    if not days:
        return empty()
    lo = min(min(d["dia"] for d in days), 70) - 5
    hi = max(max(d["sys"] for d in days), 140) + 5
    axis = _Axis(start, end, nice_ticks(lo, hi, 5))
    body = []
    for limit in (135, 85):
        body.append(f'<line class="limit" x1="0" x2="{W}" y1="{axis.y(limit):.1f}" '
                    f'y2="{axis.y(limit):.1f}" vector-effect="non-scaling-stroke"/>')
    for d in days:
        x = axis.x(d["day"])
        level = category(d["sys"], d["dia"])[0]
        tip = (f"{util.fmt_day(d['day'])}: {_fmt(d['sys'], 0)}/{_fmt(d['dia'], 0)} mmHg "
               f"({source_label(d['source'], short=True)})")
        body.append(f'<g class="bp bp-{level}"><path class="bp-range" d="M{x:.1f} {axis.y(d["sys"]):.1f} '
                    f'V{axis.y(d["dia"]):.1f}" vector-effect="non-scaling-stroke"/>'
                    + _dot(x, axis.y(d["sys"]), tip, "dot bp-sys")
                    + _dot(x, axis.y(d["dia"]), tip, "dot bp-dia") + "</g>")
    legend = ('<span class="leg leg-limit">Grenze für Messungen zu Hause: 135/85</span>'
              '<span class="leg leg-bp">oben systolisch, unten diastolisch (Tagesmittel)</span>')
    return _frame(axis, body, "Blutdruck", "bp", legend=legend)


def sleep(nights: list[dict], start: date, end: date, goal_min: int | None) -> Markup:
    if not nights:
        return empty()
    hi_h = max([(n["asleep_min"] or 0) + (n["awake_min"] or 0) for n in nights]
               + [goal_min or 0]) / 60
    axis = _Axis(start, end + timedelta(days=1), nice_ticks(0, max(hi_h * 1.05, 1)))
    slot = W / axis.span
    width = max(slot * 0.68, 1.2)
    body = []
    for n in nights:
        x = axis.x(n["night"]) + (slot - width) / 2
        staged = n["deep_min"] is not None
        parts = ([("tief", n["deep_min"]), ("leicht", n["light_min"]), ("rem", n["rem_min"])]
                 if staged else [("schlaf", n["asleep_min"])]) + [("wach", n["awake_min"])]
        tip = f"Nacht auf {util.fmt_day(n['night'])}: {util.fmt_minutes(n['asleep_min'])} Schlaf"
        if staged:
            tip += (f" (Tief {util.fmt_minutes(n['deep_min'])}, Leicht "
                    f"{util.fmt_minutes(n['light_min'])}, REM {util.fmt_minutes(n['rem_min'])})")
        tip += f" · {source_label(n['source'], short=True)}"
        total = sum(minutes for _stage, minutes in parts if minutes) / 60
        group = [f'<g class="night" data-x="{(x + width / 2) / W:.4f}" '
                 f'data-y="{axis.y(total) / H:.4f}" data-tip="{escape(tip)}">'
                 f'<title>{escape(tip)}</title>']
        bottom = 0.0
        for stage, minutes in parts:
            if not minutes:
                continue
            y_top = axis.y(bottom + minutes / 60)
            group.append(f'<rect class="st st-{stage}" x="{x:.2f}" y="{y_top:.1f}" '
                         f'width="{width:.2f}" height="{axis.y(bottom) - y_top:.1f}"/>')
            bottom += minutes / 60
        group.append("</g>")
        body.append("".join(group))
    if goal_min:
        body.append(f'<line class="goal" x1="0" x2="{W}" y1="{axis.y(goal_min / 60):.1f}" '
                    f'y2="{axis.y(goal_min / 60):.1f}" vector-effect="non-scaling-stroke"/>')
    legend = ('<span class="leg leg-tief">Tief</span><span class="leg leg-leicht">Leicht</span>'
              '<span class="leg leg-rem">REM</span><span class="leg leg-schlaf">Schlaf ohne Phasen</span>'
              '<span class="leg leg-wach">Wach</span>'
              + (f'<span class="leg leg-goal">Ziel {escape(util.fmt_minutes(goal_min))}</span>'
                 if goal_min else ""))
    decimals = _tick_decimals(axis.ticks)
    y_text = [f"{_fmt(t, decimals)} h" for t in reversed(axis.ticks)]
    return _frame(axis, body, "Schlafdauer je Nacht", "sleep", y_text=y_text,
                  x_labels=day_labels(start, end), legend=legend)


def spark(values: list[float]) -> Markup:
    if len(values) < 2:
        return Markup("")
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = 100 / (len(values) - 1)
    path = "M" + " L".join(f"{i * step:.1f} {28 - (v - lo) / span * 24:.1f}"
                           for i, v in enumerate(values))
    return Markup(f'<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" '
                  f'aria-hidden="true" focusable="false"><path d="{path}" '
                  f'vector-effect="non-scaling-stroke"/></svg>')


def ring(value, goal, cls: str) -> Markup:
    """Activity ring: share of the goal, animated by gesundheit.js."""
    percent = 0 if not goal or value is None else max(0.0, value / goal * 100)
    shown = min(percent, 100)
    return Markup(
        f'<svg class="ring ring-{cls}" viewBox="0 0 120 120" aria-hidden="true" focusable="false">'
        f'<circle class="ring-track" cx="60" cy="60" r="50" pathLength="100"/>'
        f'<circle class="ring-fill{" full" if percent >= 100 else ""}" cx="60" cy="60" r="50" '
        f'pathLength="100" stroke-dasharray="{shown:.1f} 100" data-ring="{shown:.1f}"/></svg>')
