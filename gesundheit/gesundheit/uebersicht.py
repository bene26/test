"""Building blocks of the overview page: the 3D skyline of the year and its key figures.

Everything is computed from the stored values of one person; nothing leaves the NAS.
"""

from datetime import timedelta

from . import belastung, charts, store, util
from .auswertung import WEEKDAYS_LONG
from .katalog import APPLE_SOURCES, MANUAL_SOURCES

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


SOURCE_TILES = [
    ("withings", "Withings", "Waage, Blutdruck, Schlafmatte, Thermometer", ("withings",)),
    ("garmin", "Garmin direkt", "Body Battery, Stress, HRV, Schlaf, Trainings", ("garmin",)),
    ("apple", "Apple Health", "Apple Watch, iPhone und Apps, die dort schreiben", APPLE_SOURCES),
    ("manuell", "Maßband und Praxis", "Umfänge und Körperanalyse, selbst eingetragen", MANUAL_SOURCES),
]


def _recent_count(db, pid: int, sources: tuple, since: str) -> int:
    marks = ", ".join("?" for _ in sources)
    total = 0
    for table, column in (("daily_values", "day"), ("measurements", "day"), ("sleep", "night"),
                          ("workouts", "day")):
        total += db.execute(f"SELECT COUNT(*) FROM {table} WHERE person_id = ? AND source IN ({marks}) "
                            f"AND {column} >= ?", (pid, *sources, since)).fetchone()[0]
    return total


def sources(db, pid: int, person: dict, today) -> list[dict]:
    """One tile per source with its state, for the overview (managing stays on "Quellen")."""
    today = util.to_date(today)
    since = (today - timedelta(days=6)).isoformat()
    connections = {r["provider"]: r for r in db.execute(
        "SELECT provider, last_ok, last_error FROM connections WHERE person_id = ?", (pid,))}
    last_import = db.execute("SELECT status, finished_at FROM imports WHERE person_id = ? "
                             "ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
    tiles = []
    for key, name, devices, keys in SOURCE_TILES:
        tile = {"key": key, "name": name, "devices": devices,
                "count": _recent_count(db, pid, keys, since)}
        if key == "manuell":
            marks = ", ".join("?" for _ in keys)
            last = db.execute(f"SELECT MAX(measured_at) FROM measurements WHERE person_id = ? "
                              f"AND source IN ({marks})", (pid, *keys)).fetchone()[0]
            if not last:
                tile.update(state="aus", status="noch nichts eingetragen")
            else:
                recent = (today - util.to_date(last)).days <= 31
                tile.update(state="an" if recent else "aus",
                            status=f"zuletzt {util.fmt_ago(last)}")
        elif key == "apple":
            if not last_import:
                tile.update(state="aus", status="noch kein Import")
            elif last_import["status"] == "fehler":
                tile.update(state="fehler", status="letzter Import mit Fehler")
            elif last_import["status"] != "fertig":
                tile.update(state="laeuft", status="Import läuft")
            else:
                tile.update(state="an", status=f"Import {util.fmt_ago(last_import['finished_at'])}")
        else:
            c = connections.get(key)
            if key == "garmin" and not person.get("garmin_enabled"):
                tile.update(state="aus", status="ausgeschaltet")
            elif not c:
                tile.update(state="aus", status="nicht verbunden")
            elif c["last_error"]:
                tile.update(state="fehler", status="Abgleich mit Fehler")
            else:
                tile.update(state="an", status=f"abgeglichen {util.fmt_ago(c['last_ok'])}"
                            if c["last_ok"] else "verbunden")
        tiles.append(tile)
    return tiles
