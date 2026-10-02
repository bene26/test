"""Values typed in or imported by hand: the tape measure and the body analysis at the practice.

The Renpho tape sends only the waist through Apple Health (Apple knows no other body
circumference), and the practice hands out a printout. So both can be typed into a form or
imported as CSV (the app's template, or a table with similar column names). Each entry is one
group of measurements with its own id, so it can be deleted as a whole. A CSV file is treated
like any other foreign input: size and row limits, known columns only, every number checked
against the plausible range of its value.
"""

import csv
import io
import re
import secrets
import unicodedata
from datetime import datetime, time, timedelta

from . import auswertung, bewertung, charts, store, util
from .katalog import CIRCUMFERENCES, MANUAL_SOURCES, METRICS, PRACTICE_METRICS

KINDS = {
    "massband": {"label": "Maßband", "source": "massband", "metrics": CIRCUMFERENCES,
                 "hint": "Die zwölf Stellen des Renpho-Maßbands; leere Felder bleiben leer."},
    "praxis": {"label": "Körperanalyse in der Praxis", "source": "praxis",
               "metrics": PRACTICE_METRICS,
               "hint": "Die Werte vom Ausdruck der Ernährungsberatung (Messung mit Elektroden, "
                       "bioelektrische Impedanz). Körperwasser in Litern entspricht Kilogramm. "
                       "Muskelmasse so wie auf dem Ausdruck (oft nur die Skelettmuskulatur, "
                       "deshalb nicht mit der Waage vergleichbar)."},
}
GROUP_PATTERN = re.compile(r"^(massband|praxis)-[0-9a-f]{12}$")
CSV_MAX_BYTES = 1024 * 1024
CSV_MAX_ROWS = 5000
DEFAULT_TIME = time(8, 0)

# Column names that are understood (after lower case, without units in brackets).
SYNONYMS = {
    "date": ("datum", "date", "tag", "messdatum", "zeitpunkt"),
    "time": ("uhrzeit", "zeit", "time"),
    "circ_neck": ("hals", "halsumfang", "neck"),
    "circ_shoulders": ("schultern", "schulter", "schulterumfang", "shoulders", "shoulder"),
    "circ_chest": ("brust", "brustumfang", "chest"),
    "circ_waist": ("taille", "taillenumfang", "waist"),
    "circ_belly": ("bauch", "bauchumfang", "abdomen", "belly"),
    "circ_hip": ("hufte", "hueftumfang", "huftumfang", "huefte", "hip", "hips"),
    "circ_arm_l": ("oberarm links", "arm links", "linker oberarm", "left arm", "left upper arm",
                   "upper arm left", "arm left"),
    "circ_arm_r": ("oberarm rechts", "arm rechts", "rechter oberarm", "right arm",
                   "right upper arm", "upper arm right", "arm right"),
    "circ_thigh_l": ("oberschenkel links", "linker oberschenkel", "left thigh", "thigh left"),
    "circ_thigh_r": ("oberschenkel rechts", "rechter oberschenkel", "right thigh", "thigh right"),
    "circ_calf_l": ("wade links", "linke wade", "left calf", "calf left"),
    "circ_calf_r": ("wade rechts", "rechte wade", "right calf", "calf right"),
    "weight": ("gewicht", "korpergewicht", "weight"),
    "fat_ratio": ("korperfett", "fettanteil", "korperfettanteil", "body fat", "fat"),
    "fat_mass": ("fettmasse", "fat mass"),
    "fat_free_mass": ("magermasse", "fettfreie masse", "ffm", "lean mass", "fat free mass"),
    "muscle_mass": ("muskelmasse", "skelettmuskelmasse", "muscle mass", "smm"),
    "hydration": ("korperwasser", "gesamtkorperwasser", "tbw", "total body water", "wasser"),
    "bmr": ("grundumsatz", "ruheumsatz", "bmr"),
    "visceral_fat": ("viszeralfett", "visceral fat"),
    "phase_angle": ("phasenwinkel", "phase angle", "phi"),
    "bia_r": ("resistanz", "resistance", "r"),
    "bia_xc": ("reaktanz", "reactance", "xc"),
    "ecw": ("extrazellulares wasser", "ecw"),
    "icw": ("intrazellulares wasser", "icw"),
    "bcm": ("korperzellmasse", "bcm", "body cell mass"),
    "ecm": ("extrazellulare masse", "ecm"),
    "ecm_bcm": ("ecm/bcm", "ecm/bcm-index", "ecm-bcm-index", "ecm bcm index", "ecm bcm"),
    "cell_share": ("zellanteil", "bcm anteil", "bcm%"),
}
_COLUMN = {name: key for key, names in SYNONYMS.items() for name in names}


class ImportError_(ValueError):
    """The CSV file cannot be read; the message is safe to show."""


def _normal(header: str) -> str:
    text = re.sub(r"[\(\[].*?[\)\]]", "", header or "")         # units in brackets
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))  # ü -> u, ä -> a
    text = text.replace("ß", "ss").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip(" :")


def new_group(kind: str) -> str:
    return f"{kind}-{secrets.token_hex(6)}"


def save(db, pid: int, kind: str, when: datetime, values: dict) -> tuple[str, int]:
    """Store one entry; returns (group id, number of values kept)."""
    source = KINDS[kind]["source"]
    group = new_group(kind)
    rows = [(metric, value, when, source, group) for metric, value in values.items()
            if metric in KINDS[kind]["metrics"] and value is not None]
    return group, store.add_measurements(db, pid, rows)


def sessions(db, pid: int, limit: int = 30) -> list[dict]:
    """Entries typed in or imported, newest first, with their values."""
    marks = ", ".join("?" for _ in MANUAL_SOURCES)
    rows = db.execute(
        f"SELECT group_id, source, measured_at, metric, value FROM measurements "
        f"WHERE person_id = ? AND source IN ({marks}) AND group_id != '' "
        f"ORDER BY measured_at DESC, id", (pid, *MANUAL_SOURCES)).fetchall()
    groups: dict[str, dict] = {}
    for r in rows:
        if r["group_id"] not in groups:
            if len(groups) >= limit:
                break
            groups[r["group_id"]] = {"id": r["group_id"], "source": r["source"],
                                     "at": r["measured_at"], "values": []}
        groups[r["group_id"]]["values"].append((r["metric"], r["value"]))
    for group in groups.values():
        order = {m: i for i, m in enumerate(KINDS[group["source"]]["metrics"])}
        group["values"].sort(key=lambda mv: order.get(mv[0], 99))
    return list(groups.values())


def delete(db, pid: int, group: str) -> int:
    if not GROUP_PATTERN.match(group or ""):
        return 0
    marks = ", ".join("?" for _ in MANUAL_SOURCES)
    return db.execute(f"DELETE FROM measurements WHERE person_id = ? AND group_id = ? "
                      f"AND source IN ({marks})", (pid, group, *MANUAL_SOURCES)).rowcount


def _number(cell: str):
    match = re.match(r"^\s*(-?\d{1,6}(?:[.,]\d{1,3})?)\s*[a-zA-Z°%Ω/]*\s*$", cell or "")
    return float(match.group(1).replace(",", ".")) if match else None


def _when(day_text: str, time_text: str = "") -> datetime | None:
    text = (day_text or "").strip()
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", text) or None
    if match:
        y, m, d, hh, mm = match.groups()
    else:
        match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,?\s+(\d{1,2}):(\d{2}))?", text)
        if not match:
            return None
        d, m, y, hh, mm = match.groups()
    if not hh and time_text:
        tm = re.match(r"^\s*(\d{1,2}):(\d{2})", time_text)
        if tm:
            hh, mm = tm.groups()
    try:
        return datetime(int(y), int(m), int(d), int(hh or DEFAULT_TIME.hour),
                        int(mm or DEFAULT_TIME.minute))
    except ValueError:
        return None


def read_csv(raw: bytes) -> tuple[list[tuple[datetime, dict]], int, list[str]]:
    """(rows, skipped rows, columns not understood) from a CSV file."""
    if len(raw) > CSV_MAX_BYTES:
        raise ImportError_("Die Datei ist größer als 1 MB.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover (cp1252 decodes almost anything)
        raise ImportError_("Die Datei ist keine Textdatei.")
    if "\x00" in text:
        raise ImportError_("Die Datei ist keine Textdatei.")
    first = text.split("\n", 1)[0]
    delimiter = max((";", ",", "\t"), key=first.count)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ImportError_("Die Datei ist leer.") from None
    columns = [_COLUMN.get(_normal(h)) for h in header]
    unknown = [h.strip() for h, c in zip(header, columns) if c is None and h.strip()]
    if "date" not in columns:
        raise ImportError_("Keine Spalte „Datum“ gefunden.")
    if not any(c in METRICS for c in columns):
        raise ImportError_("Keine bekannte Messwert-Spalte gefunden (zum Beispiel „Taille“ "
                           "oder „Phasenwinkel“).")
    rows, skipped = [], 0
    for n, cells in enumerate(reader):
        if n >= CSV_MAX_ROWS:
            raise ImportError_(f"Mehr als {CSV_MAX_ROWS} Zeilen; bitte aufteilen.")
        if not any(c.strip() for c in cells):
            continue
        cells = cells + [""] * (len(columns) - len(cells))
        data = dict(zip(columns, cells))
        when = _when(data.get("date", ""), data.get("time", ""))
        values = {c: _number(v) for c, v in data.items() if c in METRICS}
        values = {k: v for k, v in values.items() if v is not None}
        if not when or when.date() > util.today() or not values:
            skipped += 1
            continue
        rows.append((when, values))
    return rows, skipped, unknown


def import_csv(db, pid: int, kind: str, raw: bytes) -> dict:
    """Store the rows of a CSV file as entries of one kind; counts for the message."""
    rows, skipped, unknown = read_csv(raw)
    allowed = KINDS[kind]["metrics"]
    entries = values = dropped = 0
    for when, data in rows:
        kept = {k: v for k, v in data.items() if k in allowed}
        dropped += len(data) - len(kept)
        if not kept:
            skipped += 1
            continue
        _group, count = save(db, pid, kind, when, kept)
        entries += 1 if count else 0
        values += count
        dropped += len(kept) - count          # outside the plausible range
    return {"entries": entries, "values": values, "skipped": skipped, "dropped": dropped,
            "unknown": unknown}


def template(kind: str) -> tuple[list[str], list[str]]:
    """Header and an example row for the CSV template."""
    metrics = KINDS[kind]["metrics"]
    header = ["Datum", "Uhrzeit"] + [
        f"{METRICS[m].label} ({METRICS[m].unit})" if METRICS[m].unit else METRICS[m].label
        for m in metrics]
    return header, [util.today().strftime("%d.%m.%Y"), "08:00"] + [""] * len(metrics)


# ---------- Showing them on the body page ----------

# Everything both the scale and the practice report. Muscle mass is compared too, with a
# note: scales usually report all muscle (with its water), practices often skeletal muscle
# only, so a fixed gap is expected; what counts is that both move the same way.
COMPARE = ("weight", "fat_ratio", "fat_mass", "fat_free_mass", "muscle_mass", "hydration", "bmr",
           "visceral_fat")
COMPARE_NOTES = {
    "muscle_mass": "Die Waage zählt meist alle Muskeln mit ihrem Wasser, die Praxis oft nur die "
                   "Skelettmuskulatur; ein fester Abstand ist normal.",
    "visceral_fat": "Waagen und Praxisgeräte nutzen verschiedene Skalen für das Viszeralfett.",
    "bmr": "Der Grundumsatz ist bei beiden eine Schätzung aus Formeln.",
}
CHART_CIRCUMFERENCES = (("circ_waist", "u-taille"), ("circ_belly", "u-bauch"), ("circ_hip", "u-huefte"))


def circumferences(db, pid: int, today, days: int = 365) -> dict | None:
    """Latest value of every circumference with its change, waist to height, and a chart."""
    today = util.to_date(today)
    start = today - timedelta(days=days - 1)
    tiles = []
    for key in CIRCUMFERENCES:
        latest = store.latest(db, pid, key)
        if not latest:
            continue
        last_day = util.to_date(latest["day"])
        earlier = store.daily_series(db, pid, key, last_day - timedelta(days=90),
                                     last_day - timedelta(days=1))
        m = METRICS[key]
        tiles.append({"key": key, "label": m.label, "value": latest["value"], "day": latest["day"],
                      "source": latest["source"], "decimals": m.decimals,
                      "change": latest["value"] - earlier[0]["value"] if earlier else None,
                      "since": earlier[0]["day"] if earlier else None, "good": m.good})
    if not tiles:
        return None
    by_key = {t["key"]: t for t in tiles}
    ratios = {}
    h = auswertung.height(db, pid)
    if "circ_waist" in by_key and h:
        value = by_key["circ_waist"]["value"] / h
        ratios["whtr"] = {"value": value, "category": bewertung.whtr_category(value), "height": h}
    if "circ_waist" in by_key and "circ_hip" in by_key:
        ratios["whr"] = {"value": by_key["circ_waist"]["value"] / by_key["circ_hip"]["value"]}
    series = [{"label": METRICS[k].label, "cls": cls,
               "points": store.daily_series(db, pid, k, start, today)}
              for k, cls in CHART_CIRCUMFERENCES]
    series = [s for s in series if s["points"]]
    chart = (charts.multi_line(series, start, today, "cm", 1, "Umfänge im Verlauf")
             if any(len(s["points"]) > 1 for s in series) else None)
    return {"tiles": tiles, "ratios": ratios, "chart": chart, "series": series}


def _practice_days(db, pid: int) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for r in db.execute("SELECT day, metric, value FROM measurements WHERE person_id = ? "
                        "AND source = 'praxis' ORDER BY measured_at", (pid,)):
        days.setdefault(r["day"], {})[r["metric"]] = r["value"]
    return days


def _home_value(db, pid: int, metric: str, day) -> tuple | None:
    """The home value (scale, any source but the practice) closest to a day, within 3 days."""
    day = util.to_date(day)
    order = [s for s in store.priority(db, METRICS[metric].family) if s != "praxis"]
    found = store.per_source(db, pid, metric, day - timedelta(days=3), day + timedelta(days=3))
    best = None
    for other, by_source in found.items():
        source = next((s for s in order if s in by_source), None)
        if not source:
            continue
        distance = abs((util.to_date(other) - day).days)
        if best is None or distance < best[0]:
            best = (distance, other, source, by_source[source])
    return best[1:] if best else None


def _home_series(db, pid: int, metric: str, start, end) -> list[dict]:
    """Daily home values (first source in the order, never the practice)."""
    order = [s for s in store.priority(db, METRICS[metric].family) if s != "praxis"]
    points = []
    for d, by_source in sorted(store.per_source(db, pid, metric, start, end).items()):
        source = next((s for s in order if s in by_source), None)
        if source:
            points.append({"day": d, "value": by_source[source]})
    return points


def practice(db, pid: int, today, columns: int = 6) -> dict | None:
    """The analyses at the practice side by side, and how the home scale compares."""
    days = _practice_days(db, pid)
    if not days:
        return None
    shown = sorted(days)[-columns:]
    rows = []
    for key in PRACTICE_METRICS:
        values = [days[d].get(key) for d in shown]
        if all(v is None for v in values):
            continue
        present = [v for v in values if v is not None]
        change = (round(present[-1] - present[-2], METRICS[key].decimals)
                  if len(present) >= 2 else None)
        rows.append({"key": key, "label": METRICS[key].label, "unit": METRICS[key].unit,
                     "decimals": METRICS[key].decimals, "values": values, "change": change,
                     "trend": bewertung.trend_class(change, METRICS[key].good) if change else "neutral"})
    last = days[shown[-1]]
    phase = last.get("phase_angle")
    comparisons = []
    first_day = util.to_date(sorted(days)[0])
    chart_start, chart_end = first_day - timedelta(days=30), util.to_date(today)
    for key in COMPARE:
        pairs = []
        for d in sorted(days):
            if key not in days[d]:
                continue
            home = _home_value(db, pid, key, d)
            if home:
                pairs.append({"day": d, "practice": days[d][key], "home": home[2],
                              "home_day": home[0], "source": home[1],
                              "diff": home[2] - days[d][key]})
        if not pairs:
            continue
        m = METRICS[key]
        item = {"key": key, "label": m.label, "unit": m.unit, "decimals": m.decimals,
                "pairs": pairs, "last": pairs[-1], "note": COMPARE_NOTES.get(key, ""),
                "mean": sum(p["diff"] for p in pairs) / len(pairs)}
        if len(pairs) >= 2:
            practice_change = pairs[-1]["practice"] - pairs[0]["practice"]
            home_change = pairs[-1]["home"] - pairs[0]["home"]
            small = 10 ** -m.decimals
            same = (abs(practice_change) < small and abs(home_change) < small) or \
                practice_change * home_change > 0
            item["trend"] = {"practice": practice_change, "home": home_change, "same": same,
                             "since": pairs[0]["day"]}
        item["chart"] = (lambda key=key, m=m: charts.multi_line(
            [s_ for s_ in (
                {"label": "Zu Hause", "cls": "p-jetzt",
                 "points": _home_series(db, pid, key, chart_start, chart_end)},
                {"label": "Praxis", "cls": "u-praxis",
                 "points": [{"day": d, "value": days[d][key]} for d in sorted(days) if key in days[d]]})
             if s_["points"]],
            chart_start, chart_end, m.unit, m.decimals, f"{m.label} zu Hause und in der Praxis"))
        comparisons.append(item)
    return {"days": shown, "rows": rows, "phase": phase,
            "phase_note": bewertung.phase_angle_note(phase) if phase else None,
            "comparisons": comparisons, "count": len(days)}
