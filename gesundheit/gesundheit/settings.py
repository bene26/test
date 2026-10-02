"""Single values: profile, goals, retention, connection options. Stored in the settings table."""

# key: default (int or None). Everything is an integer, None means "not set".
DEFAULTS: dict[str, int | None] = {
    "height_cm": None,
    "goal_steps": 10000,
    "goal_active_min": 30,
    "goal_active_kcal": 500,
    "goal_sleep_min": 480,
    "goal_weight_dg": None,       # target weight in tenths of a kilogram (723 = 72,3 kg)
    "retention_days": 0,          # 0 = keep forever
    "garmin_enabled": 0,
    "garmin_backfill_days": 30,
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
