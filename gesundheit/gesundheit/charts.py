"""Charts as server-side SVG (no chart library, no inline styles, no scripts).

The plot area stretches to the card width (preserveAspectRatio="none"); lines and dots keep
their thickness through vector-effect="non-scaling-stroke", and dots are zero-length
round-capped paths so they stay round. Axis labels are HTML next to the SVG, so text never
gets distorted. Ticks are evenly spaced and the axis spans exactly first to last tick, so the
labels (flex, space-between) line up with the grid lines.
"""

import itertools
import math
from datetime import date, timedelta

from markupsafe import Markup, escape

from . import util
from .katalog import source_label

W, H = 1000, 300
_ids = itertools.count(1)


def _uid(prefix="g") -> str:
    return f"{prefix}{next(_ids)}"


def smooth_path(coords: list[tuple[float, float]]) -> str:
    """Monotone cubic curve through the points (no overshoot above the highest value)."""
    if len(coords) < 3:
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    n = len(coords)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) if xs[i + 1] != xs[i] else 0.0
         for i in range(n - 1)]
    m = [d[0]] + [(d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0.0
                  for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        if a * a + b * b > 9:
            t = 3 / math.sqrt(a * a + b * b)
            m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    parts = [f"M{xs[0]:.1f} {ys[0]:.1f}"]
    for i in range(n - 1):
        dx = (xs[i + 1] - xs[i]) / 3
        parts.append(f"C{xs[i] + dx:.1f} {ys[i] + m[i] * dx:.1f} {xs[i + 1] - dx:.1f} "
                     f"{ys[i + 1] - m[i + 1] * dx:.1f} {xs[i + 1]:.1f} {ys[i + 1]:.1f}")
    return " ".join(parts)


def _gradient(uid: str, top="g-top", bottom="g-bottom") -> str:
    return (f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" class="{top}"/><stop offset="1" class="{bottom}"/>'
            f'</linearGradient></defs>')


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
    path = smooth_path(coords)
    if len(coords) > 1:
        uid = _uid()
        body.append(_gradient(uid))
        body.append(f'<path class="area" fill="url(#{uid})" d="{path} L{coords[-1][0]:.1f} {H} '
                    f'L{coords[0][0]:.1f} {H} Z"/>')
        body.append(f'<path class="line" d="{path}" vector-effect="non-scaling-stroke"/>')
    if trend and len(points) >= 14:
        rolling = _rolling(points)
        trend_path = smooth_path([(axis.x(p["day"]), axis.y(v)) for p, v in zip(points, rolling)])
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
    uid = _uid()
    body = [_gradient(uid, "b-top", "b-bottom"), f'<g class="bar-fill" fill="url(#{uid})">']
    for p in points:
        x = axis.x(p["day"]) + (slot - width) / 2
        y = axis.y(p["value"])
        reached = goal is not None and p["value"] >= goal
        tip = (f"{util.fmt_day(p['day'])}: {_fmt(p['value'], decimals)}{unit_text} "
               f"({source_label(p['source'], short=True)})")
        radius = min(width / 2, 6)
        body.append(f'<rect class="bar{" reached" if reached else ""}" x="{x:.2f}" y="{y:.1f}" '
                    f'width="{width:.2f}" height="{H - y:.1f}" rx="{radius:.1f}" '
                    f'data-x="{(x + width / 2) / W:.4f}" '
                    f'data-y="{y / H:.4f}" data-tip="{escape(tip)}"><title>{escape(tip)}</title></rect>')
    body.append("</g>")
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


# ---------- More kinds (uniform scaling where the drawing has text inside) ----------

def rings(items: list[dict], size: int = 200) -> Markup:
    """Concentric activity rings. items: [{key, value, goal}] from outside to inside."""
    parts = [f'<svg class="ringe-svg" viewBox="0 0 {size} {size}" aria-hidden="true" focusable="false">']
    center = size / 2
    for i, item in enumerate(items):
        radius = center - 12 - i * 23
        percent = 0 if not item["goal"] or item["value"] is None else max(0.0, item["value"] / item["goal"] * 100)
        first = min(percent, 100)
        parts.append(f'<g class="kreis kreis-{item["key"]}">'
                     f'<circle class="ring-track" cx="{center}" cy="{center}" r="{radius}" pathLength="100"/>'
                     f'<circle class="ring-fill{" full" if percent >= 100 else ""}" cx="{center}" cy="{center}" '
                     f'r="{radius}" pathLength="100" stroke-dasharray="{first:.1f} 100" data-ring="{first:.1f}"/>')
        if percent > 100:  # second lap, a little darker
            parts.append(f'<circle class="ring-fill ring-lap" cx="{center}" cy="{center}" r="{radius}" '
                         f'pathLength="100" stroke-dasharray="{min(percent - 100, 100):.1f} 100"/>')
        parts.append("</g>")
    parts.append("</svg>")
    return Markup("".join(parts))


def gauge(value, maximum: float, label: str, unit: str = "", levels=(40, 70)) -> Markup:
    """Half-circle gauge for scores (sleep score, Body Battery, readiness)."""
    if value is None:
        return Markup("")
    share = max(0.0, min(float(value) / maximum, 1.0)) * 100
    level = "niedrig" if value < levels[0] else "mittel" if value < levels[1] else "gut"
    return Markup(
        f'<svg class="gauge gauge-{level}" viewBox="0 0 200 120" role="img" '
        f'aria-label="{escape(label)}: {escape(util.fmt_num(value))}{escape(unit)}" focusable="false">'
        f'<path class="gauge-track" d="M20 105 A80 80 0 0 1 180 105" pathLength="100"/>'
        f'<path class="gauge-fill" d="M20 105 A80 80 0 0 1 180 105" pathLength="100" '
        f'stroke-dasharray="{share:.1f} 100" data-ring="{share:.1f}"/>'
        f'<text class="gauge-wert" x="100" y="92" text-anchor="middle">{escape(util.fmt_num(value))}</text>'
        f'<text class="gauge-label" x="100" y="114" text-anchor="middle">{escape(label)}</text></svg>')


def donut(parts: list[tuple[str, str, float]], center_text: str = "", sub: str = "") -> Markup:
    """parts: [(css key, label, value)]; segments in order, clockwise from the top."""
    total = sum(v for _k, _l, v in parts if v) or 1
    aria = escape(", ".join(f"{label} {util.fmt_num(v / total * 100)} %" for _k, label, v in parts if v))
    svg = [f'<svg class="donut" viewBox="0 0 120 120" role="img" aria-label="{aria}" focusable="false">'
           f'<circle class="donut-track" cx="60" cy="60" r="46" pathLength="100"/>']
    start = 0.0
    for key, label, value in parts:
        if not value:
            continue
        share = value / total * 100
        svg.append(f'<circle class="donut-teil st-{key}" cx="60" cy="60" r="46" pathLength="100" '
                   f'stroke-dasharray="{max(share - 0.6, 0.1):.2f} {100 - max(share - 0.6, 0.1):.2f}" '
                   f'stroke-dashoffset="{-start:.2f}"><title>{escape(label)} {util.fmt_num(share)} %</title></circle>')
        start += share
    if center_text:
        svg.append(f'<text class="donut-wert" x="60" y="{62 if sub else 66}" text-anchor="middle">{escape(center_text)}</text>')
    if sub:
        svg.append(f'<text class="donut-sub" x="60" y="78" text-anchor="middle">{escape(sub)}</text>')
    svg.append("</svg>")
    return Markup("".join(svg))


def multi_line(series: list[dict], start: date, end: date, unit: str, decimals: int, label: str,
               x_labels=None, limits: tuple | None = None) -> Markup:
    """Several lines on one axis. series: [{label, cls, points: [{day, value, ...}], dashed}]."""
    values = [p["value"] for s_ in series for p in s_["points"]]
    if not values:
        return empty()
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.08 or max(abs(hi) * 0.02, 1)
    low, high = lo - pad, hi + pad
    if limits:
        low, high = max(low, limits[0]), min(high, limits[1])
    axis = _Axis(start, end, nice_ticks(low, high))
    unit_text = f" {unit}" if unit else ""
    body = []
    for s_ in series:
        pts = [p for p in s_["points"] if start <= util.to_date(p["day"]) <= end]
        if not pts:
            continue
        coords = [(axis.x(p["day"]), axis.y(p["value"])) for p in pts]
        path = smooth_path(coords)
        uid = _uid()
        group = [f'<g class="serie {s_["cls"]}{" gestrichelt" if s_.get("dashed") else ""}">', _gradient(uid, "s-top", "s-bottom")]
        if len(coords) > 1 and not s_.get("dashed"):
            group.append(f'<path class="area" fill="url(#{uid})" d="{path} L{coords[-1][0]:.1f} {H} L{coords[0][0]:.1f} {H} Z"/>')
        if len(coords) > 1:
            group.append(f'<path class="line" d="{path}" vector-effect="non-scaling-stroke"/>')
        for (x, y), p in zip(coords, pts):
            when = p.get("label") or util.fmt_day(p["day"])
            group.append(_dot(x, y, f"{s_['label']} · {when}: {_fmt(p['value'], decimals)}{unit_text}"))
        group.append("</g>")
        body.append("".join(group))
    legend = "".join(f'<span class="leg leg-serie {s_["cls"]}{" gestrichelt" if s_.get("dashed") else ""}">{escape(s_["label"])}</span>'
                     for s_ in series if s_["points"])
    kind = "multi viele" if max(len(s_["points"]) for s_ in series) > 45 else "multi"
    return _frame(axis, body, label, kind, x_labels=x_labels, legend=legend)


class _NumAxis:
    def __init__(self, ticks):
        self.ticks, self.lo, self.hi = ticks, ticks[0], ticks[-1]

    def pos(self, value, size):
        return (value - self.lo) / (self.hi - self.lo or 1) * size


def scatter(points: list[tuple[float, float, str]], x_meta: tuple, y_meta: tuple,
            fit: tuple | None = None) -> Markup:
    """points: [(x, y, tip)]; x_meta/y_meta: (label, unit, decimals); fit: (slope, intercept)."""
    if len(points) < 3:
        return empty("Zu wenige gemeinsame Tage für ein Streudiagramm.")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xpad = (max(xs) - min(xs)) * 0.06 or 1
    ypad = (max(ys) - min(ys)) * 0.08 or 1
    xa = _NumAxis(nice_ticks(min(xs) - xpad, max(xs) + xpad))
    ya = _NumAxis(nice_ticks(min(ys) - ypad, max(ys) + ypad))
    body = [f'<line class="grid" x1="0" x2="{W}" y1="{H - ya.pos(t, H):.1f}" y2="{H - ya.pos(t, H):.1f}" '
            f'vector-effect="non-scaling-stroke"/>' for t in ya.ticks]
    body += [f'<line class="grid grid-v" y1="0" y2="{H}" x1="{xa.pos(t, W):.1f}" x2="{xa.pos(t, W):.1f}" '
             f'vector-effect="non-scaling-stroke"/>' for t in xa.ticks]
    if fit:
        slope, intercept = fit
        x1, x2 = xa.lo, xa.hi
        y1, y2 = slope * x1 + intercept, slope * x2 + intercept
        body.append(f'<line class="fit" x1="0" x2="{W}" y1="{H - ya.pos(y1, H):.1f}" '
                    f'y2="{H - ya.pos(y2, H):.1f}" vector-effect="non-scaling-stroke"/>')
    body.append('<g class="dots">' + "".join(
        _dot(xa.pos(x, W), H - ya.pos(y, H), tip) for x, y, tip in points) + "</g>")
    xd, yd = _tick_decimals(xa.ticks), _tick_decimals(ya.ticks)
    y_labels = [_fmt(t, yd) for t in reversed(ya.ticks)]
    x_labels = [_fmt(t, xd) for t in xa.ticks]
    label = f"{y_meta[0]} gegen {x_meta[0]}"
    legend = (f'<span class="achse">→ {escape(x_meta[0])}{" (" + escape(x_meta[1]) + ")" if x_meta[1] else ""}</span>'
              f'<span class="achse">↑ {escape(y_meta[0])}{" (" + escape(y_meta[1]) + ")" if y_meta[1] else ""}</span>'
              + ('<span class="leg leg-fit">Ausgleichsgerade</span>' if fit else ""))
    return Markup(
        f'<figure class="chart chart-scatter" data-chart>'
        f'<div class="chart-y" aria-hidden="true">{"".join(f"<span>{escape(t)}</span>" for t in y_labels)}</div>'
        f'<div class="chart-plot"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" '
        f'aria-label="{escape(label)}" focusable="false">{"".join(body)}</svg>'
        f'<div class="chart-tip" data-chart-tip hidden></div></div>'
        f'<div class="chart-x" aria-hidden="true">{"".join(f"<span>{escape(t)}</span>" for t in x_labels)}</div>'
        f'<figcaption class="chart-legend">{legend}</figcaption></figure>')


def radar(axes: list[str], series: list[dict], maximum: float = 1.5) -> Markup:
    """series: [{label, cls, values: [0..maximum]}]; rings at 50, 100 and 150 %."""
    if not series:
        return empty()
    size, center, radius = 340, 170, 118
    n = len(axes)

    def point(i, value):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        r = radius * min(value, maximum) / maximum
        return center + r * math.cos(angle), center + r * math.sin(angle)

    svg = [f'<svg class="radar" viewBox="0 0 {size} {size}" role="img" aria-label="Zielerreichung je Person" focusable="false">']
    for level in (0.5, 1.0, 1.5):
        ring_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, level) for i in range(n)))
        svg.append(f'<polygon class="radar-ring{" radar-ziel" if level == 1 else ""}" points="{ring_pts}"/>')
    for i, name in enumerate(axes):
        x, y = point(i, maximum)
        lx, ly = point(i, maximum * 1.16)
        anchor = "middle" if abs(lx - center) < 10 else ("start" if lx > center else "end")
        svg.append(f'<line class="radar-achse" x1="{center}" y1="{center}" x2="{x:.1f}" y2="{y:.1f}"/>')
        svg.append(f'<text class="radar-label" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{escape(name)}</text>')
    lx, ly = point(0, 1.0)
    svg.append(f'<text class="radar-mark" x="{lx + 6:.1f}" y="{ly + 12:.1f}">Ziel</text>')
    for s_ in series:
        pts = [point(i, v or 0) for i, v in enumerate(s_["values"])]
        svg.append(f'<g class="serie {s_["cls"]}"><polygon class="radar-flaeche" points="'
                   + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>'
                   + "".join(f'<circle class="radar-punkt" cx="{x:.1f}" cy="{y:.1f}" r="3.5"><title>'
                             f'{escape(s_["label"])} · {escape(axes[i])}: {util.fmt_num((s_["values"][i] or 0) * 100)} % des Ziels</title></circle>'
                             for i, (x, y) in enumerate(pts)) + "</g>")
    svg.append("</svg>")
    legend = "".join(f'<span class="leg leg-serie {s_["cls"]}">{escape(s_["label"])}</span>' for s_ in series)
    return Markup(f'<figure class="radar-figur">{"".join(svg)}<figcaption class="chart-legend">{legend}</figcaption></figure>')


def heatmap(values: dict[str, float], end: date, unit: str, decimals: int, label: str,
            weeks: int = 53, good: str = "up") -> Markup:
    """Calendar of the last weeks (Monday on top), five shades by quantile."""
    start = end - timedelta(days=end.weekday()) - timedelta(weeks=weeks - 1)
    present = sorted(v for v in values.values() if v is not None)
    if not present:
        return empty("Für diesen Wert gibt es im letzten Jahr keine Tage.")

    def level(v):
        if v is None:
            return 0
        rank = sum(1 for p in present if p <= v) / len(present)
        if good == "down":
            rank = 1 - rank + 1 / len(present)
        return 1 + min(3, int(rank * 4 - 1e-9))

    cell, gap, left, top = 13, 3, 26, 16
    width = left + weeks * (cell + gap)
    height = top + 7 * (cell + gap)
    svg = [f'<svg class="heatmap" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}" focusable="false">']
    for row, name in ((0, "Mo"), (2, "Mi"), (4, "Fr"), (6, "So")):
        svg.append(f'<text class="hm-tag" x="0" y="{top + row * (cell + gap) + cell - 2}">{name}</text>')
    last_month, last_label = None, -9
    unit_text = f" {unit}" if unit else ""
    for week in range(weeks):
        monday = start + timedelta(weeks=week)
        if monday.month != last_month:
            last_month = monday.month
            if week < weeks - 2 and week - last_label >= 3:
                last_label = week
                svg.append(f'<text class="hm-monat" x="{left + week * (cell + gap)}" y="10">{util.MONTHS[monday.month - 1]}</text>')
        for row in range(7):
            day = monday + timedelta(days=row)
            if day > end:
                continue
            value = values.get(day.isoformat())
            text = f"{util.fmt_day(day)}: " + (f"{_fmt(value, decimals)}{unit_text}" if value is not None else "kein Wert")
            svg.append(f'<rect class="hm hm-{level(value)}" x="{left + week * (cell + gap)}" '
                       f'y="{top + row * (cell + gap)}" width="{cell}" height="{cell}" rx="3"><title>{escape(text)}</title></rect>')
    svg.append("</svg>")
    legend = ('<span class="hm-skala">weniger <i class="hm-1"></i><i class="hm-2"></i><i class="hm-3"></i><i class="hm-4"></i> mehr</span>'
              if good != "down" else
              '<span class="hm-skala">ungünstiger <i class="hm-1"></i><i class="hm-2"></i><i class="hm-3"></i><i class="hm-4"></i> besser</span>')
    return Markup(f'<figure class="heatmap-figur"><div class="heatmap-scroll">{"".join(svg)}</div>'
                  f'<figcaption class="chart-legend">{legend}</figcaption></figure>')


def columns(labels: list[str], values: list[float | None], unit: str, decimals: int,
            label: str, highlight: str = "max") -> Markup:
    """Category columns, e.g. the average per weekday. The best column is highlighted."""
    present = [v for v in values if v is not None]
    if not present:
        return empty()
    ticks = nice_ticks(0, max(present) * 1.08 or 1)
    top = ticks[-1]
    n = len(labels)
    slot = W / n
    width = slot * 0.56
    best = (max if highlight == "max" else min)(present)
    uid = _uid()
    unit_text = f" {unit}" if unit else ""
    body = [_gradient(uid, "b-top", "b-bottom"), f'<g class="bar-fill" fill="url(#{uid})">']
    for i, (name, value) in enumerate(zip(labels, values)):
        if value is None:
            continue
        height = value / top * H
        x = i * slot + (slot - width) / 2
        tip = f"{name}: {_fmt(value, decimals)}{unit_text}"
        body.append(f'<rect class="bar{" reached" if value == best else ""}" x="{x:.1f}" y="{H - height:.1f}" '
                    f'width="{width:.1f}" height="{height:.1f}" rx="8" data-x="{(x + width / 2) / W:.4f}" '
                    f'data-y="{(H - height) / H:.4f}" data-tip="{escape(tip)}"><title>{escape(tip)}</title></rect>')
    body.append("</g>")
    grid = "".join(f'<line class="grid" x1="0" x2="{W}" y1="{H - t / top * H:.1f}" y2="{H - t / top * H:.1f}" '
                   f'vector-effect="non-scaling-stroke"/>' for t in ticks)
    decimals_axis = _tick_decimals(ticks)
    return Markup(
        f'<figure class="chart chart-columns" data-chart>'
        f'<div class="chart-y" aria-hidden="true">{"".join(f"<span>{escape(_fmt(t, decimals_axis))}</span>" for t in reversed(ticks))}</div>'
        f'<div class="chart-plot"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" '
        f'aria-label="{escape(label)}" focusable="false">{grid}{"".join(body)}</svg>'
        f'<div class="chart-tip" data-chart-tip hidden></div></div>'
        f'<div class="chart-x chart-x-mitte" aria-hidden="true">{"".join(f"<span>{escape(t)}</span>" for t in labels)}</div>'
        f'</figure>')


def spark_area(values: list[float]) -> Markup:
    """Small trend line with a soft fill, for key figure tiles."""
    if len(values) < 2:
        return Markup("")
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = 100 / (len(values) - 1)
    coords = [(i * step, 30 - (v - lo) / span * 26) for i, v in enumerate(values)]
    path = smooth_path(coords)
    uid = _uid("s")
    return Markup(f'<svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true" '
                  f'focusable="false">{_gradient(uid, "sp-top", "sp-bottom")}'
                  f'<path class="spark-flaeche" fill="url(#{uid})" d="{path} L100 32 L0 32 Z"/>'
                  f'<path class="spark-linie" d="{path}" vector-effect="non-scaling-stroke"/></svg>')
