"""Outlook ("Ausblick"): how values could go on, in a positive and in a negative way.

Every value gets three paths from today, all taken from the person's own past:
- "wie bisher": the trend of the last eight weeks carried on;
- "positiv": as in the person's best four weeks of the last year;
- "negativ": as in their weakest four weeks.

Two kinds of values:
- trends (weight, body fat, VO2max): the rate per week of those weeks goes on and fades out
  over about twelve weeks (habits rarely stay at an extreme for months), capped at a safe rate;
- levels (resting pulse, HRV, steps, sleep): the value moves towards the level of those weeks,
  most of the way within three weeks.
Fitness is simulated from the training load: as before, built up step by step, or a break.

For every value the outlook also shows what was different in the best weeks compared with the
weakest (sleep, steps, training, bedtime): a correlation, not a proof. Scenarios, not a
prediction.
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import auswertung, belastung, bewertung, charts, util
from .auswertung import KEYS

HORIZONS = {4: "4 Wochen", 12: "3 Monate", 26: "6 Monate"}
HORIZONS_IN = {4: "4 Wochen", 12: "3 Monaten", 26: "6 Monaten"}   # "in 3 Monaten"
DEFAULT_HORIZON = 12
WINDOW_DAYS = 28
TREND_FADE_WEEKS = 12
BUILD_CAP = 1.3          # the positive fitness path builds up to 30 % more load, not further
LEVEL_WEEKS = 3
EXPECTED_LEVEL_WEEKS = 4
# Fastest change per week that a scenario may assume (trend values).
CAPS = {"weight": lambda now: now * 0.01, "fat_ratio": lambda now: 0.4, "vo2max": lambda now: 0.4,
        "circ_waist": lambda now: 1.0}
TREND_KEYS = ("weight", "circ_waist", "fat_ratio", "vo2max")
LEVEL_KEYS = ("resting_hr", "hrv", "steps", "schlaf_dauer")
LEVER_KEYS = ("schlaf_dauer", "steps", "training_min", "zubettgehen", "stress_avg")
LABELS = {"gut": "Positiv", "erwartet": "Wie bisher", "schlecht": "Negativ"}
NEUTRAL_LABELS = {"gut": "Niedriger", "erwartet": "Wie bisher", "schlecht": "Höher"}


@dataclass
class Path:
    key: str                      # gut, erwartet, schlecht
    label: str
    values: list                  # [(date, value)] daily from today to the end
    why: str                      # where the path comes from
    goal_day: date | None = None

    @property
    def end(self) -> float:
        return self.values[-1][1]


@dataclass
class Outlook:
    key: str
    label: str
    unit: str
    decimals: int
    kind: str                     # trend, niveau, fitness
    direction: str                # up, down or "" (neutral: lower and higher instead)
    current: float
    history: list                 # [(date, value)] for the chart, as long as the horizon
    paths: dict                   # key -> Path
    days: int
    goal: float | None = None
    levers: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    basis: str = ""
    extra: dict = field(default_factory=dict)

    def fmt(self, value) -> str:
        if self.key in KEYS:
            return auswertung.fmt(self.key, value)
        return util.fmt_num(value, self.decimals) + (f" {self.unit}" if self.unit else "")

    def change(self, path_key: str) -> str:
        diff = self.paths[path_key].end - self.current
        if self.unit == "h":
            return ("+" if diff >= 0 else "−") + util.fmt_minutes(abs(diff) * 60)
        return util.fmt_signed(diff, self.decimals) + (f" {self.unit}" if self.unit else "")

    @property
    def summary(self) -> str:
        p = self.paths
        low, high = sorted((p["gut"].end, p["schlecht"].end))
        return (f"Wie bisher {self.fmt(p['erwartet'].end)} in {_horizon_text(self.days)}; "
                f"Spanne von {self.fmt(low)} bis {self.fmt(high)}.")

    def chart(self):
        return charts.fan(self.history, self.paths, self.days, self.unit, self.decimals,
                          f"{self.label}: Verlauf und Szenarien", self.fmt, self.goal,
                          neutral=not self.direction)


def _horizon_text(days: int) -> str:
    weeks = round(days / 7)
    return HORIZONS_IN.get(weeks) or (f"{weeks} Wochen" if weeks != 1 else "einer Woche")


def _points(db, pid, key, start, end) -> list[tuple]:
    return [(util.to_date(p["day"]), p["value"]) for p in auswertung.series(db, pid, key, start, end)]


def _rolling(points: list[tuple], days: int = 7) -> list[tuple]:
    out = []
    for i, (day, _v) in enumerate(points):
        window = [v for d, v in points[max(0, i - days * 2):i + 1] if (day - d).days < days]
        out.append((day, sum(window) / len(window)))
    return out


def slope_per_week(points: list[tuple]) -> float | None:
    if len(points) < 4 or (points[-1][0] - points[0][0]).days < 14:
        return None
    first = points[0][0]
    fit = auswertung.linear_fit([(d - first).days for d, _ in points], [v for _, v in points])
    return fit[0] * 7 if fit else None


def windows(points: list[tuple], today: date, stat: str, min_count: int) -> list[dict]:
    """Four-week windows of the last year, one per week, with their mean or slope."""
    by_day = dict(points)
    out = []
    end = today
    while end - timedelta(days=WINDOW_DAYS - 1) >= today - timedelta(days=364):
        start = end - timedelta(days=WINDOW_DAYS - 1)
        inside = [(d, by_day[d]) for d in util.days(start, end) if d in by_day]
        if len(inside) >= min_count:
            value = (statistics.mean(v for _, v in inside) if stat == "mean"
                     else slope_per_week(inside))
            if value is not None:
                out.append({"start": start, "end": end, "value": value})
        end -= timedelta(days=7)
    return out


def window_text(w: dict) -> str:
    return f"{w['start'].day}.{w['start'].month}. bis {w['end'].day}.{w['end'].month}."


def fade(rate_per_week: float, days: int, weeks: float) -> float:
    """Change after `days` when a weekly rate fades out over `weeks`."""
    return rate_per_week * weeks * (1 - math.exp(-days / (7 * weeks)))


def approach(current: float, target: float, days: int, weeks: float) -> float:
    return target + (current - target) * math.exp(-days / (7 * weeks))


def _direction(key: str, person: dict, current: float) -> str:
    if key == "weight":
        if person.get("goal_weight_dg"):
            return "down" if person["goal_weight_dg"] / 10 < current else "up"
        value = bewertung.bmi(current, person.get("height_cm"))
        if value is None:
            return ""
        return "down" if value >= 25 else "up" if value < 18.5 else ""
    return KEYS[key].good if key in KEYS else "up"


def _better(direction: str, a: float, b: float) -> bool:
    return a < b if direction == "down" else a > b


def _best_worst(direction: str, wins: list[dict]) -> tuple[dict, dict]:
    """(best, worst) window; for neutral values (lowest, highest)."""
    low = min(wins, key=lambda w: w["value"])
    high = max(wins, key=lambda w: w["value"])
    if direction == "up":
        return high, low
    return low, high


def _labels(direction: str) -> dict:
    return LABELS if direction else NEUTRAL_LABELS


def _goal_day(values: list[tuple], goal: float | None, current: float):
    if goal is None or goal == current:
        return None
    for day, value in values:
        if (value <= goal) if goal < current else (value >= goal):
            return day
    return None


def levers(db, pid: int, key: str, best: dict, worst: dict) -> list[str]:
    """What was different in the best four weeks compared with the weakest (largest first)."""
    found = []
    for lever in LEVER_KEYS:
        if lever == key or lever not in KEYS:
            continue
        good = [v for _, v in _points(db, pid, lever, best["start"], best["end"])]
        bad = [v for _, v in _points(db, pid, lever, worst["start"], worst["end"])]
        if len(good) < 10 or len(bad) < 10:
            continue
        mg, mb = statistics.mean(good), statistics.mean(bad)
        if lever == "zubettgehen":
            size = abs(mg - mb) / 0.5           # half an hour counts like 100 %
        else:
            base = (abs(mg) + abs(mb)) / 2 or 1
            size = abs(mg - mb) / base / 0.08   # 8 % counts like 100 %
        if size < 1:
            continue
        found.append((size, f"{KEYS[lever].label}: {auswertung.fmt(lever, mg)} in den besten, "
                            f"{auswertung.fmt(lever, mb)} in den schwächsten Wochen"))
    return [text for _size, text in sorted(found, reverse=True)[:3]]


def trend(db, pid: int, person: dict, key: str, today: date, days: int) -> Outlook | None:
    meta = KEYS[key]
    points = _points(db, pid, key, today - timedelta(days=364), today)
    recent = [p for p in points if p[0] > today - timedelta(days=56)]
    if len(recent) < 6:
        return None
    first = recent[0][0]
    fit = auswertung.linear_fit([(d - first).days for d, _ in recent], [v for _, v in recent])
    if not fit:
        return None
    rate_now = fit[0] * 7
    current = fit[1] + fit[0] * (today - first).days
    wins = windows(points, today, "slope", 4)
    if len(wins) < 4:
        return None
    direction = _direction(key, person, current)
    best, worst = _best_worst(direction, wins)
    cap = CAPS[key](current)

    def clamp(rate):
        return max(-cap, min(cap, rate))
    if direction:
        good_rate = best["value"] if _better(direction, best["value"], rate_now) else rate_now
        bad_rate = worst["value"] if _better(direction, rate_now, worst["value"]) else rate_now
    else:
        good_rate, bad_rate = min(best["value"], rate_now), max(worst["value"], rate_now)
    rates = {"gut": clamp(good_rate), "erwartet": clamp(rate_now), "schlecht": clamp(bad_rate)}
    goal = person["goal_weight_dg"] / 10 if key == "weight" and person.get("goal_weight_dg") else None
    labels = _labels(direction)
    unit = f" {meta.unit}" if meta.unit else ""
    if direction:
        good_name, bad_name = "besten", "schwächsten"
    else:
        good_name, bad_name = "am stärksten fallenden", "am stärksten steigenden"
    whys = {
        "gut": (f"wie in deinen {good_name} vier Wochen ({window_text(best)}): "
                f"{util.fmt_signed(best['value'], 2)}{unit} pro Woche"
                if rates["gut"] != rates["erwartet"] else
                "du bist schon so gut unterwegs wie in deinen besten Wochen: der Trend geht weiter"),
        "erwartet": f"Trend der letzten acht Wochen: {util.fmt_signed(rate_now, 2)}{unit} pro Woche",
        "schlecht": (f"wie in deinen {bad_name} vier Wochen ({window_text(worst)}): "
                     f"{util.fmt_signed(worst['value'], 2)}{unit} pro Woche"
                     if rates["schlecht"] != rates["erwartet"] else
                     "so schwach wie jetzt war es im letzten Jahr nie länger: der Trend geht weiter"),
    }
    paths = {}
    for k, rate in rates.items():
        values = [(today + timedelta(days=d), current + fade(rate, d, TREND_FADE_WEEKS))
                  for d in range(days + 1)]
        paths[k] = Path(k, labels[k], values, whys[k], _goal_day(values, goal, current))
    history = [p for p in points if p[0] > today - timedelta(days=days)]
    return Outlook(
        key, meta.label, meta.unit, meta.decimals, "trend", direction, current, history, paths,
        days, goal, levers(db, pid, key, best, worst) if direction else [],
        [f"Heute laut Trend der letzten acht Wochen: {auswertung.fmt(key, current)}",
         f"{len(wins)} Vier-Wochen-Abschnitte im letzten Jahr, je Abschnitt die Veränderung pro Woche "
         "(Gerade durch die Messungen)",
         f"Die Raten flachen über etwa {TREND_FADE_WEEKS} Wochen ab; höchstens "
         f"{util.fmt_num(cap, 2)}{unit} pro Woche",
         "Nur Szenarien aus deiner eigenen Vergangenheit, keine Vorhersage."],
        f"aus {len(points)} Messungen", {"best": best, "worst": worst, "rates": rates})


def level(db, pid: int, person: dict, key: str, today: date, days: int) -> Outlook | None:
    meta = KEYS[key]
    points = _points(db, pid, key, today - timedelta(days=364), today)
    last14 = [v for d, v in points if d > today - timedelta(days=14)]
    last56 = [p for p in points if p[0] > today - timedelta(days=56)]
    if len(last14) < 7 or len(last56) < 21:
        return None
    wins = windows(points, today, "mean", 14)
    if len(wins) < 4:
        return None
    current = statistics.mean(last14)
    rate_now = slope_per_week(last56) or 0.0
    direction = meta.good
    best, worst = _best_worst(direction, wins)
    good_target = best["value"] if _better(direction, best["value"], current) else current
    bad_target = worst["value"] if _better(direction, current, worst["value"]) else current
    lo, hi = min(w["value"] for w in wins), max(w["value"] for w in wins)
    labels = _labels(direction)
    paths = {
        "gut": Path("gut", labels["gut"], [(today + timedelta(days=d), approach(current, good_target, d, LEVEL_WEEKS))
                                           for d in range(days + 1)],
                    f"wie in deinen besten vier Wochen ({window_text(best)}): Ø {auswertung.fmt(key, best['value'])}"
                    if good_target != current else "du bist schon auf deinem besten Niveau: es bleibt so"),
        "erwartet": Path("erwartet", labels["erwartet"],
                         [(today + timedelta(days=d),
                           min(hi, max(lo, current + fade(rate_now, d, EXPECTED_LEVEL_WEEKS))))
                          for d in range(days + 1)],
                         f"Trend der letzten acht Wochen läuft langsam aus (Ø heute {auswertung.fmt(key, current)})"),
        "schlecht": Path("schlecht", labels["schlecht"],
                         [(today + timedelta(days=d), approach(current, bad_target, d, LEVEL_WEEKS))
                          for d in range(days + 1)],
                         f"wie in deinen schwächsten vier Wochen ({window_text(worst)}): Ø {auswertung.fmt(key, worst['value'])}"
                         if bad_target != current else "schwächer als jetzt war es im letzten Jahr nicht"),
    }
    goal = person.get(meta.goal_field) if meta.goal_field else None
    if goal and key == "schlaf_dauer":
        goal = goal / 60
    history = _rolling(points)
    history = [p for p in history if p[0] > today - timedelta(days=days)]
    return Outlook(
        key, meta.label, meta.unit, meta.decimals, "niveau", direction, current, history, paths, days,
        goal, levers(db, pid, key, best, worst),
        [f"Heute: Schnitt der letzten 14 Tage, {auswertung.fmt(key, current)}",
         f"{len(wins)} Vier-Wochen-Abschnitte im letzten Jahr; bester Schnitt {auswertung.fmt(key, best['value'])}, "
         f"schwächster {auswertung.fmt(key, worst['value'])}",
         f"Der Wert bewegt sich in etwa {LEVEL_WEEKS} Wochen zum größten Teil dorthin; „wie bisher“ "
         "folgt dem Trend der letzten acht Wochen und bleibt in deiner bisherigen Spanne",
         "Die Linie in der Vergangenheit ist der Schnitt über jeweils sieben Tage."],
        f"aus {len(points)} Tagen", {"best": best, "worst": worst})


def fitness(db, pid: int, person: dict, today: date, days: int) -> Outlook | None:
    """Fitness (42-day load average) under three ways of training from now on."""
    warmup = 180
    start = today - timedelta(days=warmup + days)
    loads = belastung.daily(db, pid, person, start, today)
    recent = [d for d in loads if d > (today - timedelta(days=42)).isoformat()]
    if len(recent) < 21:
        return None
    ctl = atl = 0.0
    history = []
    for day in util.days(start, today):
        load = loads.get(day.isoformat(), 0.0)
        ctl += (load - ctl) / belastung.FITNESS_DAYS
        atl += (load - atl) / belastung.FATIGUE_DAYS
        if day > today - timedelta(days=days):
            history.append((day, ctl))
    usual = statistics.mean(loads.get((today - timedelta(days=n)).isoformat(), 0.0) for n in range(28))
    if usual < 5:
        return None

    def plan(name, d):
        week = (d - 1) // 7
        if name == "erwartet":
            return usual
        if name == "schlecht":
            return usual * 0.3
        steps = week - week // 4 + 1        # three weeks up, one easy week
        build = min(1.05 ** steps, BUILD_CAP)
        return usual * build * (0.6 if week % 4 == 3 else 1.0)

    paths = {}
    whys = {"gut": "drei Wochen je 5 % mehr Belastung, dann eine ruhige Woche, bis höchstens 30 % "
                   "über dem jetzigen Schnitt",
            "erwartet": f"jeden Tag so viel wie im Schnitt der letzten vier Wochen (Ø {util.fmt_num(usual)} Punkte)",
            "schlecht": "nur noch ein Drittel davon, etwa bei Krankheit oder wenig Zeit"}
    ends = {}
    for name in ("gut", "erwartet", "schlecht"):
        c, a = ctl, atl
        values = [(today, c)]
        for d in range(1, days + 1):
            load = plan(name, d)
            c += (load - c) / belastung.FITNESS_DAYS
            a += (load - a) / belastung.FATIGUE_DAYS
            values.append((today + timedelta(days=d), c))
        ends[name] = round(c - a)
        paths[name] = Path(name, LABELS[name], values, whys[name] + f"; Form am Ende {util.fmt_signed(c - a, 0)}")
    return Outlook(
        "fitness", "Fitness", "", 0, "fitness", "up", ctl, history, paths, days, None, [],
        ["Fitness ist der gleitende 42-Tage-Schnitt deiner Belastung (Trainingsimpuls nach Banister)",
         f"Heute {util.fmt_num(ctl)}, Ermüdung {util.fmt_num(atl)}",
         "Für jedes Szenario wird die Belastung Tag für Tag weitergerechnet",
         "Form = Fitness minus Ermüdung; stark negativ heißt: Erholung einplanen"],
        f"aus {len(loads)} Tagen", {"form_end": ends})


def all_outlooks(db, pid: int, person: dict, today=None, weeks: int = DEFAULT_HORIZON) -> list[Outlook]:
    today = util.to_date(today) or util.today()
    days = weeks * 7
    out = []
    for key in TREND_KEYS:
        out.append(trend(db, pid, person, key, today, days))
    hrv_key = "hrv_rmssd" if auswertung.series(db, pid, "hrv_rmssd", today - timedelta(days=56), today) else "hrv_sdnn"
    for key in LEVEL_KEYS:
        out.append(level(db, pid, person, hrv_key if key == "hrv" else key, today, days))
    out.append(fitness(db, pid, person, today, days))
    # without any spread there is nothing to choose between
    return [o for o in out if o and abs(o.paths["gut"].end - o.paths["schlecht"].end) >= 10 ** -o.decimals]


def weekly_scenarios(db, pid: int, key: str, today: date, direction: str = "up") -> dict | None:
    """Best, usual and weakest four-week mean of a level value (for the step forecast)."""
    points = _points(db, pid, key, today - timedelta(days=364), today - timedelta(days=1))
    wins = windows(points, today - timedelta(days=1), "mean", 14)
    if len(wins) < 4:
        return None
    best, worst = _best_worst(direction, wins)
    return {"best": best, "worst": worst}
