"""What the app knows: sources, value families with their source order, and every metric.

A *source* is where a value comes from (Withings directly, Garmin directly, or a device or
app inside the Apple Health export). A *family* groups metrics that share one source order:
per day the first source in the order that has a value wins (see store.py).
"""

from dataclasses import dataclass

# key: label, short label for chips, kind (direct connection or part of the Apple export)
SOURCES = {
    "withings": ("Withings", "Withings", "direkt"),
    "garmin": ("Garmin", "Garmin", "direkt"),
    "apple_watch": ("Apple Watch", "Watch", "apple"),
    "iphone": ("iPhone", "iPhone", "apple"),
    "apple_garmin": ("Garmin über Apple Health", "Garmin (Apple)", "apple"),
    "apple_withings": ("Withings über Apple Health", "Withings (Apple)", "apple"),
    "apple_andere": ("Andere Apps über Apple Health", "Andere (Apple)", "apple"),
}
APPLE_SOURCES = tuple(k for k, v in SOURCES.items() if v[2] == "apple")

# key: label, description, default source order
FAMILIES = {
    "koerper": ("Körper", "Gewicht, Fett, Muskeln, Wasser, Knochen, Größe",
                ["withings", "apple_withings", "apple_andere", "iphone", "garmin",
                 "apple_garmin", "apple_watch"]),
    "blutdruck": ("Blutdruck", "Systolisch, diastolisch, Puls bei der Messung",
                  ["withings", "apple_withings", "apple_andere", "iphone", "garmin",
                   "apple_garmin", "apple_watch"]),
    "herz": ("Herz und Erholung", "Ruhepuls, HRV, Sauerstoff, Atmung, VO2max, Body Battery",
             ["garmin", "apple_garmin", "apple_watch", "withings", "apple_withings", "iphone",
              "apple_andere"]),
    "temperatur": ("Temperatur", "Körpertemperatur vom Thermometer",
                   ["withings", "apple_withings", "apple_andere", "iphone", "apple_watch",
                    "garmin", "apple_garmin"]),
    "schlaf": ("Schlaf", "Dauer, Phasen, Bewertung",
               ["garmin", "apple_garmin", "apple_watch", "withings", "apple_withings",
                "apple_andere", "iphone"]),
    "aktivitaet": ("Aktivität", "Schritte, Strecke, Kalorien, Etagen, aktive Minuten, Trainings",
                   ["garmin", "apple_garmin", "apple_watch", "iphone", "withings",
                    "apple_withings", "apple_andere"]),
}


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    family: str
    agg: str            # per day and source: mean, last, sum, min, max
    decimals: int
    lo: float           # plausible range; values outside are dropped on import
    hi: float
    chart: str = "line"  # line, bar
    good: str = ""       # direction that counts as better: up, down, or "" (neutral)
    page: str = ""       # page that shows it (views), for links


_M = [
    # Körper
    Metric("weight", "Gewicht", "kg", "koerper", "last", 1, 20, 400, page="koerper"),
    Metric("fat_ratio", "Körperfett", "%", "koerper", "last", 1, 1, 75, good="down",
           page="koerper"),
    Metric("fat_mass", "Fettmasse", "kg", "koerper", "last", 1, 0.5, 250, good="down",
           page="koerper"),
    Metric("fat_free_mass", "Fettfreie Masse", "kg", "koerper", "last", 1, 10, 250,
           page="koerper"),
    Metric("muscle_mass", "Muskelmasse", "kg", "koerper", "last", 1, 5, 200, good="up",
           page="koerper"),
    Metric("hydration", "Körperwasser", "kg", "koerper", "last", 1, 5, 200, page="koerper"),
    Metric("bone_mass", "Knochenmasse", "kg", "koerper", "last", 1, 0.5, 10, page="koerper"),
    Metric("visceral_fat", "Viszeralfett", "Index", "koerper", "last", 0, 0, 60, good="down",
           page="koerper"),
    Metric("bmr", "Grundumsatz", "kcal", "koerper", "last", 0, 500, 5000, page="koerper"),
    Metric("height", "Größe", "cm", "koerper", "last", 0, 100, 250, page="koerper"),
    # Blutdruck
    Metric("bp_sys", "Systolisch", "mmHg", "blutdruck", "mean", 0, 50, 260, good="down",
           page="herz"),
    Metric("bp_dia", "Diastolisch", "mmHg", "blutdruck", "mean", 0, 30, 180, good="down",
           page="herz"),
    Metric("pulse", "Puls bei der Messung", "bpm", "blutdruck", "mean", 0, 25, 250,
           page="herz"),
    # Herz und Erholung
    Metric("resting_hr", "Ruhepuls", "bpm", "herz", "mean", 0, 25, 150, good="down",
           page="herz"),
    Metric("hr_min", "Niedrigster Puls", "bpm", "herz", "min", 0, 20, 200, page="herz"),
    Metric("hr_max", "Höchster Puls", "bpm", "herz", "max", 0, 40, 250, page="herz"),
    Metric("hrv_rmssd", "HRV nachts (RMSSD)", "ms", "herz", "mean", 0, 1, 300, good="up",
           page="herz"),
    Metric("hrv_sdnn", "HRV (SDNN)", "ms", "herz", "mean", 0, 1, 300, good="up", page="herz"),
    Metric("spo2", "Sauerstoffsättigung", "%", "herz", "mean", 1, 50, 100, good="up",
           page="herz"),
    Metric("resp_rate", "Atemfrequenz", "/min", "herz", "mean", 1, 4, 60, page="herz"),
    Metric("vo2max", "VO2max", "ml/kg/min", "herz", "last", 1, 10, 95, good="up",
           page="aktivitaet"),
    Metric("pwv", "Pulswellengeschwindigkeit", "m/s", "herz", "mean", 1, 2, 25, good="down",
           page="herz"),
    Metric("ekg_afib", "EKG-Einstufung", "", "herz", "last", 0, 0, 2, page="herz"),
    Metric("ekg_puls", "Puls beim EKG", "bpm", "herz", "last", 0, 25, 250, page="herz"),
    Metric("body_battery_max", "Body Battery (höchster Wert)", "", "herz", "max", 0, 0, 100,
           good="up", page="aktivitaet"),
    Metric("body_battery_min", "Body Battery (niedrigster Wert)", "", "herz", "min", 0, 0, 100,
           good="up", page="aktivitaet"),
    Metric("stress_avg", "Stress (Durchschnitt)", "", "herz", "mean", 0, 0, 100, good="down",
           page="aktivitaet"),
    Metric("readiness", "Trainingsbereitschaft", "", "herz", "last", 0, 0, 100, good="up",
           page="aktivitaet"),
    # Temperatur
    Metric("temperature", "Körpertemperatur", "°C", "temperatur", "mean", 1, 30, 45,
           page="herz"),
    # Aktivität
    Metric("steps", "Schritte", "", "aktivitaet", "sum", 0, 0, 150000, chart="bar",
           good="up", page="aktivitaet"),
    Metric("distance_km", "Strecke", "km", "aktivitaet", "sum", 1, 0, 500, chart="bar",
           good="up", page="aktivitaet"),
    Metric("active_kcal", "Aktivkalorien", "kcal", "aktivitaet", "sum", 0, 0, 15000,
           chart="bar", good="up", page="aktivitaet"),
    Metric("floors", "Etagen", "", "aktivitaet", "sum", 0, 0, 1000, chart="bar", good="up",
           page="aktivitaet"),
    Metric("active_min", "Aktive Minuten", "min", "aktivitaet", "sum", 0, 0, 1440,
           chart="bar", good="up", page="aktivitaet"),
]
METRICS = {m.key: m for m in _M}

# Not shown as a chart of their own (codes, or values that only make sense next to others).
NO_CHART = {"ekg_afib", "ekg_puls", "height"}

EKG_LABELS = {0: "Kein Vorhofflimmern erkannt", 1: "Hinweis auf Vorhofflimmern",
              2: "Nicht eindeutig"}

# Sleep is a family of its own with its own table; these are its fields for charts.
SLEEP_FIELDS = {
    "asleep_min": "Schlafdauer", "deep_min": "Tiefschlaf", "light_min": "Leichtschlaf",
    "rem_min": "REM", "awake_min": "Wach", "score": "Bewertung", "hr_avg": "Puls im Schlaf",
    "rr_avg": "Atemfrequenz im Schlaf",
}

WORKOUT_KINDS = {
    "laufen": "Laufen", "radfahren": "Radfahren", "gehen": "Gehen", "wandern": "Wandern",
    "schwimmen": "Schwimmen", "kraft": "Krafttraining", "yoga": "Yoga und Pilates",
    "hiit": "Intervall- und Ausdauertraining", "rudern": "Rudern",
    "crosstrainer": "Crosstrainer", "tanzen": "Tanzen", "ballsport": "Ballsport",
    "wintersport": "Wintersport", "sonstiges": "Training",
}

APPLE_WORKOUTS = {
    "Running": "laufen", "Cycling": "radfahren", "HandCycling": "radfahren",
    "Walking": "gehen", "Hiking": "wandern", "Swimming": "schwimmen",
    "TraditionalStrengthTraining": "kraft", "FunctionalStrengthTraining": "kraft",
    "CoreTraining": "kraft", "Yoga": "yoga", "Pilates": "yoga", "MindAndBody": "yoga",
    "Flexibility": "yoga", "HighIntensityIntervalTraining": "hiit", "CrossTraining": "hiit",
    "MixedCardio": "hiit", "StairClimbing": "hiit", "Stairs": "hiit", "JumpRope": "hiit",
    "Rowing": "rudern", "Elliptical": "crosstrainer", "Dance": "tanzen",
    "SocialDance": "tanzen", "CardioDance": "tanzen", "Soccer": "ballsport",
    "Basketball": "ballsport", "Tennis": "ballsport", "Volleyball": "ballsport",
    "Handball": "ballsport", "Badminton": "ballsport", "TableTennis": "ballsport",
    "Squash": "ballsport", "Golf": "ballsport", "DownhillSkiing": "wintersport",
    "CrossCountrySkiing": "wintersport", "Snowboarding": "wintersport",
    "SnowSports": "wintersport", "SkatingSports": "wintersport",
}

GARMIN_WORKOUTS = {
    "running": "laufen", "trail_running": "laufen", "treadmill_running": "laufen",
    "track_running": "laufen", "indoor_running": "laufen", "cycling": "radfahren",
    "road_biking": "radfahren", "mountain_biking": "radfahren", "gravel_cycling": "radfahren",
    "indoor_cycling": "radfahren", "virtual_ride": "radfahren", "e_bike_fitness": "radfahren",
    "walking": "gehen", "casual_walking": "gehen", "speed_walking": "gehen",
    "hiking": "wandern", "lap_swimming": "schwimmen", "open_water_swimming": "schwimmen",
    "swimming": "schwimmen", "strength_training": "kraft", "yoga": "yoga", "pilates": "yoga",
    "breathwork": "yoga", "hiit": "hiit", "cardio": "hiit", "fitness_equipment": "hiit",
    "stair_climbing": "hiit", "rowing": "rudern", "indoor_rowing": "rudern",
    "elliptical": "crosstrainer", "dance": "tanzen", "soccer": "ballsport",
    "tennis": "ballsport", "golf": "ballsport", "resort_skiing_snowboarding": "wintersport",
    "cross_country_skiing": "wintersport", "backcountry_skiing": "wintersport",
    "skate_skiing": "wintersport",
}

WITHINGS_WORKOUTS = {
    1: "gehen", 2: "laufen", 3: "wandern", 6: "radfahren", 7: "schwimmen", 12: "ballsport",
    13: "ballsport", 14: "ballsport", 15: "ballsport", 16: "kraft", 17: "kraft",
    18: "crosstrainer", 19: "yoga", 20: "ballsport", 21: "ballsport", 22: "ballsport",
    23: "ballsport", 24: "ballsport", 27: "ballsport", 28: "yoga", 29: "tanzen",
    34: "wintersport", 35: "wintersport", 187: "rudern", 188: "tanzen", 191: "ballsport",
    192: "ballsport", 306: "gehen", 307: "laufen", 308: "radfahren",
}


def source_label(key: str, short: bool = False) -> str:
    entry = SOURCES.get(key)
    if not entry:
        return key
    return entry[1] if short else entry[0]
