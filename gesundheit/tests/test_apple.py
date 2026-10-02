"""Apple Health export: parsing, units, sources, sleep, workouts and hostile files."""

import io
import zipfile
from pathlib import Path

import pytest

from gesundheit import apple, store
from gesundheit.apple import AppleImportError

HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE HealthData [
<!-- HealthKit Export Version: 13 -->
<!ELEMENT HealthData (ExportDate,Me,(Record|Correlation|Workout|ActivitySummary)*)>
<!ATTLIST HealthData
  locale CDATA #REQUIRED
>
<!ELEMENT Record ((MetadataEntry|HeartRateVariabilityMetadataList)*)>
]>
<HealthData locale="de_DE">
 <ExportDate value="2026-09-03 08:00:00 +0200"/>
 <Me HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexNotSet"/>
"""
WATCH = 'sourceName="Apple Watch von Anna" device="&lt;&lt;HKDevice: 0x1&gt;, name:Apple Watch, manufacturer:Apple Inc., model:Watch, hardware:Watch6,1&gt;"'
PHONE = 'sourceName="iPhone von Anna" device="&lt;&lt;HKDevice: 0x2&gt;, name:iPhone, manufacturer:Apple Inc., model:iPhone&gt;"'
CONNECT = 'sourceName="Connect"'
MATE = 'sourceName="Health Mate"'


def record(kind, value, unit, start, end=None, source=WATCH):
    return (f' <Record type="HKQuantityTypeIdentifier{kind}" {source} unit="{unit}" '
            f'creationDate="{start}" startDate="{start}" endDate="{end or start}" value="{value}">'
            f'<MetadataEntry key="HKWasUserEntered" value="0"/></Record>\n')


def sleep(stage, start, end, source=WATCH):
    return (f' <Record type="HKCategoryTypeIdentifierSleepAnalysis" {source} '
            f'startDate="{start}" endDate="{end}" value="HKCategoryValueSleepAnalysis{stage}"/>\n')


BODY = "".join([
    record("StepCount", 4000, "count", "2026-09-01 09:00:00 +0200", "2026-09-01 10:00:00 +0200"),
    record("StepCount", 5000, "count", "2026-09-01 17:00:00 +0200", "2026-09-01 18:00:00 +0200"),
    record("StepCount", 6500, "count", "2026-09-01 12:00:00 +0200", source=PHONE),
    record("DistanceWalkingRunning", 3.1, "mi", "2026-09-01 09:00:00 +0200"),
    record("ActiveEnergyBurned", 1000, "kJ", "2026-09-01 09:00:00 +0200"),
    record("AppleExerciseTime", 31, "min", "2026-09-01 09:00:00 +0200"),
    record("HeartRate", 55, "count/min", "2026-09-01 03:00:00 +0200"),
    record("HeartRate", 140, "count/min", "2026-09-01 18:10:00 +0200"),
    record("RestingHeartRate", 54, "count/min", "2026-09-01 23:59:00 +0200"),
    record("HeartRateVariabilitySDNN", 48, "ms", "2026-09-01 04:00:00 +0200"),
    record("OxygenSaturation", 0.97, "%", "2026-09-01 04:00:00 +0200"),
    record("BodyMass", 176.4, "lb", "2026-09-01 07:05:00 +0200", source=MATE),
    record("BodyFatPercentage", 0.215, "%", "2026-09-01 07:05:00 +0200", source=MATE),
    record("Height", 1.81, "m", "2026-09-01 07:05:00 +0200", source=PHONE),
    record("BloodPressureSystolic", 127, "mmHg", "2026-09-01 07:30:00 +0200", source=MATE),
    record("BloodPressureDiastolic", 82, "mmHg", "2026-09-01 07:30:00 +0200", source=MATE),
    record("BodyTemperature", 98.6, "degF", "2026-09-01 08:00:00 +0200", source=PHONE),
    record("VO2Max", 46.8, "mL/min·kg", "2026-09-01 18:00:00 +0200"),
    record("StepCount", 8000, "count", "2026-09-02 10:00:00 +0200", source=CONNECT),
    record("BodyMass", 9999, "kg", "2026-09-02 07:00:00 +0200"),       # implausible
    record("StepCount", "abc", "count", "2026-09-02 10:00:00 +0200"),  # not a number
    record("DietaryEnergyConsumed", 500, "kcal", "2026-09-02 12:00:00 +0200"),  # ignored type
    sleep("InBed", "2026-08-31 22:40:00 +0200", "2026-09-01 06:50:00 +0200"),
    sleep("AsleepCore", "2026-08-31 23:00:00 +0200", "2026-09-01 01:00:00 +0200"),
    sleep("AsleepDeep", "2026-09-01 01:00:00 +0200", "2026-09-01 02:00:00 +0200"),
    sleep("Awake", "2026-09-01 02:00:00 +0200", "2026-09-01 02:15:00 +0200"),
    sleep("AsleepREM", "2026-09-01 02:15:00 +0200", "2026-09-01 03:45:00 +0200"),
    sleep("AsleepCore", "2026-09-01 03:45:00 +0200", "2026-09-01 06:30:00 +0200"),
    sleep("AsleepCore", "2026-09-01 14:00:00 +0200", "2026-09-01 14:20:00 +0200"),  # nap
    sleep("InBed", "2026-08-31 23:00:00 +0200", "2026-09-01 06:40:00 +0200", source=PHONE),
    ' <Correlation type="HKCorrelationTypeIdentifierBloodPressure" sourceName="Health Mate" '
    'startDate="2026-09-01 07:30:00 +0200" endDate="2026-09-01 07:30:00 +0200">\n  '
    + record("BloodPressureSystolic", 127, "mmHg", "2026-09-01 07:30:00 +0200", source=MATE)
    + ' </Correlation>\n',
    f' <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="42.5" durationUnit="min" '
    f'{WATCH} startDate="2026-09-01 18:00:00 +0200" endDate="2026-09-01 18:42:30 +0200">\n'
    '  <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="455" unit="kcal"/>\n'
    '  <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning" sum="7.4" unit="km"/>\n'
    '  <WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="151" minimum="98" maximum="176" unit="count/min"/>\n'
    '  <WorkoutRoute sourceName="Apple Watch"><FileReference path="/workout-routes/route.gpx"/></WorkoutRoute>\n'
    ' </Workout>\n',
    ' <Workout workoutActivityType="HKWorkoutActivityTypeTraditionalStrengthTraining" duration="0.75" '
    'durationUnit="hr" totalEnergyBurned="900" totalEnergyBurnedUnit="kJ" sourceName="Connect" '
    'startDate="2026-09-02 18:00:00 +0200" endDate="2026-09-02 18:45:00 +0200"/>\n',
    ' <ActivitySummary dateComponents="2026-09-01" activeEnergyBurned="512" activeEnergyBurnedGoal="500"/>\n',
])
EXPORT = HEADER + BODY + "</HealthData>\n"


def make_zip(path, xml=EXPORT, name="apple_health_export/export.xml", extra=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, xml)
        zf.writestr("apple_health_export/export_cda.xml", "<ClinicalDocument/>")
        for extra_name, content in (extra or {}).items():
            zf.writestr(extra_name, content)
    return path


def run(db, path):
    return apple.import_export(db, str(path), 50 * 1024 * 1024)


def test_full_export(db, tmp_path):
    progress = []
    counts = apple.import_export(db, str(make_zip(tmp_path / "e.zip")), 50 * 1024 * 1024,
                                 progress.append)
    assert progress[-1] == 100 and counts["uebersprungen"] == 1
    day = "2026-09-01"
    steps = store.per_source(db, "steps", day, "2026-09-02")
    assert steps[day] == {"apple_watch": 9000, "iphone": 6500}
    assert steps["2026-09-02"] == {"apple_garmin": 8000}
    assert store.daily_series(db, "steps", day, day)[0]["source"] == "apple_watch"
    assert store.per_source(db, "distance_km", day, day)[day]["apple_watch"] == pytest.approx(4.989, 0.001)
    assert store.per_source(db, "active_kcal", day, day)[day]["apple_watch"] == pytest.approx(239.0, 0.01)
    assert store.per_source(db, "hr_min", day, day)[day]["apple_watch"] == 55
    assert store.per_source(db, "hr_max", day, day)[day]["apple_watch"] == 140
    assert store.latest(db, "spo2")["value"] == pytest.approx(97)
    weight = store.latest(db, "weight")
    assert weight["value"] == pytest.approx(80.01, 0.01) and weight["source"] == "apple_withings"
    assert store.latest(db, "fat_ratio")["value"] == pytest.approx(21.5)
    assert store.latest(db, "height")["value"] == pytest.approx(181)
    assert store.latest(db, "temperature")["value"] == pytest.approx(37.0)
    bp = store.readings(db, ("bp_sys", "bp_dia"), day, day)
    assert len(bp) == 1 and bp[0]["values"] == {"bp_sys": 127, "bp_dia": 82}


def test_sleep_nights(db, tmp_path):
    run(db, make_zip(tmp_path / "e.zip"))
    rows = {r["source"]: dict(r) for r in db.execute("SELECT * FROM sleep")}
    watch = rows["apple_watch"]
    assert watch["night"] == "2026-09-01"
    assert watch["asleep_min"] == 2 * 60 + 60 + 90 + 165   # core + deep + rem + core
    assert watch["deep_min"] == 60 and watch["rem_min"] == 90 and watch["awake_min"] == 15
    assert watch["bed_start"] == "2026-08-31 22:40:00"
    assert rows["iphone"]["asleep_min"] is None and rows["iphone"]["deep_min"] is None
    assert store.sleep_series(db, "2026-09-01", "2026-09-01")[0]["source"] == "apple_watch"


def test_workouts(db, tmp_path):
    run(db, make_zip(tmp_path / "e.zip"))
    rows = {r["kind"]: dict(r) for r in db.execute("SELECT * FROM workouts")}
    run_row = rows["laufen"]
    assert run_row["source"] == "apple_watch" and run_row["duration_min"] == 42.5
    assert run_row["distance_km"] == 7.4 and run_row["energy_kcal"] == 455
    assert run_row["hr_avg"] == 151 and run_row["hr_max"] == 176
    kraft = rows["kraft"]
    assert kraft["source"] == "apple_garmin" and kraft["duration_min"] == 45
    assert kraft["energy_kcal"] == pytest.approx(215.1, 0.1)


def test_reimport_does_not_duplicate(db, tmp_path):
    path = make_zip(tmp_path / "e.zip")
    run(db, path)
    before = [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in store.HEALTH_TABLES]
    run(db, path)
    after = [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in store.HEALTH_TABLES]
    assert before == after
    assert store.per_source(db, "steps", "2026-09-01", "2026-09-01")["2026-09-01"]["apple_watch"] == 9000


def test_german_file_name(db, tmp_path):
    run(db, make_zip(tmp_path / "e.zip", name="apple_health_export/exportieren.xml"))
    assert store.latest(db, "weight")


@pytest.mark.parametrize("name,device,expected", [
    ("Apple Watch von Anna", "", "apple_watch"),
    ("Annas iPhone", "", "iphone"),
    ("x", "<<HKDevice>, model:Watch, hardware:Watch7,2>", "apple_watch"),
    ("Connect", "", "apple_garmin"),
    ("Garmin Connect", "", "apple_garmin"),
    ("Health Mate", "", "apple_withings"),
    ("Withings", "", "apple_withings"),
    ("MyFitnessPal", "", "apple_andere"),
])
def test_source_mapping(name, device, expected):
    assert apple.source_key(name, device) == expected


def test_time_parsing():
    assert str(apple.parse_time("2026-09-01 22:30:00 -0400")) == "2026-09-02 04:30:00"
    assert apple.parse_time("kaputt") is None


def test_not_a_zip(db, tmp_path):
    path = tmp_path / "e.zip"
    path.write_text(EXPORT)
    with pytest.raises(AppleImportError, match="keine ZIP"):
        run(db, path)


def test_zip_without_export(db, tmp_path):
    path = tmp_path / "e.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("bild.jpg", b"x")
    with pytest.raises(AppleImportError, match="fehlt"):
        run(db, path)


def test_zip_bomb_is_refused(db, tmp_path):
    path = make_zip(tmp_path / "e.zip", xml=HEADER + " " * 5_000_000 + "</HealthData>")
    with pytest.raises(AppleImportError, match="gepackt"):
        run(db, path)


def test_too_large_is_refused(db, tmp_path):
    path = make_zip(tmp_path / "e.zip")
    with pytest.raises(AppleImportError, match="zu groß"):
        apple.import_export(db, str(path), 1000)


def test_entities_are_refused(db, tmp_path):
    evil = ('<?xml version="1.0"?>\n<!DOCTYPE HealthData [<!ENTITY a "aaaaaaaaaa">'
            '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>\n<HealthData>&b;</HealthData>')
    with pytest.raises(AppleImportError):
        run(db, make_zip(tmp_path / "e.zip", xml=evil))
    assert db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 0


def test_external_entity_is_refused(db, tmp_path):
    evil = ('<?xml version="1.0"?>\n<!DOCTYPE HealthData [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            '\n<HealthData>&x;</HealthData>')
    with pytest.raises(AppleImportError):
        run(db, make_zip(tmp_path / "e.zip", xml=evil))


def test_other_xml_is_refused(db, tmp_path):
    with pytest.raises(AppleImportError, match="kein Apple"):
        run(db, make_zip(tmp_path / "e.zip", xml="<?xml version='1.0'?><svg></svg>"))


def test_broken_xml(db, tmp_path):
    with pytest.raises(AppleImportError, match="beschädigt"):
        run(db, make_zip(tmp_path / "e.zip", xml=EXPORT[:-40]))


def test_paths_inside_zip_are_never_used(db, tmp_path):
    path = make_zip(tmp_path / "e.zip", extra={"../../boese.txt": "x"})
    run(db, path)
    assert not (tmp_path.parent / "boese.txt").exists()


# ---------- Upload through the page ----------

def upload(logged_in, content, filename="Export.zip", ajax=False, token=None):
    logged_in.get("/quellen")
    headers = {"X-Gesundheit-Ajax": "1"} if ajax else {}
    return logged_in.client.post("/quellen/apple/hochladen", data={
        "csrf_token": token or logged_in.token, "datei": (io.BytesIO(content), filename)},
        content_type="multipart/form-data", headers=headers)


def zip_bytes(tmp_path):
    return make_zip(tmp_path / "upload.zip").read_bytes()


def test_upload_imports_and_removes_file(app, logged_in, db, tmp_path):
    response = upload(logged_in, zip_bytes(tmp_path), ajax=True)
    data = response.get_json()
    assert response.status_code == 200 and data["ok"]
    status = logged_in.client.get(data["status_url"]).get_json()
    assert status["status"] == "fertig" and status["progress"] == 100
    assert store.latest(db, "weight")
    uploads = Path(app.config["UPLOAD_DIR"])
    assert list(uploads.iterdir()) == []  # neither the upload nor a temporary part remains
    page = logged_in.get("/quellen").get_data(as_text=True)
    assert "Nächte" in page and "fertig" in page


def test_upload_without_javascript_redirects(logged_in, tmp_path):
    response = upload(logged_in, zip_bytes(tmp_path))
    assert response.status_code == 302 and response.headers["Location"].endswith("#apple")


def test_upload_needs_csrf(logged_in, tmp_path):
    response = upload(logged_in, zip_bytes(tmp_path), ajax=True, token="falsch")
    assert response.status_code == 400


def test_upload_rejects_other_files(logged_in, db):
    response = upload(logged_in, b"hallo", filename="notizen.txt", ajax=True)
    assert response.status_code == 400 and "ZIP" in response.get_json()["nachricht"]


def test_broken_upload_is_reported(logged_in, db):
    response = upload(logged_in, b"PK-kein-zip", ajax=True)
    status = logged_in.client.get(response.get_json()["status_url"]).get_json()
    assert status["status"] == "fehler" and "keine ZIP" in status["message"]


def test_upload_limit(app, logged_in, tmp_path):
    app.config["UPLOAD_MAX_MB"] = 1
    response = upload(logged_in, b"0" * (1024 * 1024 + 10), ajax=True)
    assert response.status_code == 413 and "Import-Ordner" in response.get_json()["nachricht"]


def test_large_upload_without_login_is_refused_early(app):
    response = app.test_client().post("/quellen/apple/hochladen", data={
        "datei": (io.BytesIO(b"0" * (3 * 1024 * 1024)), "Export.zip")},
        content_type="multipart/form-data")
    assert response.status_code == 413
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


def test_normal_forms_keep_small_limit(logged_in):
    logged_in.get("/einstellungen")
    response = logged_in.post("/einstellungen/ziele", {"goal_steps": "1" * (3 * 1024 * 1024)})
    assert response.status_code == 413


def test_import_folder(app, logged_in, db, tmp_path):
    folder = Path(app.config["IMPORT_DIR"])
    folder.mkdir()
    make_zip(folder / "export.zip")
    (folder / "link.zip").symlink_to(folder / "export.zip")
    logged_in.get("/quellen")
    logged_in.post("/quellen/apple/ordner")
    assert store.latest(db, "weight")
    assert (folder / "export.zip").exists()  # the folder may be read-only: file stays
    names = [p.name for p in __import__("gesundheit").jobs.import_folder_files(app)]
    assert names == ["export.zip"]
