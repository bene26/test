"""Building blocks of the overview page: the 3D skyline of the year and its key figures.

Everything is computed from the stored values of one person; nothing leaves the NAS.
"""

from datetime import timedelta

from . import belastung, charts, store, util
from .auswertung import WEEKDAYS_LONG

PERIODS = {"3M": (91, "Deine letzten 3 Monate"), "6M": (182, "Deine letzten 6 Monate"),
           "12M": (364, "Dein Jahr · 12 Monate")}
DEFAULT_PERIOD = "12M"


def period_choice(value) -> str:
    return value if value in PERIODS else DEFAULT_PERIOD


def _big(value: float) -> tuple[float, int, str]:
    """(number, decimals, suffix) for a large total: millions get two decimals."""
    if value >= 1_000_000:
        return round(value / 1_000_000, 2), 2, " Mio."
    return round(value), 0, ""


def skyline(db, pid: int, person: dict, end, period: str = DEFAULT_PERIOD) -> dict:
    """Both skyline views (steps and load) for the period ending on 'end'."""
    days, label = PERIODS[period_choice(period)]
    end = util.to_date(end)
    start = end - timedelta(days=days - 1)
    steps = {p["day"]: p["value"] for p in store.daily_series(db, pid, "steps", start, end)}
    distance = {p["day"]: p["value"] for p in store.daily_series(db, pid, "distance_km", start, end)}
    active = {p["day"]: p["value"] for p in store.daily_series(db, pid, "active_min", start, end)}
    loads = belastung.daily(db, pid, person, start, end)
    trainings = store.workouts(db, pid, start, end)

    cells_steps, cells_load = [], []
    for day in util.days(start, end):
        key = day.isoformat()
        tip = [f"{WEEKDAYS_LONG[day.weekday()]}, {day.day}. {util.MONTHS_LONG[day.month - 1]}"]
        if key in steps:
            tip.append((util.fmt_num(steps[key]), "Schritte"))
        if key in loads:
            tip.append((util.fmt_num(loads[key]), "Belastungspunkte"))
        cells_steps.append({"day": day, "value": steps.get(key), "tip": tip})
        cells_load.append({"day": day, "value": loads.get(key), "tip": tip})

    views = []
    if steps:
        total = sum(steps.values())
        number, decimals, suffix = _big(total)
        sub = []
        if distance:
            sub.append(f"≈ {util.fmt_num(sum(distance.values()))} km")
        sub.append(f"{len(trainings)} Trainings")
        if active:
            sub.append(f"{util.fmt_num(sum(active.values()) / 60)} Stunden aktiv")
        views.append({
            "key": "schritte", "label": "Schritte", "number": number, "decimals": decimals,
            "suffix": suffix, "unit": "Schritte", "sub": " · ".join(sub),
            "chart": charts.skyline(cells_steps, "", 0,
                                    f"Schritte je Tag als 3D-Diagramm, {label}"),
        })
    if loads:
        total = sum(loads.values())
        number, decimals, suffix = _big(total)
        weekly: dict[tuple, float] = {}
        for key, value in loads.items():
            iso = util.to_date(key).isocalendar()
            weekly[(iso[0], iso[1])] = weekly.get((iso[0], iso[1]), 0.0) + value
        best_week = max(weekly.items(), key=lambda item: item[1])
        sub = [f"Ø {util.fmt_num(total / days)} pro Tag",
               f"stärkste Woche {util.fmt_num(best_week[1])} (KW {best_week[0][1]})",
               f"{len(trainings)} Trainings"]
        views.append({
            "key": "belastung", "label": "Belastung", "number": number, "decimals": decimals,
            "suffix": suffix, "unit": "Belastungspunkte", "sub": " · ".join(sub),
            "chart": charts.skyline(cells_load, "", 0,
                                    f"Belastung je Tag als 3D-Diagramm, {label}"),
        })
    return {"period": period_choice(period), "label": label, "views": views,
            "periods": list(PERIODS)}
