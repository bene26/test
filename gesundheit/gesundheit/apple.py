"""Apple Health export (export.zip from the Health app on the iPhone).

The ZIP is treated as hostile input: only one XML file inside is read, as a stream, never
unpacked to disk; sizes and the compression ratio are limited (zip bomb); the XML parser
refuses entities and external references (defusedxml). Only known record types are used.

High-frequency values (steps, energy, distance, heart rate …) are summed up or averaged per
day and source while reading; the single samples are not stored (data minimisation).
Sleep stages become one night per source, workouts are stored one by one.
"""

import logging
import zipfile
from datetime import datetime, timedelta, timezone

from defusedxml.ElementTree import iterparse

from . import store, util
from .katalog import APPLE_WORKOUTS

log = logging.getLogger("gesundheit")

MAX_RATIO = 200          # uncompressed / compressed size of the XML inside the ZIP
COMMIT_EVERY = 20000

# Apple type -> (metric, how to store): point = single reading, sum/mean/min/max per day
QUANTITY = {
    "HKQuantityTypeIdentifierBodyMass": ("weight", "point"),
    "HKQuantityTypeIdentifierBodyFatPercentage": ("fat_ratio", "point"),
    "HKQuantityTypeIdentifierLeanBodyMass": ("fat_free_mass", "point"),
    "HKQuantityTypeIdentifierHeight": ("height", "point"),
    "HKQuantityTypeIdentifierBloodPressureSystolic": ("bp_sys", "point"),
    "HKQuantityTypeIdentifierBloodPressureDiastolic": ("bp_dia", "point"),
    "HKQuantityTypeIdentifierBodyTemperature": ("temperature", "point"),
    "HKQuantityTypeIdentifierVO2Max": ("vo2max", "point"),
    "HKQuantityTypeIdentifierStepCount": ("steps", "sum"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance_km", "sum"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_kcal", "sum"),
    "HKQuantityTypeIdentifierFlightsClimbed": ("floors", "sum"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("active_min", "sum"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "mean"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", "mean"),
    "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", "mean"),
    "HKQuantityTypeIdentifierRespiratoryRate": ("resp_rate", "mean"),
    "HKQuantityTypeIdentifierHeartRate": ("hr", "minmax"),
}
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
SLEEP_STAGES = {
    "HKCategoryValueSleepAnalysisInBed": "bett",
    "HKCategoryValueSleepAnalysisAsleep": "schlaf",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "schlaf",
    "HKCategoryValueSleepAnalysisAsleepCore": "leicht",
    "HKCategoryValueSleepAnalysisAsleepDeep": "tief",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem",
    "HKCategoryValueSleepAnalysisAwake": "wach",
}
SESSION_GAP = timedelta(hours=3)


class AppleImportError(Exception):
    """Message is safe to show to the user."""


# ---------- Units ----------

def convert(metric: str, value: float, unit: str) -> float | None:
    unit = (unit or "").strip()
    if metric in ("weight", "fat_free_mass"):
        return {"kg": value, "lb": value * 0.45359237, "g": value / 1000,
                "st": value * 6.35029318}.get(unit)
    if metric == "height":
        return {"cm": value, "m": value * 100, "in": value * 2.54, "ft": value * 30.48,
                "mm": value / 10}.get(unit)
    if metric in ("fat_ratio", "spo2"):
        return value * 100 if unit == "%" and value <= 1 else value
    if metric == "distance_km":
        return {"km": value, "m": value / 1000, "mi": value * 1.609344,
                "yd": value * 0.0009144, "ft": value * 0.0003048}.get(unit)
    if metric == "active_kcal":
        return {"kcal": value, "Cal": value, "kJ": value / 4.184, "cal": value / 1000}.get(unit)
    if metric == "temperature":
        return {"degC": value, "degF": (value - 32) * 5 / 9}.get(unit)
    if metric == "active_min":
        return {"min": value, "s": value / 60, "hr": value * 60}.get(unit)
    if metric == "hrv_sdnn":
        return {"ms": value, "s": value * 1000}.get(unit)
    return value


# ---------- Sources ----------

def source_key(source_name: str, device: str) -> str:
    """Map Apple's sourceName/device to one of our source keys (katalog.SOURCES)."""
    name = (source_name or "").lower()
    dev = (device or "").lower()
    if "garmin" in name or name.strip() == "connect" or "manufacturer:garmin" in dev:
        return "apple_garmin"
    if "withings" in name or "health mate" in name or "manufacturer:withings" in dev:
        return "apple_withings"
    if "model:watch" in dev or "watch" in name:
        return "apple_watch"
    if "model:iphone" in dev or "iphone" in name:
        return "iphone"
    return "apple_andere"


def parse_time(text: str) -> datetime | None:
    """'2024-03-01 08:15:00 +0100' -> local time without tzinfo."""
    try:
        base = datetime.fromisoformat(text[:19])
        offset = text[20:].strip()
        sign = -1 if offset.startswith("-") else 1
        minutes = sign * (int(offset[1:3]) * 60 + int(offset[3:5]))
        return util.localize(base.replace(tzinfo=timezone(timedelta(minutes=minutes))))
    except (ValueError, IndexError, TypeError):
        return None


# ---------- File checks ----------

class _Counter:
    """File wrapper that counts bytes (progress) and stops at the declared size."""

    def __init__(self, raw, limit: int):
        self.raw = raw
        self.limit = limit
        self.read_bytes = 0

    def read(self, size=-1):
        chunk = self.raw.read(size if size and size > 0 else 1 << 20)
        self.read_bytes += len(chunk)
        if self.read_bytes > self.limit:
            raise AppleImportError("Die Datei ist größer als angegeben. Import abgebrochen.")
        return chunk


def find_export(path, xml_max_bytes: int):
    """Open the ZIP and return (zipfile, ZipInfo of the export XML)."""
    if not zipfile.is_zipfile(path):
        raise AppleImportError("Das ist keine ZIP-Datei. Bitte die Datei „Export.zip“ aus der "
                           "Health-App hochladen.")
    archive = zipfile.ZipFile(path)
    candidates = []
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        base = name.rsplit("/", 1)[-1].lower()
        if (info.is_dir() or not base.endswith(".xml") or base.endswith("_cda.xml")
                or name.count("/") > 2 or "__macosx" in name.lower()):
            continue
        candidates.append(info)
    if not candidates:
        archive.close()
        raise AppleImportError("In der ZIP-Datei fehlt die Datei export.xml.")
    info = max(candidates, key=lambda i: i.file_size)
    if info.file_size > xml_max_bytes:
        archive.close()
        raise AppleImportError("Die Export-Datei ist zu groß.")
    if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
        archive.close()
        raise AppleImportError("Die ZIP-Datei ist ungewöhnlich stark gepackt und wird aus "
                           "Sicherheitsgründen nicht gelesen.")
    return archive, info


# ---------- Import ----------

class _Aggregator:
    def __init__(self):
        self.daily: dict[tuple, list] = {}   # (metric, day, source) -> [sum, count, min, max]

    def add(self, metric, day, source, value):
        entry = self.daily.get((metric, day, source))
        if entry is None:
            self.daily[(metric, day, source)] = [value, 1, value, value]
        else:
            entry[0] += value
            entry[1] += 1
            if value < entry[2]:
                entry[2] = value
            if value > entry[3]:
                entry[3] = value

    def rows(self, modes: dict):
        for (metric, day, source), (total, count, low, high) in self.daily.items():
            mode = modes[metric]
            if mode == "sum":
                yield metric, day, source, total
            elif mode == "mean":
                yield metric, day, source, total / count
            elif mode == "minmax":
                yield "hr_min", day, source, low
                yield "hr_max", day, source, high


def _sleep_nights(samples: dict[str, list]) -> list[tuple]:
    """Group stage samples per source into sessions (gap < 3 h) -> nights."""
    nights = []
    for source, items in samples.items():
        items.sort()
        session: list = []
        for item in items + [None]:
            if session and (item is None or item[0] - max(s[1] for s in session) > SESSION_GAP):
                nights.append((source, session))
                session = []
            if item is not None:
                session.append(item)
    result = []
    for source, session in nights:
        minutes = {"bett": 0.0, "schlaf": 0.0, "leicht": 0.0, "tief": 0.0, "rem": 0.0,
                   "wach": 0.0}
        for start, end, stage in session:
            minutes[stage] += (end - start).total_seconds() / 60
        asleep = minutes["schlaf"] + minutes["leicht"] + minutes["tief"] + minutes["rem"]
        start = min(s[0] for s in session)
        end = max(s[1] for s in session)
        staged = minutes["leicht"] + minutes["tief"] + minutes["rem"] > 0
        result.append((end.date(), source, {
            "bed_start": start, "bed_end": end, "asleep_min": asleep or None,
            "deep_min": minutes["tief"] if staged else None,
            "light_min": minutes["leicht"] if staged else None,
            "rem_min": minutes["rem"] if staged else None,
            "awake_min": minutes["wach"] if (staged or minutes["wach"]) else None,
        }))
    # Several sessions of one source ending on the same day: keep the longest (naps aside).
    best: dict[tuple, tuple] = {}
    for night, source, data in result:
        key = (night, source)
        length = data["asleep_min"] or (data["bed_end"] - data["bed_start"]).total_seconds() / 60
        if key not in best or length > best[key][0]:
            best[key] = (length, data)
    return [(night, source, data) for (night, source), (_l, data) in best.items()]


def _workout(element, attrs) -> dict | None:
    start = parse_time(attrs.get("startDate", ""))
    end = parse_time(attrs.get("endDate", ""))
    if not start:
        return None
    kind_raw = attrs.get("workoutActivityType", "").replace("HKWorkoutActivityType", "")
    data = {"kind": APPLE_WORKOUTS.get(kind_raw, "sonstiges"), "started_at": start,
            "ended_at": end}
    try:
        duration = float(attrs.get("duration", ""))
        data["duration_min"] = convert("active_min", duration, attrs.get("durationUnit", "min"))
    except ValueError:
        if end:
            data["duration_min"] = (end - start).total_seconds() / 60
    for value_key, unit_key, metric, target in (
            ("totalDistance", "totalDistanceUnit", "distance_km", "distance_km"),
            ("totalEnergyBurned", "totalEnergyBurnedUnit", "active_kcal", "energy_kcal")):
        try:
            data[target] = convert(metric, float(attrs[value_key]), attrs.get(unit_key, ""))
        except (KeyError, ValueError):
            pass
    for child in element:
        if child.tag != "WorkoutStatistics":
            continue
        kind = child.get("type", "")
        try:
            if kind == "HKQuantityTypeIdentifierHeartRate":
                data["hr_avg"] = float(child.get("average", ""))
                data["hr_max"] = float(child.get("maximum", ""))
            elif kind == "HKQuantityTypeIdentifierActiveEnergyBurned" and "energy_kcal" not in data:
                data["energy_kcal"] = convert("active_kcal", float(child.get("sum", "")),
                                              child.get("unit", ""))
            elif kind.startswith("HKQuantityTypeIdentifierDistance") and "distance_km" not in data:
                data["distance_km"] = convert("distance_km", float(child.get("sum", "")),
                                              child.get("unit", ""))
        except ValueError:
            pass
    return data


def import_export(db, path, xml_max_bytes: int, progress=lambda percent: None) -> dict:
    """Read the export and store everything. Returns counts per kind."""
    archive, info = find_export(path, xml_max_bytes)
    counts = {"messwerte": 0, "tageswerte": 0, "naechte": 0, "trainings": 0, "uebersprungen": 0}
    aggregator = _Aggregator()
    modes = {metric: mode for metric, mode in QUANTITY.values()}
    sleep_samples: dict[str, list] = {}
    points = []
    since_commit = 0
    last_percent = -1
    try:
        with archive.open(info) as raw:
            stream = _Counter(raw, info.file_size + 1024)
            depth = 0
            root = None
            for event, element in iterparse(stream, events=("start", "end")):
                if event == "start":
                    depth += 1
                    if root is None:
                        root = element
                        if element.tag != "HealthData":
                            raise AppleImportError("Das ist kein Apple-Health-Export.")
                    continue
                depth -= 1
                tag = element.tag
                if tag == "Record":
                    _record(element.attrib, aggregator, points, sleep_samples, counts)
                elif tag == "Workout" and depth == 1:
                    attrs = element.attrib
                    data = _workout(element, attrs)
                    if data:
                        source = source_key(attrs.get("sourceName", ""), attrs.get("device", ""))
                        external = f"{attrs.get('startDate', '')}|{data['kind']}"
                        counts["trainings"] += store.upsert_workout(db, source, external, data)
                if depth == 1:
                    root.clear()  # free memory of everything read so far
                    if len(points) >= 5000:
                        counts["messwerte"] += store.add_measurements(db, points)
                        since_commit += len(points)
                        points.clear()
                    if since_commit >= COMMIT_EVERY:
                        db.commit()
                        since_commit = 0
                    percent = int(stream.read_bytes * 90 / max(info.file_size, 1))
                    if percent != last_percent:
                        last_percent = percent
                        progress(percent)
    except AppleImportError:
        raise
    except Exception as exc:  # broken XML, truncated ZIP, CRC error …
        log.warning("Apple-Import abgebrochen: %s", type(exc).__name__)
        raise AppleImportError("Die Export-Datei ist beschädigt oder unvollständig. Bitte den "
                           "Export in der Health-App neu erstellen.") from None
    finally:
        archive.close()

    counts["messwerte"] += store.add_measurements(db, points)
    progress(92)
    counts["tageswerte"] = store.set_daily_many(db, aggregator.rows(modes))
    progress(96)
    for night, source, data in _sleep_nights(sleep_samples):
        counts["naechte"] += store.upsert_sleep(db, night, source, data)
    db.commit()
    progress(100)
    return counts


def _record(attrs, aggregator, points, sleep_samples, counts):
    kind = attrs.get("type", "")
    if kind == SLEEP_TYPE:
        stage = SLEEP_STAGES.get(attrs.get("value", ""))
        start, end = parse_time(attrs.get("startDate", "")), parse_time(attrs.get("endDate", ""))
        if stage and start and end and end > start and end - start < timedelta(hours=24):
            source = source_key(attrs.get("sourceName", ""), attrs.get("device", ""))
            sleep_samples.setdefault(source, []).append((start, end, stage))
        return
    mapping = QUANTITY.get(kind)
    if not mapping:
        return
    metric, mode = mapping
    try:
        value = float(attrs.get("value", ""))
    except ValueError:
        counts["uebersprungen"] += 1
        return
    value = convert(metric if metric != "hr" else "hr_max", value, attrs.get("unit", ""))
    start = parse_time(attrs.get("startDate", ""))
    if value is None or start is None:
        counts["uebersprungen"] += 1
        return
    source = source_key(attrs.get("sourceName", ""), attrs.get("device", ""))
    if mode == "point":
        points.append((metric, value, start, source, ""))
    else:
        aggregator.add(metric, start.date().isoformat(), source, value)
