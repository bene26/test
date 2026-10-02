"""Withings: official public API with OAuth 2.0 (read-only scopes).

Setup once: create a free application at developer.withings.com, enter its client ID and
secret here (or as WITHINGS_CLIENT_ID / WITHINGS_CLIENT_SECRET), and register the callback
address shown on the Quellen page. Tokens are stored encrypted (crypto.py) and refreshed
automatically; Withings hands out a new refresh token with every refresh.
"""

import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from . import store, util
from .katalog import WITHINGS_WORKOUTS

AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
API = "https://wbsapi.withings.net"
SCOPE = "user.info,user.metrics,user.activity,user.sleepevents"
TIMEOUT = 30
MAX_PAGES = 200
log = logging.getLogger("gesundheit")

# Withings measure type -> (metric, factor applied after value * 10^unit)
MEASURE_TYPES = {
    1: ("weight", 1), 4: ("height", 100), 5: ("fat_free_mass", 1), 6: ("fat_ratio", 1),
    8: ("fat_mass", 1), 9: ("bp_dia", 1), 10: ("bp_sys", 1), 11: ("pulse", 1),
    12: ("temperature", 1), 54: ("spo2", 1), 71: ("temperature", 1), 76: ("muscle_mass", 1),
    77: ("hydration", 1), 88: ("bone_mass", 1), 91: ("pwv", 1), 123: ("vo2max", 1),
    170: ("visceral_fat", 1), 226: ("bmr", 1),
}
ACTIVITY_FIELDS = "steps,distance,elevation,soft,moderate,intense,active,calories,hr_min,hr_max"
SLEEP_FIELDS = ("deepsleepduration,lightsleepduration,remsleepduration,wakeupduration,"
                "hr_average,rr_average,sleep_score,total_sleep_time")
WORKOUT_FIELDS = "calories,distance,hr_average,hr_max,manual_distance,manual_calories"


class WithingsError(Exception):
    """Message is safe to show to the user (never contains tokens)."""


class AuthExpired(WithingsError):
    pass


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "scope": SCOPE,
        "redirect_uri": redirect_uri, "state": state,
    })


def _token_request(http, data: dict) -> dict:
    try:
        response = http.post(f"{API}/v2/oauth2", data=data, timeout=TIMEOUT)
        payload = response.json()
    except Exception as exc:  # network, TLS, invalid JSON
        raise WithingsError(f"Withings nicht erreichbar ({type(exc).__name__}).") from None
    if payload.get("status") != 0 or "body" not in payload:
        if payload.get("status") in (100, 101, 102, 200, 401, 503):
            raise AuthExpired("Withings hat die Anmeldung abgelehnt. Bitte neu verbinden.")
        raise WithingsError(f"Withings meldet Fehler {payload.get('status')}.")
    body = payload["body"]
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_at": int(time.time()) + int(body.get("expires_in", 10800)),
        "userid": str(body.get("userid", "")),
        "scope": body.get("scope", ""),
    }


def exchange_code(http, client_id, client_secret, code, redirect_uri) -> dict:
    return _token_request(http, {
        "action": "requesttoken", "grant_type": "authorization_code", "client_id": client_id,
        "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri,
    })


def refresh_tokens(http, client_id, client_secret, refresh_token) -> dict:
    return _token_request(http, {
        "action": "requesttoken", "grant_type": "refresh_token", "client_id": client_id,
        "client_secret": client_secret, "refresh_token": refresh_token,
    })


class Client:
    """Calls the API and refreshes the access token when needed.

    on_tokens(tokens) is called after every refresh so the new tokens get stored at once
    (the old refresh token stops working).
    """

    def __init__(self, http, tokens: dict, client_id: str, client_secret: str, on_tokens):
        self.http = http
        self.tokens = tokens
        self.client_id = client_id
        self.client_secret = client_secret
        self.on_tokens = on_tokens

    def _refresh(self):
        self.tokens = refresh_tokens(self.http, self.client_id, self.client_secret,
                                     self.tokens["refresh_token"])
        self.on_tokens(self.tokens)

    def call(self, path: str, params: dict) -> dict:
        if self.tokens.get("expires_at", 0) < time.time() + 120:
            self._refresh()
        for attempt in (1, 2):
            try:
                response = self.http.post(
                    f"{API}/{path}", data=params, timeout=TIMEOUT,
                    headers={"Authorization": f"Bearer {self.tokens['access_token']}"})
                payload = response.json()
            except Exception as exc:
                raise WithingsError(f"Withings nicht erreichbar ({type(exc).__name__}).") from None
            status = payload.get("status")
            if status == 0:
                return payload.get("body") or {}
            if status == 401 and attempt == 1:
                self._refresh()
                continue
            if status == 601:
                raise WithingsError("Withings bremst gerade (zu viele Anfragen). "
                                    "Der nächste Abgleich versucht es wieder.")
            if status in (100, 101, 102, 200, 401):
                raise AuthExpired("Die Withings-Anmeldung ist abgelaufen. Bitte neu verbinden.")
            raise WithingsError(f"Withings meldet Fehler {status}.")
        raise AuthExpired("Die Withings-Anmeldung ist abgelaufen. Bitte neu verbinden.")

    def pages(self, path: str, params: dict, key: str):
        """All items of a paged list (more/offset)."""
        offset = None
        for _ in range(MAX_PAGES):
            query = dict(params)
            if offset:
                query["offset"] = offset
            body = self.call(path, query)
            yield from body.get(key) or []
            if not body.get("more"):
                return
            offset = body.get("offset")
            if not offset:
                return


# ---------- Mapping ----------

def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def store_measure_groups(db, pid, groups) -> int:
    rows = []
    for group in groups:
        if group.get("category", 1) != 1 or not _num(group.get("date")):
            continue  # 2 = objectives (targets), not real measurements
        measured_at = util.from_unix(group["date"])
        group_id = f"w{group.get('grpid', '')}"
        for measure in group.get("measures") or []:
            mapping = MEASURE_TYPES.get(measure.get("type"))
            value, unit = _num(measure.get("value")), _num(measure.get("unit"))
            if not mapping or value is None or unit is None:
                continue
            metric, factor = mapping
            rows.append((metric, value * (10 ** unit) * factor, measured_at, "withings",
                         group_id))
    return store.add_measurements(db, pid, rows)


def _seconds_to_min(*values):
    numbers = [_num(v) for v in values]
    if all(n is None for n in numbers):
        return None
    return sum(n or 0 for n in numbers) / 60


def store_activities(db, pid, activities) -> int:
    rows = []
    for item in activities:
        day = item.get("date")
        if not isinstance(day, str) or len(day) != 10:
            continue
        distance = _num(item.get("distance"))
        rows += [
            ("steps", day, "withings", _num(item.get("steps"))),
            ("distance_km", day, "withings", distance / 1000 if distance is not None else None),
            ("floors", day, "withings", _num(item.get("elevation"))),
            ("active_min", day, "withings",
             _seconds_to_min(item.get("moderate"), item.get("intense"))),
            ("active_kcal", day, "withings", _num(item.get("calories"))),
            ("hr_min", day, "withings", _num(item.get("hr_min"))),
            ("hr_max", day, "withings", _num(item.get("hr_max"))),
        ]
    return store.set_daily_many(db, pid, [r for r in rows if r[3] is not None])


def store_sleep(db, pid, series) -> int:
    count = 0
    for item in series:
        if not _num(item.get("startdate")) or not _num(item.get("enddate")):
            continue
        data = item.get("data") or {}
        start, end = util.from_unix(item["startdate"]), util.from_unix(item["enddate"])
        deep = _seconds_to_min(data.get("deepsleepduration"))
        light = _seconds_to_min(data.get("lightsleepduration"))
        rem = _seconds_to_min(data.get("remsleepduration"))
        asleep = _seconds_to_min(data.get("total_sleep_time"))
        if asleep is None and any(v is not None for v in (deep, light, rem)):
            asleep = (deep or 0) + (light or 0) + (rem or 0)
        count += store.upsert_sleep(db, pid, end.date(), "withings", {
            "bed_start": start, "bed_end": end, "asleep_min": asleep, "deep_min": deep,
            "light_min": light, "rem_min": rem,
            "awake_min": _seconds_to_min(data.get("wakeupduration")),
            "score": _num(data.get("sleep_score")), "hr_avg": _num(data.get("hr_average")),
            "rr_avg": _num(data.get("rr_average")),
        })
    return count


def store_workouts(db, pid, series) -> int:
    count = 0
    for item in series:
        if not _num(item.get("startdate")) or item.get("id") is None:
            continue
        data = item.get("data") or {}
        start = util.from_unix(item["startdate"])
        end = util.from_unix(item["enddate"]) if _num(item.get("enddate")) else None
        distance = _num(data.get("distance")) or _num(data.get("manual_distance"))
        count += store.upsert_workout(db, pid, "withings", str(item["id"]), {
            "kind": WITHINGS_WORKOUTS.get(item.get("category"), "sonstiges"),
            "started_at": start, "ended_at": end,
            "duration_min": (end - start).total_seconds() / 60 if end else None,
            "distance_km": distance / 1000 if distance else None,
            "energy_kcal": _num(data.get("calories")) or _num(data.get("manual_calories")),
            "hr_avg": _num(data.get("hr_average")), "hr_max": _num(data.get("hr_max")),
        })
    return count


def store_heart(db, pid, series) -> int:
    rows = []
    for item in series:
        ecg = item.get("ecg") or {}
        if not _num(item.get("timestamp")) or _num(ecg.get("afib")) is None:
            continue
        at = util.from_unix(item["timestamp"])
        group_id = f"ecg{ecg.get('signalid', item['timestamp'])}"
        rows.append(("ekg_afib", ecg["afib"], at, "withings", group_id))
        if _num(item.get("heart_rate")):
            rows.append(("ekg_puls", item["heart_rate"], at, "withings", group_id))
    return store.add_measurements(db, pid, rows)


# ---------- Sync ----------

def sync(db, pid: int, client: Client, cursor: dict, backfill_days: int, now: datetime | None = None,
         commit=lambda: None) -> tuple[dict, dict, str]:
    """Fetch everything changed since the last run. Returns (new cursor, counts, error).

    Each part keeps its own position, so a failing part does not block the others; error is
    the first problem as text ("" if all went well). AuthExpired is raised: reconnect needed.
    """
    now = now or util.now()
    start_ts = util.to_unix(now) - 300  # small overlap against clock differences
    initial = util.to_unix(now - timedelta(days=max(1, backfill_days)))
    cursor = dict(cursor or {})
    counts = {}
    first_error = None

    def run(part, fetch):
        nonlocal first_error
        try:
            counts[part] = fetch(cursor.get(part))
            cursor[part] = start_ts
            commit()
        except AuthExpired:
            raise
        except WithingsError as exc:
            log.warning("Withings %s: %s", part, exc)
            first_error = first_error or exc

    # Body measurements: complete history on the first run (few values per day).
    run("messwerte", lambda since: store_measure_groups(db, pid, client.pages(
        "measure", {"action": "getmeas", "category": 1, "lastupdate": since or 0},
        "measuregrps")))
    run("aktivitaet", lambda since: store_activities(db, pid, client.pages(
        "v2/measure", {"action": "getactivity", "lastupdate": since or initial,
                       "data_fields": ACTIVITY_FIELDS}, "activities")))
    run("schlaf", lambda since: store_sleep(db, pid, client.pages(
        "v2/sleep", {"action": "getsummary", "lastupdate": since or initial,
                     "data_fields": SLEEP_FIELDS}, "series")))
    run("training", lambda since: store_workouts(db, pid, client.pages(
        "v2/measure", {"action": "getworkouts", "lastupdate": since or initial,
                       "data_fields": WORKOUT_FIELDS}, "series")))
    run("ekg", lambda since: store_heart(db, pid, client.pages(
        "v2/heart", {"action": "list", "startdate": since or initial,
                     "enddate": start_ts + 300}, "series")))
    return cursor, counts, str(first_error) if first_error else ""
