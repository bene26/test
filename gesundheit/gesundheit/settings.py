"""App-wide single values (retention, Withings history). Stored in the settings table."""

# key: default (int or None). Everything is an integer, None means "not set".
# Goals, height and the Garmin switch belong to each person (persons.py).
DEFAULTS: dict[str, int | None] = {
    "retention_days": 0,          # 0 = keep forever
    "withings_backfill_days": 365,
}


def get(db, key: str):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None or row["value"] == "":
        return DEFAULTS[key]
    try:
        return int(row["value"])
    except ValueError:
        return DEFAULTS[key]


def get_all(db) -> dict:
    values = dict(DEFAULTS)
    for row in db.execute("SELECT key, value FROM settings"):
        if row["key"] in DEFAULTS:
            try:
                values[row["key"]] = int(row["value"]) if row["value"] != "" else None
            except ValueError:
                pass
    return values


def put(db, key: str, value) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, "" if value is None else str(int(value))),
    )
