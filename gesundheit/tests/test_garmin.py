"""Garmin direct: switch, login with and without MFA, tokens only, mapping of a day."""

import json
from datetime import date

import pytest

from gesundheit import garmin, jobs, settings, store

TOKENS = json.dumps({"di_token": "t" * 600, "di_refresh_token": "r" * 40, "di_client_id": "c"})


class AuthError(Exception):
    pass


AuthError.__name__ = "GarminConnectAuthenticationError"


class FakeClient:
    def __init__(self, owner):
        self.owner = owner

    def dumps(self):
        return TOKENS

    def loads(self, tokens):
        self.owner.loaded = tokens


class FakeGarmin:
    instances = []
    mfa = False
    fail_login = False
    expired = False

    def __init__(self, email=None, password=None, return_on_mfa=False, **_):
        self.email, self.password = email, password
        self.client = FakeClient(self)
        self.loaded = None
        FakeGarmin.instances.append(self)

    def login(self, tokenstore=None):
        if tokenstore:
            if FakeGarmin.expired:
                raise AuthError("expired")
            self.loaded = tokenstore
            return None, None
        if FakeGarmin.fail_login:
            raise AuthError("bad")
        return ("needs_mfa", None) if FakeGarmin.mfa else (None, None)

    def resume_login(self, _state, code):
        if code != "123456":
            raise AuthError("wrong code")

    # data
    def get_user_summary(self, day):
        if day == "2026-09-02":
            return {"totalSteps": 0, "restingHeartRate": 55}
        return {"totalSteps": 11234, "totalDistanceMeters": 8400, "activeKilocalories": 610,
                "floorsAscended": 9.2, "moderateIntensityMinutes": 20,
                "vigorousIntensityMinutes": 15, "restingHeartRate": 52, "minHeartRate": 47,
                "maxHeartRate": 158, "averageStressLevel": 28, "bodyBatteryHighestValue": 91,
                "bodyBatteryLowestValue": 18, "averageSpo2": 96, "avgWakingRespirationValue": 14.5}

    def get_sleep_data(self, day):
        if day != "2026-09-01":
            return {}
        return {"dailySleepDTO": {
            "calendarDate": "2026-09-01", "sleepTimeSeconds": 26400, "deepSleepSeconds": 5400,
            "lightSleepSeconds": 15000, "remSleepSeconds": 6000, "awakeSleepSeconds": 1200,
            "sleepStartTimestampLocal": 1788217200000, "sleepEndTimestampLocal": 1788244800000,
            "sleepScores": {"overall": {"value": 84}}, "averageRespirationValue": 13.8}}

    def get_hrv_data(self, day):
        return {"hrvSummary": {"lastNightAvg": 49}}

    def get_training_readiness(self, day):
        return [{"score": 71}]

    def get_max_metrics(self, day):
        return [{"generic": {"vo2MaxPreciseValue": 48.3}}]

    def get_activities_by_date(self, start, end):
        return [{"activityId": 99, "activityType": {"typeKey": "trail_running"},
                 "startTimeLocal": "2026-09-01 17:30:00", "duration": 3000, "distance": 9100,
                 "calories": 620, "averageHR": 149, "maxHR": 177},
                {"activityName": "ohne ID"}]

    def get_body_composition(self, start, end):
        return {"dateWeightList": [{"date": 1788242400000, "weight": 80100, "bodyFat": 21.2,
                                    "samplePk": 7}]}


@pytest.fixture(autouse=True)
def fake_garmin(monkeypatch):
    FakeGarmin.instances = []
    FakeGarmin.mfa = FakeGarmin.fail_login = FakeGarmin.expired = False
    monkeypatch.setattr(garmin, "FACTORY", FakeGarmin)
    monkeypatch.setattr(garmin, "available", lambda: True)
    monkeypatch.setattr(garmin, "PAUSE", 0)
    yield FakeGarmin


def enable(logged_in, days="2"):
    logged_in.get("/quellen")
    logged_in.post("/quellen/garmin/schalter", {"aktiv": "on", "tage": days})


def test_off_by_default_and_login_refused(logged_in, db):
    assert settings.get(db, "garmin_enabled") == 0
    page = logged_in.get("/quellen").get_data(as_text=True)
    assert "Inoffiziell" in page and "Bei Garmin anmelden" not in page
    response = logged_in.post("/quellen/garmin/anmelden", {"email": "a@b.de", "password": "x"})
    assert response.status_code == 400


def test_login_stores_only_tokens(app, logged_in, db, monkeypatch):
    synced = []
    monkeypatch.setattr(jobs, "run_garmin", lambda app, days=None: synced.append(days))
    enable(logged_in)
    assert "Bei Garmin anmelden" in logged_in.get("/quellen").get_data(as_text=True)
    logged_in.post("/quellen/garmin/anmelden", {"email": "anna@example.org",
                                                "password": "geheimes-garmin-pw"})
    secret = jobs.load_secret(app, db, "garmin")
    assert secret == {"tokens": TOKENS}
    raw = db.execute("SELECT secret_enc FROM connections WHERE provider = 'garmin'").fetchone()[0]
    assert "geheimes-garmin-pw" not in raw and "di_token" not in raw
    dump = "\n".join(str(tuple(r)) for t in ("settings", "meta", "connections")
                     for r in db.execute(f"SELECT * FROM {t}"))
    assert "geheimes-garmin-pw" not in dump and "anna@example.org" not in dump
    assert synced == [2]


def test_mfa_flow(app, logged_in, db, monkeypatch, fake_garmin):
    monkeypatch.setattr(jobs, "run_garmin", lambda app, days=None: None)
    fake_garmin.mfa = True
    enable(logged_in)
    logged_in.post("/quellen/garmin/anmelden", {"email": "a@b.de", "password": "pw"})
    page = logged_in.get("/quellen").get_data(as_text=True)
    assert "Code von Garmin" in page
    logged_in.post("/quellen/garmin/code", {"code": "000000"})
    assert not jobs.load_secret(app, db, "garmin")
    # a wrong code ends the pending login; start again
    logged_in.post("/quellen/garmin/anmelden", {"email": "a@b.de", "password": "pw"})
    logged_in.get("/quellen")
    logged_in.post("/quellen/garmin/code", {"code": "123456"})
    assert jobs.load_secret(app, db, "garmin") == {"tokens": TOKENS}


def test_pending_mfa_expires(monkeypatch, fake_garmin):
    fake_garmin.mfa = True
    status, pending = garmin.start_login("a@b.de", "pw")
    assert status == "mfa"
    clock = [garmin.time.monotonic() + garmin.MFA_TTL + 1]
    monkeypatch.setattr(garmin.time, "monotonic", lambda: clock[0])
    with pytest.raises(garmin.GarminError, match="abgelaufen"):
        garmin.finish_login(pending, "123456")


def test_wrong_password_message(logged_in, fake_garmin):
    fake_garmin.fail_login = True
    enable(logged_in)
    logged_in.post("/quellen/garmin/anmelden", {"email": "a@b.de", "password": "falsch"})
    assert "abgelehnt" in logged_in.get("/quellen").get_data(as_text=True)


def test_sync_maps_a_day(db):
    api = garmin.connect(TOKENS)
    counts = garmin.sync(db, api, date(2026, 9, 1), date(2026, 9, 2), pause=0)
    assert counts["tage"] == 2 and counts["fehler"] == 0
    day = "2026-09-01"

    def value(metric, d=day):
        series = store.daily_series(db, metric, d, d)
        return series[0]["value"] if series else None

    assert value("steps") == 11234 and value("distance_km") == pytest.approx(8.4)
    assert value("active_min") == 35 and value("resting_hr") == 52
    assert value("body_battery_max") == 91 and value("stress_avg") == 28
    assert value("hrv_rmssd") == 49 and value("readiness") == 71 and value("spo2") == 96
    assert value("steps", "2026-09-02") is None          # watch not worn: zeros are dropped
    assert value("resting_hr", "2026-09-02") == 55
    night = store.sleep_series(db, day, day)[0]
    assert night["source"] == "garmin" and night["asleep_min"] == 440 and night["score"] == 84
    assert night["bed_start"] == "2026-08-31 23:00:00"
    workout = store.workouts(db, day, day)[0]
    assert workout["kind"] == "laufen" and workout["duration_min"] == 50
    assert store.latest(db, "vo2max")["value"] == pytest.approx(48.3)
    assert store.per_source(db, "weight", day, day)[day]["garmin"] == pytest.approx(80.1)


def test_job_refreshes_tokens_and_marks_status(app, db):
    settings.put(db, "garmin_enabled", 1)
    jobs.save_secret(app, db, "garmin", {"tokens": TOKENS})
    db.commit()
    jobs.run_garmin(app, days=1)
    row = db.execute("SELECT last_ok, last_error FROM connections").fetchone()
    assert row["last_ok"] and row["last_error"] == ""


def test_expired_login_is_reported(app, db, fake_garmin):
    fake_garmin.expired = True
    settings.put(db, "garmin_enabled", 1)
    jobs.save_secret(app, db, "garmin", {"tokens": TOKENS})
    db.commit()
    jobs.run_garmin(app, days=1)
    assert "abgelehnt" in db.execute("SELECT last_error FROM connections").fetchone()[0]


def test_job_does_nothing_when_switched_off(app, db):
    jobs.save_secret(app, db, "garmin", {"tokens": TOKENS})
    db.commit()
    jobs.run_garmin(app, days=1)
    assert db.execute("SELECT last_sync FROM connections").fetchone()[0] is None


def test_switching_off_deletes_login(app, logged_in, db, monkeypatch):
    monkeypatch.setattr(jobs, "run_garmin", lambda app, days=None: None)
    enable(logged_in)
    logged_in.post("/quellen/garmin/anmelden", {"email": "a@b.de", "password": "pw"})
    logged_in.get("/quellen")
    logged_in.post("/quellen/garmin/schalter", {"tage": "30"})
    assert jobs.load_secret(app, db, "garmin") == {}
    assert settings.get(db, "garmin_enabled") == 0


def test_garbage_from_garmin_does_not_crash(db):
    class Weird(FakeGarmin):
        def get_user_summary(self, day):
            return ["unerwartet"]

        def get_sleep_data(self, day):
            return {"dailySleepDTO": {"sleepTimeSeconds": "viel"}}

        def get_hrv_data(self, day):
            raise ValueError("kaputt")

        def get_activities_by_date(self, start, end):
            return {"keine": "liste"}

    counts = garmin.sync(db, Weird(), date(2026, 9, 1), date(2026, 9, 1), pause=0)
    assert counts["fehler"] == 1
    assert db.execute("SELECT COUNT(*) FROM sleep").fetchone()[0] == 0
