"""Monthly project status report: traffic lights, milestones, tasks, hours, quotas."""

from datetime import date, timedelta

from . import data, quotas, schedule, util

MONTH_NAMES = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
               "September", "Oktober", "November", "Dezember"]
LIGHTS = {"gruen": "im Plan", "gelb": "beobachten", "rot": "handeln", "grau": "keine Daten"}
_RANK = {"grau": 0, "gruen": 1, "gelb": 2, "rot": 3}


def month_label(first: date) -> str:
    return f"{MONTH_NAMES[first.month - 1]} {first.year}"


def _worst(*lights) -> str:
    return max(lights, key=lambda x: _RANK[x])


def project_status(db, project, today: date, first: date, last: date) -> dict:
    pid = project["id"]
    ov = schedule.overview(db, today, pid)
    since, until = first.isoformat(), last.isoformat()
    in_month = lambda d: first <= d <= last  # noqa: E731
    open_tasks = data.find_tasks(db, today, project=str(pid))
    overdue = [t for t in open_tasks if t["overdue"]]
    done = db.execute(
        "SELECT id, title, done_at FROM tasks WHERE project_id = ? AND done_at >= ? AND done_at < ? "
        "ORDER BY done_at", (pid, since, (last + timedelta(days=1)).isoformat())).fetchall()
    decisions = db.execute(
        "SELECT d.number, d.text FROM decisions d WHERE d.project_id = ? AND d.created_at >= ? "
        "AND d.created_at < ? ORDER BY d.number",
        (pid, since, (last + timedelta(days=1)).isoformat())).fetchall()
    meetings = db.execute(
        "SELECT id, title, starts_at, protocol_status, version FROM meetings WHERE project_id = ? "
        "AND starts_at >= ? AND starts_at < ? ORDER BY starts_at",
        (pid, since, (last + timedelta(days=1)).isoformat())).fetchall()
    orders = quotas.orders(db, today, project_id=pid, active_only=True)
    milestones = [i for i in ov["items"] if i["kind"] == "milestone"]

    dates_light = "gruen"
    if ov["conflicts"] or ov["missed"]:
        dates_light = "rot"
    elif ov["late_phases"] or overdue:
        dates_light = "gelb"
    if not ov["items"] and not open_tasks:
        dates_light = "grau"
    quota_light = "grau"
    if orders:
        quota_light = "gruen"
        if any(o["level"] == "ueber" or any("abgelaufen" in w for w in o["warnings"])
               for o in orders):
            quota_light = "rot"
        elif any(o["warnings"] for o in orders):
            quota_light = "gelb"
    task_light = "gruen" if open_tasks or done else "grau"
    if overdue:
        task_light = "rot" if len(overdue) >= 3 and len(overdue) * 4 > len(open_tasks) else "gelb"

    return {
        "project": project,
        "lights": {"Termine": dates_light, "Kontingent": quota_light, "Aufgaben": task_light},
        "overall": _worst(dates_light, quota_light, task_light),
        "progress": schedule.project_progress(ov["items"]),
        "reached": [m for m in milestones if m["progress"] == 100 and in_month(m["start"])],
        "upcoming": ov["upcoming"][:4],
        "missed": ov["missed"],
        "late_phases": ov["late_phases"],
        "conflicts": ov["conflicts"],
        "open": len(open_tasks),
        "overdue": overdue[:10],
        "overdue_count": len(overdue),
        "done": done,
        "decisions": decisions,
        "meetings": meetings,
        "hours_month": data.project_hours(db, pid, since, until),
        "hours_total": data.project_hours(db, pid),
        "orders": orders,
    }


def build(db, today: date, first: date, last: date, project_id=None) -> list[dict]:
    if project_id:
        projects = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchall()
    else:
        projects = db.execute("SELECT * FROM projects WHERE status IN ('aktiv', 'geplant') "
                              "ORDER BY priority, name").fetchall()
    return [project_status(db, p, today, first, last) for p in projects]


def as_text(reports: list[dict], first: date) -> str:
    """Plain-text version for e-mail."""
    h = util.fmt_hours
    lines = [f"Projektstatus {month_label(first)}", f"Stand {util.fmt_date(util.today())}", ""]
    for r in reports:
        p = r["project"]
        lines.append(("== " + (f"{p['code']} · " if p["code"] else "") + p["name"] + " =="))
        lines.append("Ampel: " + ", ".join(f"{k} {LIGHTS[v]}" for k, v in r["lights"].items()))
        if r["progress"] is not None:
            lines.append(f"Fortschritt Zeitplan: {r['progress']} %")
        for m in r["reached"]:
            lines.append(f"Erreicht: {m['title']} ({util.fmt_date(m['start'])})")
        for m in r["upcoming"]:
            lines.append(f"Nächster Meilenstein: {m['title']} ({util.fmt_date(m['start'])})")
        for m in r["missed"]:
            lines.append(f"Verpasst: {m['title']} ({util.fmt_date(m['start'])})")
        for c in r["conflicts"]:
            lines.append(f"Konflikt: {c['succ']['title']} beginnt vor Ende von {c['pred']['title']}")
        lines.append(f"Aufgaben: {r['open']} offen, {r['overdue_count']} überfällig, "
                     f"{len(r['done'])} im Monat erledigt")
        for d in r["decisions"]:
            lines.append(f"Entscheidung E-{d['number']:02d}: {d['text']}")
        hm, ht = r["hours_month"], r["hours_total"]
        lines.append(f"Stunden im Monat: {h(hm['actual']) or '0 h'}; gesamt Ist {h(ht['actual']) or '0 h'}"
                     f" von {h(ht['plan']) or '0 h'} Plan")
        for o in r["orders"]:
            lines.append(f"Bestellung {o['firm_name']} {o['label']}: "
                         f"{quotas.fmt_amount(o['billed'], o['unit'])} von "
                         f"{quotas.fmt_amount(o['amount'], o['unit'])}"
                         + (f" ({'; '.join(o['warnings'])})" if o["warnings"] else ""))
        lines.append("")
    return "\n".join(lines)
