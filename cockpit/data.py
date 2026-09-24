"""Queries shared by several views and the reminder scheduler."""

from collections import defaultdict
from datetime import date, timedelta

from . import util
from .meeting_types import label as meeting_label
from .util import OPEN_STATUSES, TASK_STATUS

OPEN_SQL = "('offen', 'in_arbeit', 'wartet')"

TASK_SELECT = """
SELECT t.*, p.name AS project_name, p.code AS project_code,
       pe.name AS person_name, pf.name AS person_firm_name, f.name AS firm_name
FROM tasks t
LEFT JOIN projects p ON p.id = t.project_id
LEFT JOIN people pe ON pe.id = t.person_id
LEFT JOIN firms pf ON pf.id = pe.firm_id
LEFT JOIN firms f ON f.id = t.firm_id
"""

TASK_ORDER = " ORDER BY (t.due_date IS NULL), t.due_date, t.priority, t.id"

# Utilisation thresholds in percent (see docs/konzept.md, section 6).
LEVELS = ((70, "frei"), (95, "ok"), (105, "voll"))

DEFAULT_SETTINGS = {
    "digest_time": "07:30",
    "weekly_planning_time": "08:45",
    "weekly_review_time": "13:45",
    "prep_time": "15:00",
    "monthly_time": "09:00",
    "stale_days": "7",
    "reminders_enabled": "1",
}

ROUTINES = {
    "wochenplanung": {
        "label": "Wochenplanung",
        "minutes": 15,
        "time_setting": "weekly_planning_time",
        "checklist": [
            "Überfällige Aufgaben durchgehen: neuer Termin, nachfragen oder abschließen",
            "Aufgaben ohne Update bei den Zuständigen nachfragen",
            "Auslastung prüfen und rote Werte auflösen",
            "Meetings der Woche ansehen, Agenden vorbereiten",
        ],
    },
    "wochenabschluss": {
        "label": "Wochenabschluss",
        "minutes": 10,
        "time_setting": "weekly_review_time",
        "checklist": [
            "Status der Aufgaben aktualisieren",
            "Fehlende Protokolle abschließen und versenden",
            "Fälligkeiten der nächsten Woche prüfen",
        ],
    },
    "monatsbericht": {
        "label": "Monatsbericht",
        "minutes": 30,
        "time_setting": "monthly_time",
        "checklist": [
            "Status je Projekt bewerten (Termine, Budget bzw. Kontingent, Qualität)",
            "Entscheidungen und Risiken für das Management sammeln",
            "Auslastung und Kontingente der Firmen prüfen",
        ],
    },
}


def settings(db) -> dict:
    values = dict(DEFAULT_SETTINGS)
    values.update({r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")})
    return values


def assignee_label(row) -> str:
    if row["person_name"]:
        if row["person_firm_name"]:
            return f"{row['person_name']} ({row['person_firm_name']})"
        return row["person_name"]
    return row["firm_name"] or ""


def task_dict(row, today: date) -> dict:
    task = dict(row)
    task["assignee"] = assignee_label(row)
    task["assignee_value"] = (f"p:{row['person_id']}" if row["person_id"]
                              else f"f:{row['firm_id']}" if row["firm_id"] else "")
    task["is_open"] = row["status"] in OPEN_STATUSES
    due = util.to_date(row["due_date"])
    task["overdue"] = bool(task["is_open"] and due and due < today)
    task["due_today"] = bool(task["is_open"] and due and due == today)
    task["status_label"] = TASK_STATUS[row["status"]]
    return task


def find_tasks(db, today: date, *, status="open", project=None, assignee=None,
               preset=None, query=None, stale_days=7, meeting_id=None, limit=None):
    where, params = [], []
    if preset:
        status = "open"
    if status == "open":
        where.append(f"t.status IN {OPEN_SQL}")
    elif status == "done":
        where.append("t.status IN ('erledigt', 'abgenommen')")
    elif status in TASK_STATUS:
        where.append("t.status = ?")
        params.append(status)
    if project == "none":
        where.append("t.project_id IS NULL")
    elif project:
        where.append("t.project_id = ?")
        params.append(int(project))
    if assignee == "none":
        where.append("t.person_id IS NULL AND t.firm_id IS NULL")
    elif assignee:
        person_id, firm_id = assignee
        if person_id:
            where.append("t.person_id = ?")
            params.append(person_id)
        else:
            where.append("(t.firm_id = ? OR pe.firm_id = ?)")
            params += [firm_id, firm_id]
    if meeting_id:
        where.append("t.meeting_id = ?")
        params.append(meeting_id)
    week_end = util.week_start(today) + timedelta(days=6)
    if preset == "ueberfaellig":
        where.append("t.due_date < ?")
        params.append(today.isoformat())
    elif preset == "heute":
        where.append("t.due_date = ?")
        params.append(today.isoformat())
    elif preset == "woche":
        where.append("t.due_date BETWEEN ? AND ?")
        params += [today.isoformat(), week_end.isoformat()]
    elif preset == "ohne_update":
        where.append("t.updated_at < ?")
        params.append(util.stamp(util.now() - timedelta(days=stale_days)))
    elif preset == "ohne_termin":
        where.append("t.due_date IS NULL")
    if query:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')")
        params += [pattern, pattern]
    sql = TASK_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += TASK_ORDER
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [task_dict(r, today) for r in db.execute(sql, params)]


def assignee_options(db, current: str = "") -> list[tuple[str, list[tuple[str, str]]]]:
    """Grouped options for an assignee <select>: internal people, ANÜ people, firms."""
    groups: dict[str, list] = defaultdict(list)
    people = db.execute(
        "SELECT pe.id, pe.name, pe.active, f.name AS firm_name FROM people pe "
        "LEFT JOIN firms f ON f.id = pe.firm_id ORDER BY f.name IS NOT NULL, f.name, pe.name"
    ).fetchall()
    for p in people:
        value = f"p:{p['id']}"
        if not p["active"] and value != current:
            continue
        group = "Intern" if not p["firm_name"] else f"{p['firm_name']} (Arbeitnehmerüberlassung)"
        groups[group].append((value, p["name"]))
    for f in db.execute("SELECT id, name, active FROM firms ORDER BY name"):
        value = f"f:{f['id']}"
        if f["active"] or value == current:
            groups["Firmen"].append((value, f["name"]))
    return list(groups.items())


def project_options(db, current=None) -> list[tuple[int, str]]:
    rows = db.execute(
        "SELECT id, name, code, status FROM projects ORDER BY status = 'abgeschlossen', name"
    ).fetchall()
    return [(r["id"], f"{r['code']} · {r['name']}" if r["code"] else r["name"])
            for r in rows if r["status"] != "abgeschlossen" or r["id"] == current]


def level(percent: float | None) -> str:
    if percent is None:
        return ""
    for limit, name in LEVELS:
        if percent < limit or (name == "voll" and percent <= limit):
            return name
    return "ueber"


def workload(db, today: date, weeks: int = 6) -> dict:
    """Planned hours per assignee and week, derived from open tasks.

    A task's effort is spread evenly over the weeks from its start (or the
    current week) to its due date. Overdue effort lands in the current week.
    """
    first = util.week_start(today)
    starts = [first + timedelta(weeks=i) for i in range(weeks)]
    load: dict[str, list[float]] = defaultdict(lambda: [0.0] * weeks)
    stats: dict[str, dict] = defaultdict(lambda: {"open": 0, "overdue": 0, "effort": 0.0,
                                                   "unplanned": 0})
    rows = db.execute(
        "SELECT t.person_id, t.firm_id, t.effort_hours, t.start_date, t.due_date "
        f"FROM tasks t WHERE t.status IN {OPEN_SQL} "
        "AND (t.person_id IS NOT NULL OR t.firm_id IS NOT NULL)"
    ).fetchall()
    for r in rows:
        key = f"p:{r['person_id']}" if r["person_id"] else f"f:{r['firm_id']}"
        due = util.to_date(r["due_date"])
        s = stats[key]
        s["open"] += 1
        if due and due < today:
            s["overdue"] += 1
        if not r["effort_hours"] or not due:
            s["unplanned"] += 1
            continue
        s["effort"] += r["effort_hours"]
        due_week = util.week_start(due)
        if due_week < first:
            spread = [first]
        else:
            begin = max(util.week_start(util.to_date(r["start_date"]) or today), first)
            begin = min(begin, due_week)
            count = (due_week - begin).days // 7 + 1
            spread = [begin + timedelta(weeks=i) for i in range(count)]
        share = r["effort_hours"] / len(spread)
        for ws in spread:
            index = (ws - first).days // 7
            if 0 <= index < weeks:
                load[key][index] += share

    people = []
    for p in db.execute(
        "SELECT pe.*, f.name AS firm_name FROM people pe LEFT JOIN firms f ON f.id = pe.firm_id "
        "WHERE pe.active = 1 ORDER BY f.name IS NOT NULL, f.name, pe.name"
    ):
        key = f"p:{p['id']}"
        capacity = p["weekly_hours"] * p["availability"]
        cells = []
        for hours in load[key]:
            percent = hours / capacity * 100 if capacity else None
            cells.append({"hours": hours, "percent": percent, "level": level(percent)})
        people.append({"id": p["id"], "name": p["name"], "role": p["role"],
                       "firm_name": p["firm_name"], "capacity": capacity,
                       "weekly_hours": p["weekly_hours"], "cells": cells, **stats[key]})
    firms = []
    for f in db.execute("SELECT * FROM firms WHERE active = 1 ORDER BY name"):
        key = f"f:{f['id']}"
        cells = [{"hours": h, "percent": None, "level": ""} for h in load[key]]
        firms.append({"id": f["id"], "name": f["name"], "contract_type": f["contract_type"],
                      "cells": cells, **stats[key]})
    return {
        "weeks": [{"start": ws, "label": f"KW {util.week_number(ws)}"} for ws in starts],
        "people": people,
        "firms": firms,
    }


def missing_protocols(db, now) -> list:
    return db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.protocol_status = 'offen' "
        "AND datetime(m.starts_at, '+' || m.duration_min || ' minutes') < ? "
        "ORDER BY m.starts_at",
        (util.stamp(now),),
    ).fetchall()


def meetings_between(db, start: date, end: date) -> list:
    """Meetings starting on days start..end (inclusive)."""
    return db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.starts_at >= ? AND m.starts_at < ? ORDER BY m.starts_at",
        (start.isoformat(), (end + timedelta(days=1)).isoformat()),
    ).fetchall()


def due_routines(db, today: date) -> list[dict]:
    candidates = []
    if today.weekday() in (0, 1, 2):
        candidates.append(("wochenplanung", util.week_key(today)))
    if today.weekday() == 4:
        candidates.append(("wochenabschluss", util.week_key(today)))
    if util.is_workday(today):
        if today >= util.last_workday_of_month(today):
            candidates.append(("monatsbericht", today.strftime("%Y-%m")))
        else:
            first = today.replace(day=1)
            workdays = sum(1 for i in range((today - first).days + 1)
                           if util.is_workday(first + timedelta(days=i)))
            if workdays <= 3:
                previous = first - timedelta(days=1)
                candidates.append(("monatsbericht", previous.strftime("%Y-%m")))
    done = {(r["routine"], r["period"]) for r in db.execute("SELECT routine, period FROM routine_checks")}
    return [{"key": key, "period": period, **ROUTINES[key]}
            for key, period in candidates if (key, period) not in done]


def counts(db, now, stale_days: int) -> dict:
    today = now.date()
    open_filter = f"status IN {OPEN_SQL}"
    one = lambda sql, *args: db.execute(sql, args).fetchone()[0]  # noqa: E731
    return {
        "overdue": one(f"SELECT COUNT(*) FROM tasks WHERE {open_filter} AND due_date < ?",
                       today.isoformat()),
        "due_today": one(f"SELECT COUNT(*) FROM tasks WHERE {open_filter} AND due_date = ?",
                         today.isoformat()),
        "stale": one(f"SELECT COUNT(*) FROM tasks WHERE {open_filter} AND updated_at < ?",
                     util.stamp(now - timedelta(days=stale_days))),
        "no_due": one(f"SELECT COUNT(*) FROM tasks WHERE {open_filter} AND due_date IS NULL"),
        "missing_protocols": len(missing_protocols(db, now)),
        "meetings_today": len(meetings_between(db, today, today)),
    }


def meeting_title(row) -> str:
    return row["title"] or meeting_label(row["type"])


def auto_table(db, meeting, kind: str, today: date) -> dict:
    """Live data for an agenda item; also stored in the protocol snapshot."""
    task_columns = ["Nr.", "Aufgabe", "Projekt", "Zuständig", "Fällig", "Status"]

    def task_rows(tasks):
        rows = []
        for t in tasks:
            due = util.fmt_date(t["due_date"])
            if t["overdue"]:
                due += " · überfällig"
            rows.append([f"#{t['id']}", t["title"], t["project_name"] or "",
                         t["assignee"], due, t["status_label"]])
        return rows

    if kind == "open_actions":
        tasks = [task_dict(r, today) for r in db.execute(
            TASK_SELECT + f" WHERE t.status IN {OPEN_SQL} AND t.meeting_id IN ("
            "SELECT id FROM meetings WHERE type = ? AND project_id IS ? AND firm_id IS ? "
            "AND id != ? AND starts_at <= ?)" + TASK_ORDER,
            (meeting["type"], meeting["project_id"], meeting["firm_id"], meeting["id"],
             meeting["starts_at"]),
        )]
        return {"columns": task_columns, "rows": task_rows(tasks),
                "task_ids": [t["id"] for t in tasks], "empty": "Keine offenen Maßnahmen."}

    if kind in ("firm_tasks", "due_tasks"):
        where, params = [f"t.status IN {OPEN_SQL}"], []
        if kind == "firm_tasks" and meeting["firm_id"]:
            where.append("(t.firm_id = ? OR pe.firm_id = ?)")
            params += [meeting["firm_id"], meeting["firm_id"]]
        if kind == "due_tasks":
            week_end = util.week_start(today) + timedelta(days=6)
            where.append("t.due_date <= ?")
            params.append(week_end.isoformat())
        if meeting["project_id"]:
            where.append("t.project_id = ?")
            params.append(meeting["project_id"])
        if kind == "firm_tasks" and not meeting["firm_id"] and not meeting["project_id"]:
            return {"columns": task_columns, "rows": [], "task_ids": [],
                    "empty": "Dem Meeting ist weder eine Firma noch ein Projekt zugeordnet."}
        tasks = [task_dict(r, today) for r in db.execute(
            TASK_SELECT + " WHERE " + " AND ".join(where) + TASK_ORDER, params)]
        return {"columns": task_columns, "rows": task_rows(tasks),
                "task_ids": [t["id"] for t in tasks], "empty": "Keine offenen Aufgaben."}

    if kind == "team_capacity":
        data = workload(db, today, weeks=2)
        columns = ["Person"] + [w["label"] for w in data["weeks"]]
        rows = []
        for p in data["people"]:
            cells = [f"{c['percent']:.0f} % ({util.fmt_hours(c['hours'])})"
                     if c["percent"] is not None else "" for c in p["cells"]]
            rows.append([p["name"]] + cells)
        return {"columns": columns, "rows": rows, "empty": "Keine Personen angelegt."}

    if kind == "project_status":
        rows = []
        since = (today - timedelta(days=30)).isoformat()
        for p in db.execute(
            "SELECT p.id, p.name, "
            f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {OPEN_SQL}), "
            f"(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN {OPEN_SQL} "
            " AND t.due_date < ?), "
            "(SELECT MIN(starts_at) FROM meetings m WHERE m.project_id = p.id AND m.starts_at >= ?), "
            "(SELECT COUNT(*) FROM decisions d WHERE d.project_id = p.id AND d.created_at >= ?) "
            "FROM projects p WHERE p.status = 'aktiv' ORDER BY p.priority, p.name",
            (today.isoformat(), today.isoformat(), since),
        ):
            rows.append([p[1], str(p[2]), str(p[3]), util.fmt_datetime(p[4]) if p[4] else "–",
                         str(p[5])])
        return {"columns": ["Projekt", "Offen", "Überfällig", "Nächstes Meeting",
                            "Entscheidungen (30 Tage)"],
                "rows": rows, "empty": "Keine aktiven Projekte."}

    return {"columns": [], "rows": [], "empty": ""}
