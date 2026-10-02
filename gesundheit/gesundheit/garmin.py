"""Garmin Connect directly, through the unofficial library `garminconnect` (off by default).

Garmin offers no official access for private persons, so this uses the same login as the
Garmin Connect app. It can break whenever Garmin changes something and may conflict with
Garmin's terms of use; the app works the same without it (Garmin values also arrive through
Apple Health when the Connect app writes there).

Only the tokens are stored (encrypted), never the password. With two-factor authentication
the half-finished login waits in memory for at most five minutes (single worker process).
"""

import logging
import secrets
import threading
import time
from datetime import date, timedelta

from . import store, util
from .katalog import GARMIN_WORKOUTS

log = logging.getLogger("gesundheit")
MFA_TTL = 300
PAUSE = 0.4  # seconds between days, to stay friendly with Garmin's servers


class GarminError(Exception):
    """Message is safe to show to the user (never contains passwords or tokens)."""


class AuthExpired(GarminError):
    pass


def available() -> bool:
    try:
        import garminconnect  # noqa: F401
    except Exception:
        return False
    return True


def _factory(**kwargs):
    from garminconnect import Garmin
    return Garmin(**kwargs)


# Replaced in tests.
FACTORY = _factory

_pending: dict[str, tuple[object, float]] = {}
_pending_lock = threading.Lock()


def _translate(exc: Exception) -> GarminError:
    name = type(exc).__name__
    if "Authentication" in name:
        return AuthExpired("Garmin hat die Anmeldung abgelehnt (E-Mail, Passwort oder Code "
                           "falsch, oder die Anmeldung ist abgelaufen).")
    if "TooManyRequests" in name:
        return GarminError("Garmin bremst gerade (zu viele Anfragen). Später noch einmal "
                           "versuchen.")
    return GarminError(f"Garmin nicht erreichbar oder Antwort unverständlich ({name}).")


def _cleanup_pending(now: float) -> None:
    for key in [k for k, (_api, created) in _pending.items() if now - created > MFA_TTL]:
        _pending.pop(key, None)


def start_login(email: str, password: str) -> tuple[str, str]:
    """('ok', tokens_json) or ('mfa', pending_id) when Garmin asks for a code."""
    try:
        api = FACTORY(email=email, password=password, return_on_mfa=True)
        status, _ = api.login()
    except GarminError:
        raise
    except Exception as exc:
        raise _translate(exc) from None
    if status == "needs_mfa":
        pending_id = secrets.token_urlsafe(16)
        with _pending_lock:
            now = time.monotonic()
            _cleanup_pending(now)
            _pending[pending_id] = (api, now)
        return "mfa", pending_id
    return "ok", api.client.dumps()


def finish_login(pending_id: str, code: str) -> str:
    with _pending_lock:
        _cleanup_pending(time.monotonic())
        entry = _pending.pop(pending_id, None)
    if entry is None:
        raise GarminError("Der Anmeldevorgang ist abgelaufen. Bitte noch einmal anmelden.")
    api = entry[0]
    try:
        api.resume_login(None, code)
    except Exception as exc:
        raise _translate(exc) from None
    return api.client.dumps()


def connect(tokens: str):
    """Client from stored tokens (refreshes them if they are about to expire)."""
    try:
        api = FACTORY()
        if len(tokens) > 512:
            api.login(tokenstore=tokens)
        else:
            api.client.loads(tokens)
    except Exception as exc:
        raise _translate(exc) from None
    return api


def dump_tokens(api) -> str:
    return api.client.dumps()


# ---------- Mapping ----------

def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _first(data):
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    return data if isinstance(data, dict) else {}


def store_summary(db, pid, day: str, summary: dict) -> int:
    if not isinstance(summary, dict):
        return 0
    distance = _num(summary.get("totalDistanceMeters"))
    moderate = _num(summary.get("moderateIntensityMinutes"))
    vigorous = _num(summary.get("vigorousIntensityMinutes"))
    stress = _num(summary.get("averageStressLevel"))
    rows = [
        ("steps", _num(summary.get("totalSteps"))),
        ("distance_km", distance / 1000 if distance is not None else None),
        ("active_kcal", _num(summary.get("activeKilocalories"))),
        ("floors", _num(summary.get("floorsAscended"))),
        ("active_min", (moderate or 0) + (vigorous or 0)
         if moderate is not None or vigorous is not None else None),
        ("resting_hr", _num(summary.get("restingHeartRate"))),
        ("hr_min", _num(summary.get("minHeartRate"))),
        ("hr_max", _num(summary.get("maxHeartRate"))),
        ("stress_avg", stress if stress is not None and stress >= 0 else None),
        ("body_battery_max", _num(summary.get("bodyBatteryHighestValue"))),
        ("body_battery_min", _num(summary.get("bodyBatteryLowestValue"))),
        ("spo2", _num(summary.get("averageSpo2"))),
        ("resp_rate", _num(summary.get("avgWakingRespirationValue"))),
    ]
    # A day the watch was not worn comes back with zeros: do not let it hide other sources.
    if not rows[0][1]:
        rows = [r for r in rows if r[0] not in ("steps", "distance_km", "active_kcal", "floors",
                                                 "active_min")]
    return store.set_daily_many(db, pid, [(m, day, "garmin", v) for m, v in rows if v is not None])


def store_sleep(db, pid, data: dict) -> int:
    dto = data.get("dailySleepDTO") if isinstance(data, dict) else None
    if not isinstance(dto, dict) or not _num(dto.get("sleepTimeSeconds")):
        return 0
    night = dto.get("calendarDate")
    if not isinstance(night, str) or len(night) != 10:
        return 0
    start, end = dto.get("sleepStartTimestampLocal"), dto.get("sleepEndTimestampLocal")
    scores = dto.get("sleepScores") if isinstance(dto.get("sleepScores"), dict) else {}
    overall = scores.get("overall") if isinstance(scores.get("overall"), dict) else {}

    def minutes(key):
        value = _num(dto.get(key))
        return value / 60 if value is not None else None

    return int(store.upsert_sleep(db, pid, night, "garmin", {
        "bed_start": util.wallclock_ms(start) if _num(start) else None,
        "bed_end": util.wallclock_ms(end) if _num(end) else None,
        "asleep_min": minutes("sleepTimeSeconds"), "deep_min": minutes("deepSleepSeconds"),
        "light_min": minutes("lightSleepSeconds"), "rem_min": minutes("remSleepSeconds"),
        "awake_min": minutes("awakeSleepSeconds"), "score": _num(overall.get("value")),
        "hr_avg": _num(dto.get("avgHeartRate")),
        "rr_avg": _num(dto.get("averageRespirationValue")),
    }))


def store_hrv(db, pid, day: str, data) -> int:
    summary = data.get("hrvSummary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return 0
    return int(store.set_daily(db, pid, "hrv_rmssd", day, "garmin", _num(summary.get("lastNightAvg"))))


def store_readiness(db, pid, day: str, data) -> int:
    return int(store.set_daily(db, pid, "readiness", day, "garmin", _num(_first(data).get("score"))))


def store_vo2max(db, pid, day: str, data) -> int:
    generic = _first(data).get("generic")
    if not isinstance(generic, dict):
        return 0
    value = _num(generic.get("vo2MaxPreciseValue")) or _num(generic.get("vo2MaxValue"))
    at = util.to_datetime(f"{day} 12:00:00")
    return int(store.add_measurement(db, pid, "vo2max", value, at, "garmin", "") if value else 0)


def store_activities(db, pid, activities) -> int:
    count = 0
    for item in activities if isinstance(activities, list) else []:
        if not isinstance(item, dict) or item.get("activityId") is None:
            continue
        try:
            start = util.to_datetime(str(item.get("startTimeLocal", ""))[:19])
        except ValueError:
            continue
        if start is None:
            continue
        kind_key = (item.get("activityType") or {}).get("typeKey", "")
        duration = _num(item.get("duration"))
        distance = _num(item.get("distance"))
        count += store.upsert_workout(db, pid, "garmin", str(item["activityId"]), {
            "kind": GARMIN_WORKOUTS.get(kind_key, "sonstiges"), "started_at": start,
            "ended_at": start + timedelta(seconds=duration) if duration else None,
            "duration_min": duration / 60 if duration else None,
            "distance_km": distance / 1000 if distance else None,
            "energy_kcal": _num(item.get("calories")), "hr_avg": _num(item.get("averageHR")),
            "hr_max": _num(item.get("maxHR")),
        })
    return count


def store_body(db, pid, data) -> int:
    rows = []
    items = data.get("dateWeightList") if isinstance(data, dict) else None
    for item in items if isinstance(items, list) else []:
        stamp = _num(item.get("date")) if isinstance(item, dict) else None
        if not stamp:
            continue
        at = util.from_unix(stamp / 1000)
        group = f"g{item.get('samplePk', stamp)}"
        for metric, key, factor in (("weight", "weight", 0.001), ("fat_ratio", "bodyFat", 1),
                                    ("muscle_mass", "muscleMass", 0.001),
                                    ("bone_mass", "boneMass", 0.001)):
            value = _num(item.get(key))
            if value is not None:
                rows.append((metric, value * factor, at, "garmin", group))
    return store.add_measurements(db, pid, rows)


# ---------- Sync ----------

def sync(db, pid: int, api, start: date, end: date, commit=lambda: None, pause: float = PAUSE) -> dict:
    """Fetch all days from start to end. Single endpoints may fail without stopping the rest."""
    counts = {"tage": 0, "werte": 0, "fehler": 0}

    def attempt(fetch):
        try:
            counts["werte"] += fetch()
        except Exception as exc:
            if "Authentication" in type(exc).__name__:
                raise AuthExpired("Die Garmin-Anmeldung ist abgelaufen. Bitte neu "
                                  "anmelden.") from None
            counts["fehler"] += 1
            log.info("Garmin: Teil übersprungen (%s)", type(exc).__name__)

    for current in util.days(start, end):
        day = current.isoformat()
        attempt(lambda: store_summary(db, pid, day, api.get_user_summary(day)))
        attempt(lambda: store_sleep(db, pid, api.get_sleep_data(day)))
        attempt(lambda: store_hrv(db, pid, day, api.get_hrv_data(day)))
        attempt(lambda: store_readiness(db, pid, day, api.get_training_readiness(day)))
        attempt(lambda: store_vo2max(db, pid, day, api.get_max_metrics(day)))
        counts["tage"] += 1
        commit()
        if pause and current < end:
            time.sleep(pause)
    attempt(lambda: store_activities(db, pid, api.get_activities_by_date(start.isoformat(),
                                                                    end.isoformat())))
    attempt(lambda: store_body(db, pid, api.get_body_composition(start.isoformat(), end.isoformat())))
    commit()
    if counts["tage"] and counts["fehler"] >= counts["tage"] * 5:
        raise GarminError("Garmin hat keine verwertbaren Daten geliefert. Vielleicht hat Garmin "
                          "etwas geändert; die Bibliothek braucht dann ein Update.")
    return counts
