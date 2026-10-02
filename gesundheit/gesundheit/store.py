"""Writing and reading health values, with the source order per family.

Rule for every chart and number: per day (sleep: per night) the first source in the
family's order that has a value for that day wins. Values of different sources are never
added up or averaged together, so a step counted by the watch and the phone is not counted
twice, and a weight sent by Withings directly and again through Apple Health appears once.
"""

from datetime import date, datetime, timedelta

from . import util
from .katalog import FAMILIES, METRICS, SOURCES

AGG_SQL = {"mean": "AVG", "sum": "SUM", "min": "MIN", "max": "MAX"}
SLEEP_COLUMNS = ("bed_start", "bed_end", "asleep_min", "deep_min", "light_min", "rem_min",
                 "awake_min", "score", "hr_avg", "rr_avg")
WORKOUT_COLUMNS = ("kind", "started_at", "ended_at", "duration_min", "distance_km",
                   "energy_kcal", "hr_avg", "hr_max")


# ---------- Writing ----------

def clean(metric: str, value) -> float | None:
    """Value as float if it is a number inside the plausible range, else None."""
    meta = METRICS.get(metric)
    if meta is None or value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or not meta.lo <= number <= meta.hi:  # NaN or out of range
        return None
    return round(number, 4)


def add_measurement(db, metric: str, value, measured_at: datetime, source: str,
                    group_id: str = "") -> bool:
    number = clean(metric, value)
    if number is None or source not in SOURCES:
        return False
    db.execute(
        "INSERT INTO measurements (metric, value, measured_at, day, source, group_id) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(metric, source, measured_at) DO UPDATE SET "
        "value = excluded.value, group_id = excluded.group_id",
        (metric, number, util.stamp(measured_at), measured_at.date().isoformat(), source,
         group_id),
    )
    return True


def add_measurements(db, rows) -> int:
    """Bulk insert of (metric, value, measured_at: datetime, source, group_id)."""
    prepared = []
    for metric, value, measured_at, source, group_id in rows:
        number = clean(metric, value)
        if number is not None and source in SOURCES:
            prepared.append((metric, number, util.stamp(measured_at),
                             measured_at.date().isoformat(), source, group_id))
    db.executemany(
        "INSERT INTO measurements (metric, value, measured_at, day, source, group_id) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(metric, source, measured_at) DO UPDATE SET "
        "value = excluded.value, group_id = excluded.group_id", prepared)
    return len(prepared)


def set_daily(db, metric: str, day, source: str, value) -> bool:
    return set_daily_many(db, [(metric, day, source, value)]) == 1


def set_daily_many(db, rows) -> int:
    """Bulk upsert of (metric, day, source, value)."""
    stamp = util.stamp()
    prepared = []
    for metric, day, source, value in rows:
        number = clean(metric, value)
        if number is not None and source in SOURCES:
            prepared.append((metric, str(day)[:10], source, number, stamp))
    db.executemany(
        "INSERT INTO daily_values (metric, day, source, value, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(metric, day, source) DO UPDATE SET value = excluded.value, "
        "updated_at = excluded.updated_at", prepared)
    return len(prepared)


def _minutes(value, limit=24 * 60):
    if value is None:
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= limit else None


def upsert_sleep(db, night, source: str, data: dict) -> bool:
    """data: bed_start/bed_end (datetime), *_min (minutes), score, hr_avg, rr_avg."""
    if source not in SOURCES:
        return False
    row = {
        "bed_start": util.stamp(data["bed_start"]) if data.get("bed_start") else None,
        "bed_end": util.stamp(data["bed_end"]) if data.get("bed_end") else None,
        "asleep_min": _minutes(data.get("asleep_min")),
        "deep_min": _minutes(data.get("deep_min")),
        "light_min": _minutes(data.get("light_min")),
        "rem_min": _minutes(data.get("rem_min")),
        "awake_min": _minutes(data.get("awake_min")),
        "score": _minutes(data.get("score"), 100),
        "hr_avg": clean("resting_hr", data.get("hr_avg")) if data.get("hr_avg") else None,
        "rr_avg": clean("resp_rate", data.get("rr_avg")) if data.get("rr_avg") else None,
    }
    if not row["asleep_min"] and not row["bed_start"]:
        return False
    db.execute(
        f"INSERT INTO sleep (night, source, {', '.join(SLEEP_COLUMNS)}) "
        f"VALUES (?, ?, {', '.join('?' for _ in SLEEP_COLUMNS)}) "
        f"ON CONFLICT(night, source) DO UPDATE SET "
        + ", ".join(f"{c} = excluded.{c}" for c in SLEEP_COLUMNS),
        (str(night)[:10], source, *(row[c] for c in SLEEP_COLUMNS)),
    )
    return True


def _positive(value, limit):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 3) if 0 <= number <= limit else None


def upsert_workout(db, source: str, external_id: str, data: dict) -> bool:
    """data: kind, started_at/ended_at (datetime), duration_min, distance_km, energy_kcal,
    hr_avg, hr_max."""
    if source not in SOURCES or not data.get("started_at"):
        return False
    started = data["started_at"]
    row = {
        "kind": data.get("kind") or "sonstiges",
        "started_at": util.stamp(started),
        "ended_at": util.stamp(data["ended_at"]) if data.get("ended_at") else None,
        "duration_min": _positive(data.get("duration_min"), 7 * 24 * 60),
        "distance_km": _positive(data.get("distance_km"), 2000),
        "energy_kcal": _positive(data.get("energy_kcal"), 50000),
        "hr_avg": clean("hr_max", data.get("hr_avg")),
        "hr_max": clean("hr_max", data.get("hr_max")),
    }
    db.execute(
        f"INSERT INTO workouts (source, external_id, day, {', '.join(WORKOUT_COLUMNS)}) "
        f"VALUES (?, ?, ?, {', '.join('?' for _ in WORKOUT_COLUMNS)}) "
        f"ON CONFLICT(source, external_id) DO UPDATE SET day = excluded.day, "
        + ", ".join(f"{c} = excluded.{c}" for c in WORKOUT_COLUMNS),
        (source, str(external_id)[:100], started.date().isoformat(),
         *(row[c] for c in WORKOUT_COLUMNS)),
    )
    return True


# ---------- Source order ----------

def priority(db, family: str) -> list[str]:
    default = FAMILIES[family][2]
    row = db.execute("SELECT sources FROM source_priority WHERE family = ?",
                     (family,)).fetchone()
    order = [s for s in (row["sources"].split(",") if row else []) if s in SOURCES]
    seen = set(order)
    return order + [s for s in default if s not in seen]


def set_priority(db, family: str, order: list[str]) -> None:
    if family not in FAMILIES:
        raise KeyError(family)
    clean_order = [s for s in dict.fromkeys(order) if s in SOURCES]
    clean_order += [s for s in FAMILIES[family][2] if s not in clean_order]
    db.execute(
        "INSERT INTO source_priority (family, sources) VALUES (?, ?) "
        "ON CONFLICT(family) DO UPDATE SET sources = excluded.sources",
        (family, ",".join(clean_order)))


def reset_priority(db, family: str) -> None:
    db.execute("DELETE FROM source_priority WHERE family = ?", (family,))


def _pick(by_source: dict, order: list[str]):
    for source in order:
        if source in by_source:
            return source, by_source[source]
    return None, None


# ---------- Reading ----------

def _iso(value) -> str:
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)[:10]


def per_source(db, metric: str, start, end) -> dict[str, dict[str, float]]:
    """{day: {source: value}} with the metric's day aggregation applied per source."""
    meta = METRICS[metric]
    start, end = _iso(start), _iso(end)
    result: dict[str, dict[str, float]] = {}
    for row in db.execute(
            "SELECT day, source, value FROM daily_values WHERE metric = ? AND day BETWEEN ? AND ?",
            (metric, start, end)):
        result.setdefault(row["day"], {})[row["source"]] = row["value"]
    if meta.agg == "last":
        query = ("SELECT day, source, value, MAX(measured_at) FROM measurements "
                 "WHERE metric = ? AND day BETWEEN ? AND ? GROUP BY day, source")
    else:
        query = (f"SELECT day, source, {AGG_SQL[meta.agg]}(value) AS value FROM measurements "
                 "WHERE metric = ? AND day BETWEEN ? AND ? GROUP BY day, source")
    for row in db.execute(query, (metric, start, end)):
        result.setdefault(row["day"], {})[row["source"]] = row["value"]
    return result


def daily_series(db, metric: str, start, end) -> list[dict]:
    """[{day, value, source}] sorted by day, one entry per day that has a value."""
    order = priority(db, METRICS[metric].family)
    series = []
    for day, by_source in sorted(per_source(db, metric, start, end).items()):
        source, value = _pick(by_source, order)
        if source:
            series.append({"day": day, "value": value, "source": source})
    return series


def latest(db, metric: str, until=None) -> dict | None:
    """Most recent value (by the source order on that day), optionally up to a day."""
    until = _iso(until or util.today() + timedelta(days=1))
    row = db.execute(
        "SELECT MAX(day) FROM (SELECT MAX(day) AS day FROM measurements WHERE metric = ? "
        "AND day <= ? UNION ALL SELECT MAX(day) FROM daily_values WHERE metric = ? AND day <= ?)",
        (metric, until, metric, until)).fetchone()
    if not row or not row[0]:
        return None
    series = daily_series(db, metric, row[0], row[0])
    return series[-1] if series else None


def readings(db, metrics: tuple[str, ...], start, end) -> list[dict]:
    """Single readings grouped (e.g. systolic + diastolic + pulse), newest first.

    Per day only the readings of the first source in the family's order are kept.
    """
    family = METRICS[metrics[0]].family
    order = priority(db, family)
    marks = ",".join("?" for _ in metrics)
    groups: dict[tuple, dict] = {}
    for row in db.execute(
            f"SELECT metric, value, measured_at, day, source, group_id FROM measurements "
            f"WHERE metric IN ({marks}) AND day BETWEEN ? AND ?",
            (*metrics, _iso(start), _iso(end))):
        key = (row["source"], row["group_id"] or row["measured_at"])
        entry = groups.setdefault(key, {"measured_at": row["measured_at"], "day": row["day"],
                                        "source": row["source"], "values": {}})
        entry["values"][row["metric"]] = row["value"]
        entry["measured_at"] = min(entry["measured_at"], row["measured_at"])
    by_day: dict[str, set] = {}
    for entry in groups.values():
        by_day.setdefault(entry["day"], set()).add(entry["source"])
    winners = {day: next((s for s in order if s in sources), None)
               for day, sources in by_day.items()}
    kept = [e for e in groups.values() if winners[e["day"]] == e["source"]]
    return sorted(kept, key=lambda e: e["measured_at"], reverse=True)


def sleep_series(db, start, end) -> list[dict]:
    """One night per day (source order of 'schlaf'), sorted by night."""
    order = priority(db, "schlaf")
    nights: dict[str, dict[str, dict]] = {}
    for row in db.execute("SELECT * FROM sleep WHERE night BETWEEN ? AND ?",
                          (_iso(start), _iso(end))):
        nights.setdefault(row["night"], {})[row["source"]] = dict(row)
    result = []
    for night, by_source in sorted(nights.items()):
        source, row = _pick(by_source, order)
        if source:
            result.append(row)
    return result


def workouts(db, start, end) -> list[dict]:
    """Trainings newest first. The same training recorded by two sources (start within
    five minutes) appears once, from the first source in the order of 'aktivitaet'."""
    rank = {s: i for i, s in enumerate(priority(db, "aktivitaet"))}
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM workouts WHERE day BETWEEN ? AND ?", (_iso(start), _iso(end)))]
    rows.sort(key=lambda r: rank.get(r["source"], 99))
    kept: list[dict] = []
    for row in rows:
        started = util.to_datetime(row["started_at"])
        duplicate = any(
            k["source"] != row["source"]
            and abs((util.to_datetime(k["started_at"]) - started).total_seconds()) <= 300
            for k in kept)
        if not duplicate:
            kept.append(row)
    return sorted(kept, key=lambda r: r["started_at"], reverse=True)


def summary(values: list[float]) -> dict:
    if not values:
        return {"avg": None, "min": None, "max": None, "count": 0}
    return {"avg": sum(values) / len(values), "min": min(values), "max": max(values),
            "count": len(values)}


def sources_overview(db) -> dict[str, dict]:
    """Per source: number of values and the first and last day."""
    overview = {key: {"count": 0, "first": None, "last": None} for key in SOURCES}
    queries = [
        "SELECT source, COUNT(*), MIN(day), MAX(day) FROM measurements GROUP BY source",
        "SELECT source, COUNT(*), MIN(day), MAX(day) FROM daily_values GROUP BY source",
        "SELECT source, COUNT(*), MIN(night), MAX(night) FROM sleep GROUP BY source",
        "SELECT source, COUNT(*), MIN(day), MAX(day) FROM workouts GROUP BY source",
    ]
    for query in queries:
        for source, count, first, last in db.execute(query):
            entry = overview.setdefault(source, {"count": 0, "first": None, "last": None})
            entry["count"] += count
            entry["first"] = min(filter(None, (entry["first"], first)), default=None)
            entry["last"] = max(filter(None, (entry["last"], last)), default=None)
    return overview


HEALTH_TABLES = ("measurements", "daily_values", "sleep", "workouts")


def delete_source(db, source: str) -> int:
    total = 0
    for table in HEALTH_TABLES:
        total += db.execute(f"DELETE FROM {table} WHERE source = ?", (source,)).rowcount
    return total


def delete_all(db) -> int:
    total = 0
    for table in HEALTH_TABLES:
        total += db.execute(f"DELETE FROM {table}").rowcount
    db.execute("DELETE FROM imports")
    db.execute("DELETE FROM connections")
    db.execute("DELETE FROM source_priority")
    return total


def apply_retention(db, keep_days: int, today: date | None = None) -> int:
    """Delete values older than keep_days (0 = keep everything)."""
    if not keep_days:
        return 0
    cutoff = ((today or util.today()) - timedelta(days=keep_days)).isoformat()
    total = 0
    for table, column in (("measurements", "day"), ("daily_values", "day"),
                          ("sleep", "night"), ("workouts", "day")):
        total += db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,)).rowcount
    return total
