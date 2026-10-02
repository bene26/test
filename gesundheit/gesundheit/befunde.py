"""Findings ("Befunde"): short, checkable statements computed from one person's data.

Each rule looks at a few weeks of values, compares them with the person's own normal and
returns a finding only when the difference is clear. A finding carries a headline (the second
part is the point), three numbers as evidence, the calculation step by step ("Rechenweg") and a
chart. Rules are fixed and simple on purpose: no model, nothing leaves the NAS, and every
number can be followed back to the values on the pages. Orientation, not a diagnosis.
"""

import json
import logging
import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from . import auswertung, belastung, bewertung, charts, store, util
from .auswertung import WEEKDAYS_LONG

log = logging.getLogger(__name__)
WARN, GOOD, INFO = "warn", "gut", "info"
KEY_PATTERN = re.compile(r"^[a-z0-9_-]{1,80}$")
SEEN_KEEP = 40
TONE_WEIGHT = {WARN: 1.3, GOOD: 1.0, INFO: 0.8}
_CACHE: dict = {}
_CACHE_SECONDS = 300


@dataclass
class Finding:
    rule: str
    tone: str
    pill: str
    title_a: str
    title_b: str
    big: str
    text: str
    stats: list = field(default_factory=list)       # [(value, label)] three at most
    steps: list = field(default_factory=list)       # the calculation, step by step
    chart: Callable | None = None                   # rendered only where shown
    link: tuple = ("auswertungen.index", {})        # (endpoint, args) for "more"
    score: float = 1.0
    basis: str = ""                                 # what it was computed from
    key: str = ""

    @property
    def title(self) -> str:
        return f"{self.title_a} {self.title_b}"


def _mean(values):
    return sum(values) / len(values)


def _sd(values):
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def _points(db, pid, key, start, end):
    return auswertung.series(db, pid, key, start, end)


def _n(value, decimals=0):
    return util.fmt_num(value, decimals).replace("-", "−")


def _tip(day, text):
    return f"{util.fmt_day(day)}: {text}"


# ---------- Recovery ----------

def _baseline_rule(db, pid, today, key):
    """Last 7 days against the 28 days before: shared by resting pulse and HRV."""
    recent = _points(db, pid, key, today - timedelta(days=6), today)
    base = _points(db, pid, key, today - timedelta(days=34), today - timedelta(days=7))
    if len(recent) < 4 or len(base) < 14:
        return None
    r_vals, b_vals = [p["value"] for p in recent], [p["value"] for p in base]
    r_mean, b_mean = _mean(r_vals), _mean(b_vals)
    spread = max(_sd(b_vals), 0.5)
    diff = r_mean - b_mean
    z = diff / spread
    pct = diff / b_mean * 100 if b_mean else 0
    return recent, base, r_mean, b_mean, spread, diff, z, pct


def resting_pulse(db, pid, person, today):
    found = _baseline_rule(db, pid, today, "resting_hr")
    if not found:
        return None
    recent, base, r_mean, b_mean, spread, diff, z, _pct = found
    limit = b_mean + spread
    above = sum(1 for p in recent if p["value"] > limit)
    start = today - timedelta(days=34)
    points = [{"day": p["day"], "value": p["value"], "tip": _tip(p["day"], f"{_n(p['value'])} bpm")}
              for p in base + recent]
    steps = [
        f"Ruhepuls der letzten 7 Tage: {', '.join(_n(p['value']) for p in recent)} → Ø {_n(r_mean, 1)} bpm",
        f"Die 28 Tage davor: Ø {_n(b_mean, 1)} bpm, übliche Schwankung ±{_n(spread, 1)} bpm",
        f"Unterschied {util.fmt_signed(diff, 1)} bpm, das {_n(abs(z), 1)}-Fache deiner Schwankung",
        "Ab 3 Schlägen und dem 1,5-Fachen der Schwankung zeigt das Cockpit diesen Befund.",
    ]
    if diff >= 3 and z >= 1.5:
        return Finding(
            "ruhepuls", WARN, "Erholung", "Dein Ruhepuls liegt seit einer Woche",
            f"{_n(diff)} Schläge über normal.", f"+{_n(diff)} bpm",
            "Oft ein frühes Zeichen für zu wenig Erholung, Stress, einen Infekt oder Alkohol. "
            "Ein paar ruhigere Tage helfen meist; bleibt er hoch, ärztlich abklären lassen.",
            [(f"{_n(r_mean)} bpm", "Ø letzte 7 Tage"), (f"{_n(b_mean)} bpm", "Ø 4 Wochen davor"),
             (f"{above} von {len(recent)}", "Tage über normal")], steps,
            lambda: charts.zone_dots(points, start, today, (limit, None), "bpm", 0,
                                     "Ruhepuls der letzten fünf Wochen",
                                     f"über normal · ab {_n(limit)} bpm", "dein Normalbereich"),
            ("main.history", {"metric": "resting_hr"}), 1 + z,
            basis=f"aus {len(base) + len(recent)} Tagen")
    if diff <= -3 and z <= -1.5:
        return Finding(
            "ruhepuls", GOOD, "Erholung", "Dein Ruhepuls ist gesunken:",
            f"{_n(-diff)} Schläge weniger als sonst.", f"{util.fmt_signed(diff, 0)} bpm",
            "Ein sinkender Ruhepuls zeigt meist gute Erholung oder wachsende Ausdauer.",
            [(f"{_n(r_mean)} bpm", "Ø letzte 7 Tage"), (f"{_n(b_mean)} bpm", "Ø 4 Wochen davor"),
             (f"{_n(spread, 1)} bpm", "übliche Schwankung")], steps,
            lambda: charts.zone_dots(points, start, today, (None, b_mean - spread), "bpm", 0,
                                     "Ruhepuls der letzten fünf Wochen",
                                     f"niedriger als sonst · unter {_n(b_mean - spread)} bpm",
                                     "dein Normalbereich"),
            ("main.history", {"metric": "resting_hr"}), 0.5 - z * 0.5,
            basis=f"aus {len(base) + len(recent)} Tagen")
    return None


def hrv(db, pid, person, today):
    key = "hrv_rmssd" if store.latest(db, pid, "hrv_rmssd") else "hrv_sdnn"
    found = _baseline_rule(db, pid, today, key)
    if not found:
        return None
    recent, base, r_mean, b_mean, spread, diff, z, pct = found
    start = today - timedelta(days=34)
    points = [{"day": p["day"], "value": p["value"], "tip": _tip(p["day"], f"{_n(p['value'])} ms")}
              for p in base + recent]
    steps = [
        f"HRV der letzten 7 Tage: {', '.join(_n(p['value']) for p in recent)} → Ø {_n(r_mean, 1)} ms",
        f"Die 28 Tage davor: Ø {_n(b_mean, 1)} ms, übliche Schwankung ±{_n(spread, 1)} ms",
        f"Unterschied {util.fmt_signed(pct, 0)} %, das {_n(abs(z), 1)}-Fache deiner Schwankung",
        "Ab 10 % und der einfachen Schwankung zeigt das Cockpit diesen Befund.",
    ]
    if pct <= -10 and z <= -1:
        limit = b_mean - spread
        return Finding(
            "hrv", WARN, "Erholung", "Deine Herzfrequenzvariabilität liegt",
            f"{_n(-pct)} % unter deinem Normalwert.", f"{util.fmt_signed(pct, 0)} %",
            "Eine niedrige HRV heißt meist: Der Körper ist noch mit Erholung beschäftigt "
            "(Training, Stress, wenig Schlaf, Infekt).",
            [(f"{_n(r_mean)} ms", "Ø letzte 7 Tage"), (f"{_n(b_mean)} ms", "Ø 4 Wochen davor"),
             (f"{sum(1 for p in recent if p['value'] < limit)} von {len(recent)}", "Tage unter normal")],
            steps,
            lambda: charts.zone_dots(points, start, today, (None, limit), "ms", 0,
                                     "Herzfrequenzvariabilität der letzten fünf Wochen",
                                     f"unter normal · unter {_n(limit)} ms", "dein Normalbereich"),
            ("main.history", {"metric": key}), 1 - z, basis=f"aus {len(base) + len(recent)} Tagen")
    if pct >= 10 and z >= 1:
        return Finding(
            "hrv", GOOD, "Erholung", "Deine Herzfrequenzvariabilität ist",
            f"{_n(pct)} % höher als sonst.", f"+{_n(pct)} %",
            "Eine höhere HRV spricht für gute Erholung.",
            [(f"{_n(r_mean)} ms", "Ø letzte 7 Tage"), (f"{_n(b_mean)} ms", "Ø 4 Wochen davor"),
             (f"±{_n(spread)} ms", "übliche Schwankung")], steps,
            lambda: charts.zone_dots(points, start, today, (b_mean + spread, None), "ms", 0,
                                     "Herzfrequenzvariabilität der letzten fünf Wochen",
                                     f"höher als sonst · ab {_n(b_mean + spread)} ms", "dein Normalbereich"),
            ("main.history", {"metric": key}), 0.5 + z * 0.5,
            basis=f"aus {len(base) + len(recent)} Tagen")
    return None


# ---------- Training ----------

def easy_trainings(db, pid, person, today):
    """Endurance grows mostly from easy sessions (rule of thumb: about 80 % easy)."""
    start = today - timedelta(days=83)
    sessions = [w for w in store.workouts(db, pid, start, today) if w["hr_avg"]]
    if len(sessions) < 8:
        return None
    rest, maximum = belastung.heart_limits(db, pid, person, today)
    limit = rest + 0.7 * (maximum - rest)
    above = [w for w in sessions if w["hr_avg"] >= limit]
    share = len(above) / len(sessions)
    if share < 0.6:
        return None
    median = statistics.median(w["hr_avg"] for w in sessions)
    points = sorted(({"day": w["day"], "value": w["hr_avg"],
                      "tip": _tip(w["day"], f"{_n(w['hr_avg'])} bpm, {_n(w['duration_min'] or 0)} min")}
                     for w in sessions), key=lambda p: p["day"])
    easy = len(sessions) - len(above)
    return Finding(
        "locker", WARN, "Training", "Deine ruhigen Einheiten sind", "nicht ruhig.",
        f"{_n(share * 100)} %",
        f"Nur {easy} von {len(sessions)} Trainings der letzten zwölf Wochen lagen unter "
        f"{_n(limit)} Puls, deiner Grenze von Zone 2 zu Zone 3. Ausdauer wächst vor allem mit "
        "vielen lockeren Einheiten; als Faustregel gelten etwa 80 % locker und 20 % hart.",
        [(f"{len(above)} von {len(sessions)}", "Trainings über Zone 2"),
         (f"{_n(median)} bpm", "Median deiner Trainings"), (f"{_n(limit)} bpm", "Grenze Zone 2 → 3")],
        [f"Ruhepuls {_n(rest)} bpm, Höchstpuls {_n(maximum)} bpm (Alter oder höchster Trainingspuls)",
         f"Grenze Zone 2 → 3 nach Karvonen: {_n(rest)} + 70 % × ({_n(maximum)} − {_n(rest)}) = {_n(limit)} bpm",
         f"{len(above)} von {len(sessions)} Trainings mit Durchschnittspuls über der Grenze = {_n(share * 100)} %",
         "Ab 60 % harter Einheiten zeigt das Cockpit diesen Befund."],
        lambda: charts.zone_dots(points, start, today, (limit, None), "bpm", 0,
                                 "Durchschnittspuls je Training, letzte zwölf Wochen",
                                 f"Zone 3 · ab {_n(limit)} Puls", "locker · Zone 1 und 2"),
        ("bereiche.aktivitaet", {}), 1 + (share - 0.6) * 10, basis=f"aus {len(sessions)} Trainings")


def load_jump(db, pid, person, today):
    loads = belastung.daily(db, pid, person, today - timedelta(days=55), today)
    def window(a, b):  # days a..b back, inclusive
        return sum(loads.get((today - timedelta(days=n)).isoformat(), 0.0) for n in range(a, b + 1))
    this_week = window(0, 6)
    before = window(7, 27) / 3
    if before < 50:
        return None
    ratio = this_week / before
    weeks = [window(7 * i, 7 * i + 6) for i in range(7, -1, -1)]
    labels = [f"KW {(today - timedelta(days=7 * i)).isocalendar()[1]}" for i in range(7, -1, -1)]
    labels[-1] = "letzte 7 T"
    steps = [f"Belastung der letzten 7 Tage: {_n(this_week)} Punkte",
             f"Ø je Woche in den 3 Wochen davor: {_n(before)} Punkte",
             f"Verhältnis akut zu chronisch: {_n(this_week, 0)} ÷ {_n(before, 0)} = {_n(ratio, 2)}",
             "Ab 1,3 (30 % mehr) zeigt das Cockpit einen Sprung, unter 0,5 eine Erholungswoche."]
    stats = [(_n(this_week), "Belastung letzte 7 Tage"), (_n(before), "Ø der 3 Wochen davor"),
             (_n(ratio, 2), "akut zu chronisch")]
    chart = lambda: charts.columns(labels, weeks, "Punkte", 0, "Belastung je Woche", highlight="last")
    if ratio >= 1.3:
        return Finding(
            "sprung", WARN, "Training", "Deine Belastung ist diese Woche",
            f"um {_n((ratio - 1) * 100)} % gestiegen.", f"+{_n((ratio - 1) * 100)} %",
            "Sprünge von mehr als 30 % pro Woche erhöhen das Risiko für Überlastung. "
            "Lieber in kleineren Schritten steigern und Ruhetage einplanen.",
            stats, steps, chart, ("main.index", {"ansicht": "belastung"}), 1.5 + (ratio - 1.3) * 6,
            basis="aus acht Wochen")
    if ratio <= 0.5:
        return Finding(
            "sprung", INFO, "Training", "Deine Belastung ist diese Woche",
            f"um {_n((1 - ratio) * 100)} % gesunken.", f"−{_n((1 - ratio) * 100)} %",
            "Eine ruhige Woche nach harten Wochen ist sinnvoll. Dauert sie länger, sinkt die Fitness.",
            stats, steps, chart, ("main.index", {"ansicht": "belastung"}), 0.9,
            basis="aus acht Wochen")
    return None


# ---------- Sleep ----------

def sleep_debt(db, pid, person, today):
    nights = [n for n in store.sleep_series(db, pid, today - timedelta(days=6), today) if n["asleep_min"]]
    if len(nights) < 5:
        return None
    goal = person.get("goal_sleep_min") or 450
    values = [n["asleep_min"] for n in nights]
    avg = _mean(values)
    debt = sum(goal - v for v in values)
    under = sum(1 for v in values if v < goal)
    start = today - timedelta(days=6)
    points = [{"day": n["night"], "value": n["asleep_min"] / 60, "source": n["source"]} for n in nights]
    stats = [(util.fmt_minutes(avg), "Ø pro Nacht"), (util.fmt_minutes(goal), "dein Ziel"),
             (f"{under} von {len(nights)}", "Nächte unter dem Ziel")]
    steps = [f"Schlaf der letzten {len(nights)} Nächte: "
             + ", ".join(util.fmt_minutes(v) for v in values),
             f"Ziel {util.fmt_minutes(goal)} je Nacht (einstellbar unter Personen)",
             f"Fehlend: Summe aus Ziel minus Schlaf je Nacht = {util.fmt_minutes(max(debt, 0))}",
             "Ab 30 Minuten unter dem Ziel im Schnitt zeigt das Cockpit diesen Befund."]
    chart = lambda: charts.bars(points, start, today, "h", 1, "Schlaf der letzten sieben Nächte",
                                goal=goal / 60)
    if avg <= goal - 30:
        return Finding(
            "schlaf", WARN, "Schlaf", "Dir fehlen aus den letzten Nächten",
            f"{util.fmt_minutes(debt)} Schlaf.", f"−{util.fmt_minutes(debt)}",
            "Schlafmangel summiert sich: Ruhepuls, Stimmung und Leistung leiden zuerst. "
            "Zwei, drei frühere Abende holen viel davon wieder auf.",
            stats, steps, chart, ("bereiche.schlaf", {}), 1 + (goal - avg) / 30,
            basis=f"aus {len(nights)} Nächten")
    if under <= 1 and len(nights) >= 6:
        return Finding(
            "schlaf", GOOD, "Schlaf", "Du hast fast jede Nacht",
            "dein Schlafziel erreicht.", f"{len(nights) - under}/{len(nights)}",
            "Regelmäßig genug Schlaf ist die beste Erholung.",
            stats, steps, chart, ("bereiche.schlaf", {}), 0.8, basis=f"aus {len(nights)} Nächten")
    return None


def _clock(hours: float) -> str:
    minutes = int(round(hours * 60)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def bedtime(db, pid, person, today):
    points = _points(db, pid, "zubettgehen", today - timedelta(days=13), today)
    if len(points) < 8:
        return None
    values = [p["value"] for p in points]
    spread = _sd(values)
    if spread < 1.0:
        return None
    mid = _mean(values)
    dots = [{"day": p["day"], "value": p["value"], "tip": _tip(p["day"], f"ins Bett {_clock(p['value'])}")}
            for p in points]
    outside = sum(1 for v in values if abs(v - mid) > 0.5)
    start = today - timedelta(days=13)
    return Finding(
        "rhythmus", WARN, "Schlaf", "Deine Schlafenszeit schwankt",
        f"um ±{util.fmt_minutes(spread * 60)}.", f"±{util.fmt_minutes(spread * 60)}",
        "Ein gleichmäßiger Rhythmus (etwa ±30 Minuten) hilft dem Schlaf oft mehr als eine "
        "Stunde zusätzlich am Wochenende.",
        [(_clock(min(values)), "am frühesten"), (_clock(max(values)), "am spätesten"),
         (f"{outside} von {len(values)}", "Abende außerhalb ±30 min")],
        [f"Zubettgehen der letzten {len(values)} Nächte: " + ", ".join(_clock(v) for v in values),
         f"Mittel {_clock(mid)} Uhr, Standardabweichung {util.fmt_minutes(spread * 60)}",
         "Ab einer Stunde Standardabweichung zeigt das Cockpit diesen Befund."],
        lambda: charts.zone_dots(dots, start, today, (mid - 0.5, mid + 0.5), "Uhr", 2,
                                 "Zubettgehen der letzten zwei Wochen",
                                 f"dein Rhythmus · {_clock(mid - 0.5)} bis {_clock(mid + 0.5)}",
                                 "außerhalb", highlight="outside", y_format=_clock),
        ("auswertungen.index", {"wert": "zubettgehen"}), 1 + (spread - 1) * 2,
        basis=f"aus {len(values)} Nächten")


# ---------- Body and heart ----------

def weight_trend(db, pid, person, today):
    points = _points(db, pid, "weight", today - timedelta(days=27), today)
    if len(points) < 6:
        return None
    first = util.to_date(points[0]["day"])
    xs = [(util.to_date(p["day"]) - first).days for p in points]
    fit = auswertung.linear_fit(xs, [p["value"] for p in points])
    if not fit:
        return None
    per_week = fit[0] * 7
    if abs(per_week) < 0.25:
        return None
    goal = person["goal_weight_dg"] / 10 if person.get("goal_weight_dg") else None
    current = points[-1]["value"]
    if goal is not None:
        toward = (goal - current) * per_week > 0
        tone = GOOD if toward else WARN
    else:
        tone = INFO
    verb = "ab" if per_week < 0 else "zu"
    start = today - timedelta(days=27)
    return Finding(
        "gewicht", tone, "Körper", f"Du nimmst gerade {verb}:",
        f"{_n(abs(per_week), 1)} kg pro Woche.", f"{util.fmt_signed(per_week, 1)} kg",
        ("Das geht in Richtung deines Ziels." if tone == GOOD else
         "Das geht weg von deinem Ziel." if tone == WARN else
         "Ein Zielgewicht kannst du unter Personen eintragen, dann rechnet das Cockpit eine Prognose.")
        + " Mehr als 1 % des Körpergewichts pro Woche ist meist zu schnell.",
        [(f"{_n(points[0]['value'], 1)} → {_n(current, 1)} kg", "in vier Wochen"),
         (f"{util.fmt_signed(per_week, 1)} kg", "Trend pro Woche"),
         (f"{_n(goal, 1)} kg" if goal is not None else "–", "Zielgewicht")],
        [f"{len(points)} Messungen der letzten vier Wochen",
         f"Gerade durch alle Messungen (lineare Regression): {util.fmt_signed(fit[0] * 1000, 0)} g pro Tag",
         f"× 7 = {util.fmt_signed(per_week, 2)} kg pro Woche",
         "Ab 250 g pro Woche zeigt das Cockpit diesen Befund."],
        lambda: charts.line(points, start, today, "kg", 1, "Gewicht der letzten vier Wochen",
                            goal=goal, trend=False),
        ("bereiche.koerper", {}), 1 + abs(per_week), basis=f"aus {len(points)} Messungen")


def blood_pressure(db, pid, person, today):
    start = today - timedelta(days=29)
    readings = [r for r in store.readings(db, pid, ("bp_sys", "bp_dia"), start, today)
                if "bp_sys" in r["values"] and "bp_dia" in r["values"]]
    if len(readings) < 5:
        return None
    raised = [r for r in readings if bewertung.home_bp_raised(r["values"]["bp_sys"], r["values"]["bp_dia"])]
    share = len(raised) / len(readings)
    sys_avg = _mean([r["values"]["bp_sys"] for r in readings])
    dia_avg = _mean([r["values"]["bp_dia"] for r in readings])
    by_day: dict[str, list] = {}
    for r in readings:
        by_day.setdefault(r["day"], []).append(r)
    days = [{"day": d, "source": rows[0]["source"],
             "sys": _mean([r["values"]["bp_sys"] for r in rows]),
             "dia": _mean([r["values"]["bp_dia"] for r in rows])} for d, rows in sorted(by_day.items())]
    stats = [(f"{_n(sys_avg)}/{_n(dia_avg)}", "Ø mmHg, 30 Tage"),
             (f"{len(raised)} von {len(readings)}", "Messungen ab 135/85"),
             (bewertung.bp_category(sys_avg, dia_avg)[1], "Einstufung des Mittels")]
    steps = [f"{len(readings)} Messungen in den letzten 30 Tagen, Ø {_n(sys_avg)}/{_n(dia_avg)} mmHg",
             f"Davon {len(raised)} ab 135/85, der Grenze für Messungen zu Hause (ESH 2023)",
             "Ab der Hälfte der Messungen zeigt das Cockpit diesen Befund."]
    chart = lambda: charts.blood_pressure(days, start, today, bewertung.bp_category)
    if share >= 0.5:
        return Finding(
            "blutdruck", WARN, "Herz", "Dein Blutdruck lag",
            f"bei {len(raised)} von {len(readings)} Messungen über 135/85.", f"{len(raised)}/{len(readings)}",
            "Orientierung, keine Diagnose: Bleibt das so, bespricht man es am besten mit der "
            "Hausarztpraxis. Gemessen wird morgens und abends in Ruhe, im Sitzen.",
            stats, steps, chart, ("bereiche.herz", {}), 2 + share * 2,
            basis=f"aus {len(readings)} Messungen")
    if not raised and sys_avg < 120 and dia_avg < 80:
        return Finding(
            "blutdruck", GOOD, "Herz", "Dein Blutdruck ist", "im optimalen Bereich.",
            f"{_n(sys_avg)}/{_n(dia_avg)}", "Alle Messungen der letzten 30 Tage lagen unter 120/80.",
            stats, steps, chart, ("bereiche.herz", {}), 0.6, basis=f"aus {len(readings)} Messungen")
    return None


# ---------- Habits ----------

def step_streak(db, pid, person, today):
    if not person.get("goal_steps"):
        return None
    rec = auswertung.records(db, pid, "steps", person, today)
    current = rec.get("current") or 0
    if current < 5:
        return None
    start = today - timedelta(days=20)
    points = store.daily_series(db, pid, "steps", start, today)
    return Finding(
        "serie", GOOD, "Bewegung", "Du hast dein Schrittziel",
        f"{current} Tage in Folge geschafft.", f"{current} Tage",
        f"Deine längste Serie bisher: {rec.get('longest', current)} Tage. Weiter so.",
        [(f"{current} Tage", "aktuelle Serie"), (f"{rec.get('longest', current)} Tage", "längste Serie"),
         (_n(person["goal_steps"]), "Schritte als Ziel")],
        [f"Ziel: {_n(person['goal_steps'])} Schritte am Tag",
         f"Rückwärts ab heute (oder gestern, wenn heute noch läuft) jeden Tag mit erreichtem Ziel gezählt: {current}",
         "Ab fünf Tagen zeigt das Cockpit diese Serie."],
        lambda: charts.bars(points, start, today, "", 0, "Schritte der letzten drei Wochen",
                            goal=person["goal_steps"]),
        ("main.history", {"metric": "steps"}), 0.8 + current / 10, basis=f"seit {current} Tagen")


def weekday_gap(db, pid, person, today):
    points = store.daily_series(db, pid, "steps", today - timedelta(days=83), today - timedelta(days=1))
    if len(points) < 56:
        return None
    profile = auswertung.weekday_profile(points)
    present = [v for v in profile if v is not None]
    if len(present) < 7:
        return None
    avg = _mean(present)
    low = min(range(7), key=lambda i: profile[i])
    if profile[low] >= avg * 0.6:
        return None
    pct = (1 - profile[low] / avg) * 100
    return Finding(
        "wochentag", INFO, "Muster", f"Am {WEEKDAYS_LONG[low]} gehst du",
        f"{_n(pct)} % weniger als sonst.", f"−{_n(pct)} %",
        f"Im Schnitt {_n(profile[low])} Schritte statt {_n(avg)}. Ein fester Spaziergang an "
        f"diesem Tag gleicht viel aus.",
        [(_n(profile[low]), f"Ø am {WEEKDAYS_LONG[low]}"), (_n(avg), "Ø aller Wochentage"),
         (f"{len(points)} Tage", "ausgewertet")],
        [f"Schritte der letzten zwölf Wochen nach Wochentag gemittelt: "
         + ", ".join(f"{util.WEEKDAYS[i]} {_n(v)}" for i, v in enumerate(profile)),
         f"{WEEKDAYS_LONG[low]}: {_n(profile[low])} ÷ {_n(avg)} = {_n(100 - pct)} %",
         "Unter 60 % des Mittels zeigt das Cockpit diesen Befund."],
        lambda: charts.columns(util.WEEKDAYS, profile, "Schritte", 0, "Schritte je Wochentag",
                               highlight="min"),
        ("auswertungen.index", {"wert": "steps"}), 0.9, basis=f"aus {len(points)} Tagen")


def relationship(db, pid, person, today):
    found = auswertung.insights(db, pid, today, days=120, minimum=0.35)
    if not found:
        return None
    best = rel = found[0]
    x, y = rel["x"], rel["y"]
    lag_text = " (am Tag danach)" if rel["lag"] else ""
    pts = [(a, b, f"{auswertung.fmt(x.key, a)} → {auswertung.fmt(y.key, b)}") for a, b, *_ in rel["points"]]
    return Finding(
        f"zusammenhang-{x.key}-{y.key}", INFO, "Zusammenhang", "Zusammenhang erkannt:",
        f"{best['title']}.", f"r = {_n(rel['r'], 2)}",
        best["sentence"] + (f" {rel['effect']}." if rel.get("effect") else "")
        + " Zusammenhang heißt nicht Ursache.",
        [(_n(rel["r"], 2), "Korrelation r"), (rel["level"], "Stärke"), (str(rel["n"]), "gemeinsame Tage")],
        [f"Für {rel['n']} Tage beide Werte gesucht: {x.label} und {y.label}{lag_text}",
         f"Korrelation nach Pearson: r = {_n(rel['r'], 2)} ({rel['text']})",
         "Ab |r| = 0,35 bei mindestens 20 Tagen zeigt das Cockpit diesen Befund."],
        lambda: charts.scatter(pts, (x.label, x.unit, x.decimals), (y.label, y.unit, y.decimals),
                               fit=rel["fit"]),
        ("auswertungen.zusammenhaenge", {"x": x.key, "y": y.key, "versatz": rel["lag"]}),
        abs(rel["r"]) * 2, basis=f"aus {rel['n']} Tagen")


RULES = [resting_pulse, hrv, easy_trainings, load_jump, sleep_debt, bedtime, weight_trend,
         blood_pressure, step_streak, weekday_gap, relationship]


def _stamp(db, pid) -> tuple:
    row = db.execute(
        "SELECT (SELECT COUNT(*) || ':' || COALESCE(MAX(updated_at), '') FROM daily_values WHERE person_id = ?),"
        " (SELECT COUNT(*) || ':' || COALESCE(MAX(id), 0) FROM measurements WHERE person_id = ?),"
        " (SELECT COUNT(*) || ':' || COALESCE(MAX(id), 0) FROM workouts WHERE person_id = ?),"
        " (SELECT COUNT(*) || ':' || COALESCE(MAX(id), 0) FROM sleep WHERE person_id = ?)",
        (pid, pid, pid, pid)).fetchone()
    return tuple(row)


def compute(db, pid: int, person: dict, today=None) -> list[Finding]:
    """All findings for a person, most important first (cached for a few minutes)."""
    today = util.to_date(today) or util.today()
    cache_key = (pid, today.isoformat(), _stamp(db, pid), tuple(sorted(person.items())))
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    year, week, _ = today.isocalendar()
    found = []
    for rule in RULES:
        try:
            finding = rule(db, pid, person, today)
        except Exception:  # one broken rule must not take the pages down
            log.exception("Befund-Regel %s fehlgeschlagen", rule.__name__)
            continue
        if finding:
            finding.score *= TONE_WEIGHT[finding.tone]
            finding.key = f"{finding.rule}-{year}-{week:02d}"
            found.append(finding)
    found.sort(key=lambda f: -f.score)
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[cache_key] = (time.monotonic(), found)
    return found


def clear_cache() -> None:
    _CACHE.clear()


# ---------- Seen ----------

def seen(person: dict) -> list[str]:
    try:
        keys = json.loads(person.get("seen_findings") or "[]")
    except ValueError:
        return []
    return [k for k in keys if isinstance(k, str) and KEY_PATTERN.match(k)]


def mark_seen(db, pid: int, person: dict, keys) -> None:
    """Remember finding keys as seen (the newest few dozen are enough)."""
    known = seen(person)
    for key in keys:
        if KEY_PATTERN.match(key) and key not in known:
            known.append(key)
    db.execute("UPDATE persons SET seen_findings = ? WHERE id = ?",
               (json.dumps(known[-SEEN_KEEP:]), pid))


def news(findings: list[Finding], person: dict) -> list[Finding]:
    """Findings the person has not seen yet, most important first (for the toast; plain
    patterns are not announced)."""
    known = set(seen(person))
    return [f for f in findings if f.key not in known and f.tone != INFO]


def warnings(findings: list[Finding]) -> int:
    return sum(1 for f in findings if f.tone == WARN)
