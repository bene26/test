"""Quick answers for the start page ("Frag das Cockpit") and the Strg+K search.

There is no language model behind this: a question is matched against a few topics
by keywords and answered from the database. Anything else falls back to a search over
tasks, projects, meetings, people, firms and orders. Answers are plain text plus links;
the browser inserts them as text, never as HTML.
"""

import re
from datetime import timedelta

from flask import url_for

from . import data, quotas, schedule, util

MAX_QUERY = 200
MAX_LINKS = 6


def fold(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return text


def _like(words: list[str], columns: list[str]) -> tuple[str, list]:
    """Every word must appear in one of the columns."""
    clauses, params = [], []
    for word in words:
        pattern = "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        clauses.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in columns) + ")")
        params += [pattern] * len(columns)
    return " AND ".join(clauses), params


def _hit(title: str, group: str, hint: str, url: str) -> dict:
    return {"titel": title, "gruppe": group, "hinweis": hint, "url": url}


def _task_hint(row) -> str:
    parts = [util.TASK_STATUS.get(row["status"], row["status"])]
    if row["due_date"]:
        parts.append("fällig " + util.fmt_date(row["due_date"]))
    if row["project_code"] or row["project_name"]:
        parts.append(row["project_code"] or row["project_name"])
    return " · ".join(parts)


def search(db, query: str, limit: int = 12) -> list[dict]:
    words = [w for w in query[:100].split() if len(w) >= 2][:5]
    if not words:
        return []
    hits = []
    where, params = _like(words, ["name", "code", "client"])
    for r in db.execute(f"SELECT id, name, code, status FROM projects WHERE {where} "
                        "ORDER BY status = 'abgeschlossen', name LIMIT 4", params):
        hits.append(_hit(r["name"], "Projekt", " · ".join(x for x in (r["code"], r["status"]) if x),
                         url_for("projects.detail", project_id=r["id"])))
    where, params = _like(words, ["t.title", "t.description"])
    for r in db.execute(
            "SELECT t.id, t.title, t.status, t.due_date, p.code AS project_code, "
            "p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
            f"WHERE {where} ORDER BY t.status IN ('erledigt', 'abgenommen'), "
            "t.due_date IS NULL, t.due_date LIMIT 5", params):
        hits.append(_hit(r["title"], "Aufgabe", _task_hint(r), url_for("tasks.edit", task_id=r["id"])))
    where, params = _like(words, ["title", "type", "location", "participants"])
    for r in db.execute(f"SELECT * FROM meetings WHERE {where} ORDER BY starts_at DESC LIMIT 4",
                        params):
        hits.append(_hit(data.meeting_title(r), "Meeting", util.fmt_datetime(r["starts_at"]),
                         url_for("meetings.detail", meeting_id=r["id"])))
    where, params = _like(words, ["name", "role", "email"])
    for r in db.execute(f"SELECT id, name, role FROM people WHERE {where} "
                        "ORDER BY active DESC, name LIMIT 3", params):
        hits.append(_hit(r["name"], "Person", r["role"], url_for("team.person", person_id=r["id"])))
    where, params = _like(words, ["name", "contact_name"])
    for r in db.execute(f"SELECT id, name, contact_name FROM firms WHERE {where} "
                        "ORDER BY active DESC, name LIMIT 3", params):
        hits.append(_hit(r["name"], "Firma", r["contact_name"], url_for("team.firm", firm_id=r["id"])))
    where, params = _like(words, ["o.number", "o.title"])
    for r in db.execute("SELECT o.id, o.number, o.title, f.name AS firm_name FROM orders o "
                        f"JOIN firms f ON f.id = o.firm_id WHERE {where} "
                        "ORDER BY o.active DESC, o.id DESC LIMIT 3", params):
        title = " · ".join(x for x in (r["number"], r["title"]) if x)
        hits.append(_hit(title, "Bestellung", r["firm_name"], url_for("orders.detail", order_id=r["id"])))
    return hits[:limit]


# ---------- Answers ----------

def _link(text: str, url: str, info: str = "") -> dict:
    return {"text": text, "url": url, "info": info}


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _tasks(db, today, preset: str, limit: int = MAX_LINKS) -> list[dict]:
    return data.find_tasks(db, today, preset=preset, limit=limit)


def _task_links(tasks) -> list[dict]:
    return [_link(t["title"], url_for("tasks.edit", task_id=t["id"]),
                  " · ".join(x for x in (util.fmt_date(t["due_date"]) if t["due_date"] else "",
                                         t["assignee"]) if x))
            for t in tasks]


def _overdue(db, now):
    today = now.date()
    total = data.counts(db, now, 7)["overdue"]
    if not total:
        return ["Nichts ist überfällig. Alle offenen Aufgaben liegen im Plan."], []
    tasks = _tasks(db, today, "ueberfaellig")
    text = f"{_count(total, 'Aufgabe ist', 'Aufgaben sind')} überfällig."
    if total > len(tasks):
        text += f" Hier die {len(tasks)} ältesten:"
    links = _task_links(tasks) + [_link("Alle überfälligen Aufgaben", url_for("tasks.index", ansicht="ueberfaellig"))]
    return [text], links


def _today(db, now):
    today = now.date()
    tasks = _tasks(db, today, "heute")
    meetings = data.meetings_between(db, today, today)
    parts = []
    parts.append(f"Heute fällig: {_count(len(tasks), 'Aufgabe', 'Aufgaben')}." if tasks
                 else "Heute ist keine Aufgabe fällig.")
    if meetings:
        times = ", ".join(f"{util.to_datetime(m['starts_at']).strftime('%H:%M')} {data.meeting_title(m)}"
                          for m in meetings[:4])
        parts.append(f"{_count(len(meetings), 'Meeting', 'Meetings')} heute: {times}.")
    else:
        parts.append("Heute stehen keine Meetings an.")
    links = _task_links(tasks)[:4] + [_link(data.meeting_title(m), url_for("meetings.detail", meeting_id=m["id"]),
                                            util.fmt_datetime(m["starts_at"])) for m in meetings[:2]]
    return [" ".join(parts)], links


def _week(db, now):
    today = now.date()
    monday = util.week_start(today)
    sunday = monday + timedelta(days=6)
    counts = data.counts(db, now, 7)
    due = data.find_tasks(db, today, preset="woche")
    meetings = data.meetings_between(db, monday, sunday)
    plan = schedule.overview(db, today)
    milestones = [m for m in plan["upcoming"] if m["end"] <= sunday]
    lines = [f"Kalenderwoche {util.week_number(today)}, {util.fmt_date(monday)} bis {util.fmt_date(sunday)}."]
    summary = [
        f"{_count(len(due), 'Aufgabe ist', 'Aufgaben sind')} bis Sonntag fällig",
        f"{_count(len(meetings), 'Meeting steht', 'Meetings stehen')} im Kalender",
    ]
    if counts["overdue"]:
        summary.append(f"{_count(counts['overdue'], 'Aufgabe ist', 'Aufgaben sind')} schon überfällig")
    if counts["missing_protocols"]:
        summary.append(f"{_count(counts['missing_protocols'], 'Protokoll fehlt', 'Protokolle fehlen')} noch")
    lines.append(", ".join(summary) + ".")
    if milestones:
        lines.append("Meilensteine diese Woche: " + ", ".join(
            f"{m['title']} ({util.fmt_date(m['end'])})" for m in milestones[:3]) + ".")
    if plan["conflicts"]:
        lines.append(f"Im Zeitplan gibt es {_count(len(plan['conflicts']), 'Konflikt', 'Konflikte')}.")
    links = _task_links(due[:4]) + [_link("Woche ansehen", url_for("tasks.index", ansicht="woche"))]
    return lines, links


def _meetings(db, now):
    rows = db.execute(
        "SELECT m.*, p.name AS project_name, f.name AS firm_name FROM meetings m "
        "LEFT JOIN projects p ON p.id = m.project_id LEFT JOIN firms f ON f.id = m.firm_id "
        "WHERE m.starts_at >= ? ORDER BY m.starts_at LIMIT 5", (util.stamp(now),)).fetchall()
    if not rows:
        return ["Es sind keine kommenden Meetings eingetragen."], [
            _link("Meeting anlegen", url_for("meetings.index") + "#neu")]
    first = rows[0]
    text = f"Als Nächstes: {data.meeting_title(first)} am {util.fmt_datetime(first['starts_at'])}"
    if first["location"]:
        text += f", {first['location']}"
    text += "."
    if len(rows) > 1:
        text += f" Danach {_count(len(rows) - 1, 'weiteres', 'weitere')} in der Liste."
    links = [_link(data.meeting_title(m), url_for("meetings.detail", meeting_id=m["id"]),
                   util.fmt_datetime(m["starts_at"])) for m in rows]
    return [text], links


def _protocols(db, now):
    rows = data.missing_protocols(db, now)
    if not rows:
        return ["Alle Protokolle sind abgeschlossen."], []
    text = f"{_count(len(rows), 'Protokoll ist', 'Protokolle sind')} noch offen."
    links = [_link(data.meeting_title(m), url_for("meetings.detail", meeting_id=m["id"]),
                   util.fmt_datetime(m["starts_at"])) for m in rows[:MAX_LINKS]]
    return [text], links


def _quotas(db, now):
    firms = quotas.firm_summary(db, now.date())
    if not firms:
        return ["Es sind keine aktiven Bestellungen eingetragen."], [
            _link("Team & Firmen", url_for("team.index"))]
    warned = [f for f in firms if f["warnings"]]
    if warned:
        text = f"{_count(len(warned), 'Firma braucht', 'Firmen brauchen')} Aufmerksamkeit: " + "; ".join(
            f"{f['firm_name']} ({', '.join(f['warnings'][:2])})" for f in warned[:3]) + "."
    else:
        text = "Alle Kontingente sind im grünen Bereich."
    lines = [text, "Verplant / bestellt: " + ", ".join(
        f"{f['firm_name']} {f['percent_planned']:.0f} %" for f in firms[:4]) + "."]
    links = [_link(f["firm_name"], url_for("team.firm", firm_id=f["firm_id"]) + "#bestellungen",
                   f"{util.fmt_hours(f['free'])} frei") for f in (warned or firms)[:MAX_LINKS]]
    return lines, links


def _schedule(db, now):
    plan = schedule.overview(db, now.date())
    lines = []
    links = []
    if plan["conflicts"]:
        lines.append(f"{_count(len(plan['conflicts']), 'Konflikt', 'Konflikte')} im Zeitplan: " + "; ".join(
            f"„{c['succ']['title']}“ beginnt {c['days']} Tage zu früh nach „{c['pred']['title']}“"
            for c in plan["conflicts"][:3]) + ".")
        links += [_link(c["succ"]["title"], url_for("schedule.edit", item_id=c["succ"]["id"]),
                        f"frühestens {util.fmt_date(c['required'])}") for c in plan["conflicts"][:3]]
    else:
        lines.append("Im Zeitplan gibt es keine Konflikte.")
    if plan["missed"]:
        lines.append(f"{_count(len(plan['missed']), 'Meilenstein ist', 'Meilensteine sind')} verpasst.")
    if plan["upcoming"]:
        nxt = plan["upcoming"][0]
        lines.append(f"Nächster Meilenstein: {nxt['title']} am {util.fmt_date(nxt['end'])}"
                     + (f" ({nxt['project_label']})." if nxt.get("project_label") else "."))
        links.append(_link(nxt["title"], url_for("schedule.edit", item_id=nxt["id"]), util.fmt_date(nxt["end"])))
    links.append(_link("Zeitplan öffnen", url_for("schedule.index")))
    return lines, links[:MAX_LINKS]


def _workload(db, now):
    load = data.workload(db, now.date(), weeks=3)
    full = []
    for p in load["people"]:
        worst = max((c for c in p["cells"] if c["percent"] is not None),
                    key=lambda c: c["percent"], default=None)
        if worst and worst["percent"] > 100:
            week = load["weeks"][p["cells"].index(worst)]["label"]
            full.append((p, worst["percent"], week))
    if not full:
        return ["In den nächsten drei Wochen ist niemand überbucht."], [
            _link("Auslastung ansehen", url_for("workload.index"))]
    full.sort(key=lambda x: -x[1])
    text = f"{_count(len(full), 'Person ist', 'Personen sind')} überbucht: " + ", ".join(
        f"{p['name']} ({pct:.0f} % in {week})" for p, pct, week in full[:4]) + "."
    links = [_link(p["name"], url_for("team.person", person_id=p["id"]), f"{pct:.0f} % in {week}")
             for p, pct, week in full[:4]] + [_link("Auslastung ansehen", url_for("workload.index"))]
    return [text], links


def _hours(db, now):
    today = now.date()
    monday = util.week_start(today)
    row = db.execute(
        "SELECT COALESCE(SUM(hours), 0) AS total, COUNT(DISTINCT person_id) AS people "
        "FROM time_entries WHERE work_date BETWEEN ? AND ?",
        (monday.isoformat(), (monday + timedelta(days=6)).isoformat())).fetchone()
    if not row["total"]:
        return ["Für diese Woche sind noch keine Stunden erfasst."], [
            _link("Stunden erfassen", url_for("times.index"))]
    text = (f"Diese Woche sind {util.fmt_hours(row['total'])} erfasst, "
            f"von {_count(row['people'], 'Person', 'Personen')}.")
    return [text], [_link("Zeiten ansehen", url_for("times.index")),
                    _link("Team-Übersicht", url_for("times.team"))]


def _help(db, now):
    return [
        "Ich beantworte Fragen aus deinen Daten im Cockpit, ohne KI und ohne Internet.",
        "Frag zum Beispiel: Was ist überfällig? Was steht heute an? Fasse meine Woche zusammen. "
        "Wann ist das nächste Meeting? Welche Protokolle fehlen? Wie stehen die Kontingente? "
        "Gibt es Konflikte im Zeitplan? Wer ist überbucht? Wie viele Stunden sind erfasst? "
        "Alles andere suche ich in Aufgaben, Projekten, Meetings, Personen und Firmen.",
    ], []


TOPICS = [
    (r"hilfe|was kannst|wie funktioniert|was weisst", _help),
    (r"ueberfaellig|verspaet|verzug|zu spaet|ueber(m| dem) termin|liegen geblieben", _overdue),
    (r"protokoll", _protocols),
    (r"kontingent|bestellung|budget|abrechn|leistungsnachweis", _quotas),
    (r"konflikt|zeitplan|meilenstein|gantt|verschieb", _schedule),
    (r"auslastung|ueberbucht|ueberlast|kapazitaet|wer hat zeit|wer ist (voll|frei)", _workload),
    (r"stunden|zeiterfassung|erfasst|zeiten", _hours),
    (r"meeting|termin|besprechung|jour fixe|sitzung|kalender", _meetings),
    (r"heute|steht an", _today),
    (r"woche|zusammenfass|ueberblick|ueberblick|stand", _week),
]


def answer(db, now, question: str) -> dict:
    question = " ".join(question.split())[:MAX_QUERY]
    folded = fold(question)
    if not folded:
        texts, links = _help(db, now)
        return {"absaetze": texts, "links": links}
    for pattern, handler in TOPICS:
        if re.search(pattern, folded):
            texts, links = handler(db, now)
            return {"absaetze": texts, "links": links[:MAX_LINKS]}
    words = [w for w in re.findall(r"[\wäöüÄÖÜß-]{3,}", question)
             if fold(w) not in STOPWORDS]
    hits = search(db, " ".join(words[:4]), limit=MAX_LINKS) if words else []
    if not hits and len(words) > 1:
        for word in words:
            hits += search(db, word, limit=MAX_LINKS - len(hits))
            if len(hits) >= MAX_LINKS:
                break
    if hits:
        return {"absaetze": [f"Dazu habe ich {_count(len(hits), 'Treffer', 'Treffer')} gefunden:"],
                "links": [_link(h["titel"], h["url"], " · ".join(x for x in (h["gruppe"], h["hinweis"]) if x))
                          for h in hits]}
    return {"absaetze": [
        "Dazu habe ich nichts gefunden.",
        "Frag zum Beispiel: Was ist überfällig? Fasse meine Woche zusammen. Wie stehen die Kontingente?",
    ], "links": []}


STOPWORDS = {fold(w) for w in (
    "was", "wer", "wie", "wann", "wo", "ist", "sind", "gibt", "es", "der", "die", "das", "den",
    "dem", "ein", "eine", "einen", "und", "oder", "mit", "von", "zu", "zum", "zur", "fuer", "für",
    "mir", "mich", "meine", "meinen", "mein", "bitte", "zeig", "zeige", "suche", "finde", "habe",
    "hat", "haben", "noch", "schon", "auf", "bei", "aus", "nach", "über", "ueber", "alle", "aller",
    "welche", "welcher", "welches", "kannst", "du", "ich", "wir", "uns", "gerade", "aktuell",
)}
