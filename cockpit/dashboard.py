"""Start page building blocks (widgets) and the per-user layout.

The layout is stored as JSON in users.dashboard: a list of
{"k": key, "v": visible, "w": wide}. Unknown keys are dropped, widgets added
in a later version are appended with their defaults.
"""

import json
from datetime import date, timedelta

from . import data, quotas, schedule, util

# key: (label, description, visible by default, wide by default)
WIDGETS = {
    "kennzahlen": ("Kennzahlen", "Überfällig, heute fällig, ohne Update, Protokolle, ohne Termin",
                   True, True),
    "routinen": ("Routinen", "Wochenplanung, Wochenabschluss und Monatsbericht, wenn fällig",
                 True, True),
    "schnellerfassung": ("Schnellerfassung", "Neue Aufgabe in einer Zeile anlegen", True, True),
    "naechstes_meeting": ("Nächstes Meeting", "Das nächste Meeting groß mit Countdown",
                          True, False),
    "ueberfaellig": ("Überfällig", "Überfällige Aufgaben", True, False),
    "meetings": ("Meetings", "Meetings heute und am nächsten Arbeitstag", True, False),
    "woche": ("Diese Woche", "Aufgaben, die bis Sonntag fällig sind", True, False),
    "protokolle": ("Protokoll fehlt", "Meetings ohne abgeschlossenes Protokoll", True, False),
    "projekte": ("Projekte", "Fortschritt, nächster Meilenstein und Konflikte je Projekt",
                 True, False),
    "kalender": ("Kalender", "Monat mit Meetings, Fristen und Meilensteinen", True, False),
    "meilensteine": ("Zeitplan", "Konflikte, verpasste und nächste Meilensteine", True, False),
    "kontingente": ("Kontingente", "Bestellungen der Firmen: verplant, abgerechnet, Warnungen",
                    True, False),
    "auslastung": ("Auslastung", "Wer in den nächsten zwei Wochen überbucht ist", True, False),
    "zeiten": ("Zeiten", "Erfasste Projektstunden dieser Woche und offene Nachweise",
               False, False),
}


def default_layout() -> list[dict]:
    return [{"k": k, "v": w[2], "w": w[3]} for k, w in WIDGETS.items()]


def load(raw: str) -> list[dict]:
    try:
        stored = json.loads(raw) if raw else []
    except ValueError:
        stored = []
    layout, seen = [], set()
    if isinstance(stored, list):
        for entry in stored:
            if not isinstance(entry, dict):
                continue
            key = entry.get("k")
            if key in WIDGETS and key not in seen:
                seen.add(key)
                layout.append({"k": key, "v": bool(entry.get("v")), "w": bool(entry.get("w"))})
    if not layout:
        return default_layout()
    for entry in default_layout():
        if entry["k"] not in seen:
            layout.append(entry)
    return layout


def dump(layout: list[dict]) -> str:
    return json.dumps([{"k": e["k"], "v": e["v"], "w": e["w"]} for e in layout],
                      separators=(",", ":"))


def apply_form(order: list[str], shown: set, wide: set, move: str = "") -> list[dict]:
    """Build a layout from the edit form; `move` is 'key:up' or 'key:down'."""
    keys = [k for k in dict.fromkeys(order) if k in WIDGETS]
    keys += [k for k in WIDGETS if k not in keys]
    if move and ":" in move:
        key, direction = move.split(":", 1)
        if key in keys:
            i = keys.index(key)
            j = i - 1 if direction == "up" else i + 1 if direction == "down" else i
            if 0 <= j < len(keys):
                keys[i], keys[j] = keys[j], keys[i]
    return [{"k": k, "v": k in shown, "w": k in wide} for k in keys]


# ---------- Data for each widget. Only visible widgets are loaded. ----------

def _calendar(db, today: date, month: str | None) -> dict:
    first = today.replace(day=1)
    if month and len(month) == 7 and month[4] == "-" and month.replace("-", "").isdigit():
        y, m = int(month[:4]), int(month[5:])
        if 2000 <= y <= 2100 and 1 <= m <= 12:
            first = date(y, m, 1)
    last = date(first.year + (first.month == 12), first.month % 12 + 1, 1) - timedelta(days=1)
    start = util.week_start(first)
    end = util.week_start(last) + timedelta(days=6)
    events: dict[str, list] = {}

    def add(day, kind, text):
        events.setdefault(day, []).append({"kind": kind, "text": text})

    for m in data.meetings_between(db, start, end):
        add(m["starts_at"][:10], "meeting", f"{m['starts_at'][11:16]} {m['title']}")
    for t in db.execute(f"SELECT title, due_date FROM tasks WHERE status IN {data.OPEN_SQL} "
                        "AND due_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat())):
        add(t["due_date"], "due", f"fällig: {t['title']}")
    for s in db.execute("SELECT s.title, s.start_date, p.code, p.name FROM schedule_items s "
                        "JOIN projects p ON p.id = s.project_id WHERE s.kind = 'milestone' "
                        "AND s.start_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat())):
        add(s["start_date"], "milestone", f"◆ {s['title']} ({s['code'] or s['name']})")
    weeks, d = [], start
    while d <= end:
        week = []
        for _ in range(7):
            items = events.get(d.isoformat(), [])
            week.append({"date": d, "in_month": d.month == first.month, "today": d == today,
                         "kinds": sorted({e["kind"] for e in items}),
                         "title": "\n".join(e["text"] for e in items)})
            d += timedelta(days=1)
        weeks.append(week)
    # The list below the grid always shows the next 14 days, whatever month is displayed.
    horizon = today + timedelta(days=14)
    upcoming = [{"date": util.to_date(m["starts_at"]), "kind": "meeting",
                 "text": f"{m['starts_at'][11:16]} {m['title']}"}
                for m in data.meetings_between(db, today, horizon)]
    upcoming += [{"date": util.to_date(s["start_date"]), "kind": "milestone",
                  "text": f"◆ {s['title']}"}
                 for s in db.execute("SELECT title, start_date FROM schedule_items "
                                     "WHERE kind = 'milestone' AND progress < 100 "
                                     "AND start_date BETWEEN ? AND ?",
                                     (today.isoformat(), horizon.isoformat()))]
    upcoming.sort(key=lambda e: e["date"])
    prev_month = (first - timedelta(days=1)).strftime("%Y-%m")
    next_month = (last + timedelta(days=1)).strftime("%Y-%m")
    return {"first": first, "weeks": weeks, "upcoming": upcoming[:6],
            "prev": prev_month, "next": next_month, "label": f"{MONTHS[first.month - 1]} {first.year}"}


MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]


def _countdown(now, starts) -> str:
    delta = starts - now
    minutes = int(delta.total_seconds() // 60)
    if minutes < 0:
        return "läuft"
    if minutes < 60:
        return f"in {minutes} min"
    if starts.date() == now.date():
        return f"in {minutes // 60} h {minutes % 60:02d} min"
    if starts.date() == now.date() + timedelta(days=1):
        return "morgen"
    return f"in {(starts.date() - now.date()).days} Tagen"


def context(db, now, layout: list[dict], args, editing: bool = False) -> dict:
    """Template data for every widget that is shown."""
    today = now.date()
    wanted = {e["k"] for e in layout if e["v"] or editing}
    settings = data.settings(db)
    stale_days = int(settings["stale_days"])
    ctx = {"now": now, "today": today, "week": util.week_number(today),
           "stale_days": stale_days}
    if "kennzahlen" in wanted:
        ctx["counts"] = data.counts(db, now, stale_days)
    if "routinen" in wanted:
        ctx["routines"] = data.due_routines(db, today)
    if "schnellerfassung" in wanted:
        ctx["assignees"] = data.assignee_options(db)
        ctx["projects"] = data.project_options(db)
    if "ueberfaellig" in wanted:
        ctx["overdue"] = data.find_tasks(db, today, preset="ueberfaellig", limit=12)
        ctx["overdue_total"] = len(data.find_tasks(db, today, preset="ueberfaellig"))
    if "woche" in wanted:
        ctx["due_week"] = data.find_tasks(db, today, preset="woche", limit=12)
        ctx["week_end"] = util.week_start(today) + timedelta(days=6)
    if "meetings" in wanted:
        next_day = util.next_workday(today)
        ctx["meetings_today"] = data.meetings_between(db, today, today)
        ctx["meetings_next"] = data.meetings_between(db, today + timedelta(days=1), next_day)
        ctx["next_day"] = next_day
    if "protokolle" in wanted:
        ctx["missing"] = data.missing_protocols(db, now)
    if "naechstes_meeting" in wanted:
        row = db.execute(
            "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
            "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
            "WHERE datetime(m.starts_at, '+' || m.duration_min || ' minutes') > ? "
            "ORDER BY m.starts_at LIMIT 1", (util.stamp(now),)).fetchone()
        ctx["next_meeting"] = row
        if row:
            starts = util.to_datetime(row["starts_at"])
            ctx["next_meeting_in"] = _countdown(now, starts)
            ctx["next_meeting_actions"] = db.execute(
                f"SELECT COUNT(*) FROM tasks WHERE status IN {data.OPEN_SQL} AND meeting_id IN "
                "(SELECT id FROM meetings WHERE type = ? AND project_id IS ? AND firm_id IS ? "
                "AND id != ?)", (row["type"], row["project_id"], row["firm_id"], row["id"])
            ).fetchone()[0]
    if {"projekte", "meilensteine"} & wanted:
        ov = schedule.overview(db, today)
        ctx["schedule"] = ov
        ctx["milestones_soon"] = [m for m in ov["upcoming"]
                                  if m["end"] <= today + timedelta(days=42)][:6]
    if "projekte" in wanted:
        rows = []
        all_items = ctx["schedule"]["items"]
        conflict_projects = {}
        for c in ctx["schedule"]["conflicts"]:
            pid = c["succ"]["project_id"]
            conflict_projects[pid] = conflict_projects.get(pid, 0) + 1
        for p in db.execute(
                "SELECT p.*, "
                f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {data.OPEN_SQL}) AS open_tasks, "
                "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS all_tasks, "
                f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {data.OPEN_SQL} "
                " AND t.due_date < ?) AS overdue "
                "FROM projects p WHERE p.status IN ('aktiv', 'geplant') ORDER BY p.priority, p.name",
                (today.isoformat(),)):
            own = [i for i in all_items if i["project_id"] == p["id"]]
            progress = schedule.project_progress(own)
            source = "Zeitplan"
            if progress is None and p["all_tasks"]:
                progress = round((p["all_tasks"] - p["open_tasks"]) / p["all_tasks"] * 100)
                source = "Aufgaben"
            next_ms = next((i for i in own if i["kind"] == "milestone" and i["progress"] < 100
                            and i["end"] >= today), None)
            rows.append({"project": p, "progress": progress, "source": source,
                         "next": next_ms, "conflicts": conflict_projects.get(p["id"], 0),
                         "overdue": p["overdue"], "open": p["open_tasks"]})
        ctx["project_rows"] = rows
    if "kalender" in wanted:
        ctx["cal"] = _calendar(db, today, args.get("kal"))
    if "kontingente" in wanted:
        ctx["quota_rows"] = quotas.firm_summary(db, today)
    if "auslastung" in wanted:
        wl = data.workload(db, today, weeks=2)
        ctx["workload"] = wl
        ctx["overbooked"] = [
            {"name": p["name"], "week": w["label"], "percent": c["percent"]}
            for p in wl["people"] for w, c in zip(wl["weeks"], p["cells"]) if c["level"] == "ueber"]
    if "zeiten" in wanted:
        monday = util.week_start(today)
        rows = db.execute(
            "SELECT p.id, p.name, p.code, SUM(t.hours) AS hours FROM time_entries t "
            "JOIN projects p ON p.id = t.project_id WHERE t.work_date BETWEEN ? AND ? "
            "GROUP BY p.id ORDER BY hours DESC",
            (monday.isoformat(), (monday + timedelta(days=6)).isoformat())).fetchall()
        ctx["hours_week"] = rows
        ctx["hours_week_total"] = sum(r["hours"] for r in rows)
        ctx["records_pending"] = db.execute(
            "SELECT COUNT(*) FROM service_records WHERE status = 'eingereicht'").fetchone()[0]
    return ctx
