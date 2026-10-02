"""Withings: OAuth flow, encrypted tokens, refresh, mapping of all data kinds."""

import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from gesundheit import jobs, store, withings
from gesundheit.withings import Client

T0 = 1788242400  # 2026-09-01 08:00 Berlin


class Resp:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


class FakeWithings:
    """Answers like the Withings API; records every call."""

    def __init__(self):
        self.calls = []
        self.token_no = 0
        self.reject_token = None
        self.bodies = {}

    def tokens(self):
        self.token_no += 1
        return {"status": 0, "body": {"access_token": f"acc-{self.token_no}",
                                      "refresh_token": f"ref-{self.token_no}", "expires_in": 10800,
                                      "userid": "123456", "scope": withings.SCOPE}}

    def post(self, url, data=None, headers=None, timeout=None):
        data = dict(data or {})
        self.calls.append((url, data, dict(headers or {})))
        if url.endswith("/v2/oauth2"):
            if data.get("code") == "kaputt":
                return Resp({"status": 503})
            return Resp(self.tokens())
        auth = (headers or {}).get("Authorization", "")
        if self.reject_token and auth == f"Bearer {self.reject_token}":
            return Resp({"status": 401})
        path = url.split("wbsapi.withings.net/", 1)[1]
        body = self.bodies.get((path, data.get("action")), {})
        if callable(body):
            body = body(data)
        return Resp({"status": 0, "body": body})


@pytest.fixture
def fake(app):
    fake = FakeWithings()
    app.extensions["withings_http"] = fake
    return fake


def connect(app, logged_in, fake):
    logged_in.get("/quellen")
    logged_in.post("/quellen/withings/zugang", {"client_id": "abc123client",
                                                "client_secret": "s3cr3t-value"})
    response = logged_in.post("/quellen/withings/verbinden")
    assert response.status_code == 302
    location = urlsplit(response.headers["Location"])
    query = parse_qs(location.query)
    assert location.netloc == "account.withings.com"
    assert query["scope"] == [withings.SCOPE] and query["client_id"] == ["abc123client"]
    assert query["redirect_uri"] == ["http://nas.local:8090/quellen/withings/zurueck"]
    return query["state"][0]


def test_authorize_url_is_read_only():
    url = withings.authorize_url("id", "https://x/cb", "st")
    assert "user.metrics" in url and "user.activity" in url and "write" not in url


def test_connect_stores_tokens_encrypted(app, logged_in, fake, db, me):
    state = connect(app, logged_in, fake)
    response = logged_in.get(f"/quellen/withings/zurueck?code=abc&state={state}")
    assert response.status_code == 302
    row = db.execute("SELECT * FROM connections WHERE provider = 'withings'").fetchone()
    assert row["person_id"] == me
    raw = row["secret_enc"] + db.execute("SELECT value FROM meta WHERE key = 'withings_app'").fetchone()[0]
    for secret in ("acc-1", "ref-1", "s3cr3t-value", "abc123client"):
        assert secret not in raw
    secret = jobs.load_secret(app, db, "withings", me)
    assert secret["tokens"]["refresh_token"] in ("ref-1", "ref-2")
    assert jobs.withings_app(app, db) == ("abc123client", "s3cr3t-value")
    page = logged_in.get("/quellen").get_data(as_text=True)
    assert "verbunden" in page and "s3cr3t-value" not in page and "acc-1" not in page
    token_call = next(c for c in fake.calls if c[0].endswith("/v2/oauth2"))
    assert token_call[1]["action"] == "requesttoken" and token_call[1]["code"] == "abc"


def test_callback_with_wrong_state_is_refused(app, logged_in, fake, db, me):
    connect(app, logged_in, fake)
    logged_in.get("/quellen/withings/zurueck?code=abc&state=falsch")
    assert not jobs.load_secret(app, db, "withings", me).get("tokens")
    assert not any(c[0].endswith("/v2/oauth2") for c in fake.calls)


def test_callback_without_started_login_is_refused(app, logged_in, fake, db, me):
    logged_in.get("/quellen/withings/zurueck?code=abc&state=irgendwas")
    assert not jobs.load_secret(app, db, "withings", me).get("tokens")


def test_failed_token_exchange_shows_message(app, logged_in, fake, db, me):
    state = connect(app, logged_in, fake)
    logged_in.get(f"/quellen/withings/zurueck?code=kaputt&state={state}")
    page = logged_in.get("/quellen").get_data(as_text=True)
    assert "abgelehnt" in page
    assert not jobs.load_secret(app, db, "withings", me).get("tokens")


def test_invalid_characters_in_credentials(logged_in, app, db):
    logged_in.get("/quellen")
    logged_in.post("/quellen/withings/zugang", {"client_id": "abc<script>", "client_secret": "x"})
    assert jobs.withings_app(app, db) == ("", "")


def measure_body(data):
    return {"measuregrps": [
        {"grpid": 1, "date": T0, "category": 1, "measures": [
            {"type": 1, "value": 80250, "unit": -3}, {"type": 6, "value": 2150, "unit": -2},
            {"type": 4, "value": 181, "unit": -2}, {"type": 76, "value": 598, "unit": -1},
            {"type": 999, "value": 1, "unit": 0}]},
        {"grpid": 2, "date": T0 + 3600, "category": 1, "measures": [
            {"type": 10, "value": 128, "unit": 0}, {"type": 9, "value": 81, "unit": 0},
            {"type": 11, "value": 62, "unit": 0}]},
        {"grpid": 3, "date": T0, "category": 2, "measures": [{"type": 1, "value": 75, "unit": 0}]},
        {"grpid": 4, "date": T0 + 7200, "category": 1, "measures": [
            {"type": 71, "value": 3680, "unit": -2}, {"type": 170, "value": 9, "unit": 0}]},
    ], "more": 0}


def full_sync_bodies(fake):
    fake.bodies = {
        ("measure", "getmeas"): measure_body,
        ("v2/measure", "getactivity"): {"activities": [
            {"date": "2026-09-01", "steps": 10432, "distance": 7800.5, "elevation": 12,
             "moderate": 1200, "intense": 600, "calories": 512, "hr_min": 48, "hr_max": 151}]},
        ("v2/sleep", "getsummary"): {"series": [
            {"startdate": T0 - 9 * 3600, "enddate": T0 - 90 * 60, "data": {
                "deepsleepduration": 4200, "lightsleepduration": 15000,
                "remsleepduration": 5400, "wakeupduration": 1200, "sleep_score": 81,
                "hr_average": 57, "rr_average": 14}}]},
        ("v2/measure", "getworkouts"): {"series": [
            {"id": 77, "category": 2, "startdate": T0 + 36000, "enddate": T0 + 38400,
             "data": {"calories": 480, "distance": 7600, "hr_average": 151, "hr_max": 174}}]},
        ("v2/heart", "list"): {"series": [
            {"timestamp": T0 + 4000, "heart_rate": 64, "ecg": {"signalid": 5, "afib": 0}},
            {"timestamp": T0 + 5000, "heart_rate": 70, "bloodpressure": {"systole": 120}}]},
    }


def make_client(fake, stored):
    tokens = {"access_token": "acc-0", "refresh_token": "ref-0",
              "expires_at": int(time.time()) + 3600}
    return Client(fake, tokens, "id", "secret", stored.append)


def test_sync_maps_every_kind(db, pid, fake):
    full_sync_bodies(fake)
    cursor, counts, error = withings.sync(db, pid, make_client(fake, []), {}, 30)
    assert error == ""
    assert set(cursor) == {"messwerte", "aktivitaet", "schlaf", "training", "ekg"}
    weight = store.latest(db, pid, "weight")
    assert weight["value"] == pytest.approx(80.25) and weight["source"] == "withings"
    assert store.latest(db, pid, "height")["value"] == pytest.approx(181)
    assert store.latest(db, pid, "fat_ratio")["value"] == pytest.approx(21.5)
    assert store.latest(db, pid, "muscle_mass")["value"] == pytest.approx(59.8)
    assert store.latest(db, pid, "temperature")["value"] == pytest.approx(36.8)
    assert store.latest(db, pid, "visceral_fat")["value"] == 9
    # objectives (category 2) are not measurements
    assert db.execute("SELECT COUNT(*) FROM measurements WHERE metric = 'weight'").fetchone()[0] == 1
    bp = store.readings(db, pid, ("bp_sys", "bp_dia", "pulse"), "2026-09-01", "2026-09-01")
    assert bp[0]["values"] == {"bp_sys": 128, "bp_dia": 81, "pulse": 62}
    assert store.daily_series(db, pid, "steps", "2026-09-01", "2026-09-01")[0]["value"] == 10432
    assert store.daily_series(db, pid, "active_min", "2026-09-01", "2026-09-01")[0]["value"] == 30
    assert store.daily_series(db, pid, "distance_km", "2026-09-01", "2026-09-01")[0]["value"] == pytest.approx(7.8005)
    night = store.sleep_series(db, pid, "2026-09-01", "2026-09-01")[0]
    assert night["asleep_min"] == 410 and night["deep_min"] == 70 and night["score"] == 81
    workout = store.workouts(db, pid, "2026-09-01", "2026-09-01")[0]
    assert workout["kind"] == "laufen" and workout["duration_min"] == 40
    assert workout["distance_km"] == pytest.approx(7.6)
    ecg = store.readings(db, pid, ("ekg_afib", "ekg_puls"), "2026-09-01", "2026-09-01")
    assert len(ecg) == 1 and ecg[0]["values"] == {"ekg_afib": 0, "ekg_puls": 64}


def test_second_sync_only_asks_for_changes(db, pid, fake):
    full_sync_bodies(fake)
    cursor, _counts, _ = withings.sync(db, pid, make_client(fake, []), {}, 30)
    fake.calls.clear()
    withings.sync(db, pid, make_client(fake, []), cursor, 30)
    meas = next(c for c in fake.calls if c[1].get("action") == "getmeas")
    assert meas[1]["lastupdate"] == cursor["messwerte"]


def test_paging(db, pid, fake):
    pages = {"0": {"activities": [{"date": "2026-09-01", "steps": 1000}], "more": True,
                   "offset": 1},
             "1": {"activities": [{"date": "2026-09-02", "steps": 2000}], "more": False}}
    fake.bodies[("v2/measure", "getactivity")] = lambda data: pages[str(data.get("offset", 0))]
    withings.sync(db, pid, make_client(fake, []), {}, 30)
    assert len(store.daily_series(db, pid, "steps", "2026-09-01", "2026-09-02")) == 2


def test_expired_access_token_is_refreshed_and_kept(db, pid, fake):
    fake.reject_token = "acc-0"
    stored = []
    client = make_client(fake, stored)
    full_sync_bodies(fake)
    _cursor, _counts, error = withings.sync(db, pid, client, {}, 30)
    assert error == ""
    assert stored and stored[0]["refresh_token"] == "ref-1"
    refresh = next(c for c in fake.calls if c[0].endswith("/v2/oauth2"))
    assert refresh[1]["grant_type"] == "refresh_token" and refresh[1]["refresh_token"] == "ref-0"


def test_token_refreshed_before_expiry(fake):
    stored = []
    client = Client(fake, {"access_token": "a", "refresh_token": "r", "expires_at": 0},
                    "id", "secret", stored.append)
    client.call("measure", {"action": "getmeas"})
    assert stored[0]["access_token"] == "acc-1"


def test_rejected_login_marks_connection(app, db, pid, fake):
    jobs.save_withings_app(app, db, "a", "b")
    jobs.save_secret(app, db, "withings", pid, {"tokens": {
        "access_token": "x", "refresh_token": "y", "expires_at": 0}})
    db.commit()
    fake.post_orig = fake.post
    fake.post = lambda url, **kw: Resp({"status": 401})
    jobs.run_withings(app)
    row = db.execute("SELECT last_error, last_ok FROM connections").fetchone()
    assert "neu verbinden" in row["last_error"] and row["last_ok"] is None


def test_rate_limit_keeps_other_parts(db, pid, fake):
    full_sync_bodies(fake)
    original = fake.post

    def limited(url, data=None, headers=None, timeout=None):
        if (data or {}).get("action") == "getsummary":
            return Resp({"status": 601})
        return original(url, data=data, headers=headers, timeout=timeout)

    fake.post = limited
    cursor, _counts, error = withings.sync(db, pid, make_client(fake, []), {}, 30)
    assert "bremst" in error and "schlaf" not in cursor and "messwerte" in cursor


def test_run_job_stores_cursor_and_status(app, db, pid, fake):
    full_sync_bodies(fake)
    jobs.save_withings_app(app, db, "a", "b")
    jobs.save_secret(app, db, "withings", pid, {"tokens": {
        "access_token": "acc-0", "refresh_token": "ref-0", "expires_at": int(time.time()) + 999}})
    db.commit()
    jobs.run_withings(app)
    row = db.execute("SELECT * FROM connections").fetchone()
    assert row["last_error"] == "" and row["last_ok"]
    assert set(json.loads(row["cursor"])) >= {"messwerte", "schlaf"}


def test_disconnect_person_keeps_application(app, logged_in, fake, db, me):
    state = connect(app, logged_in, fake)
    logged_in.get(f"/quellen/withings/zurueck?code=abc&state={state}")
    logged_in.get("/quellen")
    logged_in.post("/quellen/withings/trennen", {})
    assert jobs.load_secret(app, db, "withings", me) == {}
    assert jobs.withings_app(app, db)[0] == "abc123client"
    logged_in.post("/quellen/withings/zugang/loeschen", {})
    assert jobs.withings_app(app, db) == ("", "")


def test_each_person_has_own_withings_account(app, logged_in, fake, db, me):
    from gesundheit import persons
    other = persons.create(db, "Ben")
    db.commit()
    state = connect(app, logged_in, fake)
    logged_in.get(f"/quellen/withings/zurueck?code=abc&state={state}")
    logged_in.post(f"/personen/{other}/zeigen", {"next": "/quellen"})
    state = connect(app, logged_in, fake)
    logged_in.get(f"/quellen/withings/zurueck?code=abc&state={state}")  # same Withings user id
    assert not jobs.load_secret(app, db, "withings", other).get("tokens")
    assert "schon mit" in logged_in.get("/quellen").get_data(as_text=True)


def test_sync_writes_to_the_right_person(app, db, pid, fake):
    from gesundheit import persons
    other = persons.create(db, "Ben")
    full_sync_bodies(fake)
    jobs.save_withings_app(app, db, "a", "b")
    jobs.save_secret(app, db, "withings", other, {"tokens": {
        "access_token": "acc-0", "refresh_token": "ref-0", "expires_at": int(time.time()) + 999}})
    db.commit()
    jobs.run_withings(app)
    assert store.latest(db, other, "weight") and not store.latest(db, pid, "weight")


def test_old_credentials_move_to_application(app, db, pid):
    jobs.save_secret(app, db, "withings", pid, {"client_id": "alt", "client_secret": "geheim",
                                                "tokens": {"access_token": "t"}})
    db.commit()
    jobs.migrate_secrets(app)
    assert jobs.withings_app(app, db) == ("alt", "geheim")
    assert jobs.load_secret(app, db, "withings", pid) == {"tokens": {"access_token": "t"}}
