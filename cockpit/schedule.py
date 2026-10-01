"""Project timeline: phases, milestones and finish-to-start dependencies.

A successor of a phase may start the day after the phase ends, a successor of
a milestone on the milestone's day (plus the link's lag). A link whose
successor starts earlier is a conflict. Resolving a conflict moves the
successor (keeping its duration) and, in turn, everything that depends on it.
"""

from collections import defaultdict, deque
from datetime import date, timedelta

from . import util

ITEM_SELECT = """
SELECT s.*, p.name AS project_name, p.code AS project_code, p.status AS project_status,
       pe.name AS person_name, f.name AS firm_name
FROM schedule_items s
JOIN projects p ON p.id = s.project_id
LEFT JOIN people pe ON pe.id = s.person_id
LEFT JOIN firms f ON f.id = s.firm_id
"""
ITEM_ORDER = " ORDER BY p.priority, p.name, s.project_id, s.start_date, s.kind DESC, s.id"


def _item(row) -> dict:
    item = dict(row)
    item["start"] = util.to_date(row["start_date"])
    item["end"] = util.to_date(row["end_date"])
    item["days"] = (item["end"] - item["start"]).days + 1
    item["assignee"] = row["person_name"] or row["firm_name"] or ""
    item["assignee_value"] = (f"p:{row['person_id']}" if row["person_id"]
                              else f"f:{row['firm_id']}" if row["firm_id"] else "")
    item["project_label"] = row["project_code"] or row["project_name"]
    return item


def items(db, project_id=None, active_only=False) -> list[dict]:
    where, params = [], []
    if project_id:
        where.append("s.project_id = ?")
        params.append(project_id)
    if active_only:
        where.append("p.status IN ('aktiv', 'geplant')")
    sql = ITEM_SELECT + (" WHERE " + " AND ".join(where) if where else "") + ITEM_ORDER
    return [_item(r) for r in db.execute(sql, params)]


def item(db, item_id) -> dict | None:
    row = db.execute(ITEM_SELECT + " WHERE s.id = ?", (item_id,)).fetchone()
    return _item(row) if row else None


def all_links(db) -> list[dict]:
    return [dict(r) for r in db.execute("SELECT * FROM schedule_links ORDER BY id")]


def required_start(pred: dict, lag_days: int) -> date:
    base = pred["end"] + timedelta(days=1) if pred["kind"] == "phase" else pred["end"]
    return base + timedelta(days=lag_days)


def conflicts(by_id: dict, links: list[dict]) -> list[dict]:
    found = []
    for link in links:
        pred, succ = by_id.get(link["pred_id"]), by_id.get(link["succ_id"])
        if not pred or not succ:
            continue
        need = required_start(pred, link["lag_days"])
        if succ["start"] < need:
            found.append({"link": link, "pred": pred, "succ": succ, "required": need,
                          "days": (need - succ["start"]).days})
    return found


def would_cycle(db, pred_id: int, succ_id: int) -> bool:
    """True if pred already (indirectly) depends on succ."""
    nexts = defaultdict(list)
    for r in db.execute("SELECT pred_id, succ_id FROM schedule_links"):
        nexts[r["pred_id"]].append(r["succ_id"])
    seen, queue = set(), deque([succ_id])
    while queue:
        current = queue.popleft()
        if current == pred_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        queue.extend(nexts[current])
    return False


def _move(db, row: dict, days: int) -> None:
    start = row["start"] + timedelta(days=days)
    end = row["end"] + timedelta(days=days)
    db.execute("UPDATE schedule_items SET start_date = ?, end_date = ?, updated_at = ? "
               "WHERE id = ?", (start.isoformat(), end.isoformat(), util.stamp(), row["id"]))
    row["start"], row["end"] = start, end


def push_successors(db, item_id: int) -> list[dict]:
    """Move every (transitive) successor that now starts too early. Returns moved items."""
    by_id = {i["id"]: i for i in items(db)}
    links = all_links(db)
    nexts = defaultdict(list)
    for link in links:
        nexts[link["pred_id"]].append(link)
    moved = {}
    queue = deque([item_id])
    budget = (len(links) + 1) * (len(by_id) + 1)  # links are acyclic; this is only a guard
    while queue and budget > 0:
        budget -= 1
        pred = by_id.get(queue.popleft())
        if not pred:
            continue
        for link in nexts[pred["id"]]:
            succ = by_id.get(link["succ_id"])
            if not succ:
                continue
            need = required_start(pred, link["lag_days"])
            if succ["start"] < need:
                _move(db, succ, (need - succ["start"]).days)
                moved[succ["id"]] = succ
                queue.append(succ["id"])
    return list(moved.values())


def resolve(db, link_id: int) -> list[dict]:
    """Move the successor of one link so it starts in time, then its successors."""
    link = db.execute("SELECT * FROM schedule_links WHERE id = ?", (link_id,)).fetchone()
    if not link:
        return []
    pred, succ = item(db, link["pred_id"]), item(db, link["succ_id"])
    need = required_start(pred, link["lag_days"])
    if succ["start"] >= need:
        return []
    _move(db, succ, (need - succ["start"]).days)
    return [succ] + push_successors(db, succ["id"])


def project_progress(project_items: list[dict]) -> int | None:
    """Duration-weighted progress of the phases, or None without phases."""
    phases = [i for i in project_items if i["kind"] == "phase"]
    total = sum(i["days"] for i in phases)
    if not total:
        return None
    return round(sum(i["progress"] * i["days"] for i in phases) / total)


def overview(db, today: date, project_id=None) -> dict:
    """Items, links and conflicts for the dashboard, project pages and reports."""
    all_items = items(db)
    by_id = {i["id"]: i for i in all_items}
    links = all_links(db)
    found = conflicts(by_id, links)
    shown = [i for i in all_items if (i["project_id"] == project_id if project_id
                                      else i["project_status"] in ("aktiv", "geplant"))]
    shown_ids = {i["id"] for i in shown}
    milestones = [i for i in shown if i["kind"] == "milestone"]
    return {
        "items": shown,
        "by_id": by_id,
        "links": links,
        "conflicts": [c for c in found
                      if c["succ"]["id"] in shown_ids or c["pred"]["id"] in shown_ids],
        "upcoming": [m for m in milestones if m["progress"] < 100 and m["end"] >= today],
        "missed": [m for m in milestones if m["progress"] < 100 and m["end"] < today],
        "late_phases": [i for i in shown if i["kind"] == "phase" and i["progress"] < 100
                        and i["end"] < today],
    }


# ---------- Gantt layout (rendered as SVG, see templates/schedule/_gantt.html) ----------

LABEL_W = 300
ROW_H = 34
HEAD_H = 48
DAY_W = 6


def gantt(all_items: list[dict], links: list[dict], conflict_links: set, today: date,
          show_links: bool = True) -> dict | None:
    if not all_items:
        return None
    first = min([i["start"] for i in all_items] + [today])
    last = max([i["end"] for i in all_items] + [today])
    start = util.week_start(first) - timedelta(days=7)
    end = util.week_start(last) + timedelta(days=13)
    if (end - start).days > 7 * 156:  # at most three years wide
        end = start + timedelta(days=7 * 156)
    days = (end - start).days + 1

    def x(d: date) -> float:
        return LABEL_W + (d - start).days * DAY_W

    rows, positions = [], {}
    y = HEAD_H
    current_project = None
    for it in all_items:
        if it["project_id"] != current_project:
            current_project = it["project_id"]
            rows.append({"type": "project", "y": y, "label": it["project_name"],
                         "code": it["project_code"], "project_id": it["project_id"]})
            y += ROW_H
        mid = y + ROW_H / 2
        row = {"type": it["kind"], "y": y, "mid": mid, "item": it,
               "label": _short(it["title"], 34)}
        if it["kind"] == "phase":
            x1 = x(it["start"])
            width = max(it["days"] * DAY_W, 4)
            row.update(x1=x1, width=width, x2=x1 + width,
                       done_w=width * it["progress"] / 100,
                       late=it["progress"] < 100 and it["end"] < today)
        else:
            cx = x(it["start"]) + DAY_W / 2
            row.update(cx=cx, x1=cx, x2=cx, missed=it["progress"] < 100 and it["end"] < today,
                       diamond=f"{cx},{mid - 9} {cx + 9},{mid} {cx},{mid + 9} {cx - 9},{mid}")
        positions[it["id"]] = row
        rows.append(row)
        y += ROW_H
    height = y + 8

    arrows = []
    if show_links:
        for link in links:
            a, b = positions.get(link["pred_id"]), positions.get(link["succ_id"])
            if not a or not b:
                continue
            x1 = a["x2"] + (9 if a["type"] == "milestone" else 0)
            x2 = b["x1"] - (9 if b["type"] == "milestone" else 0)
            y1, y2 = a["mid"], b["mid"]
            if x2 - x1 >= 16:
                path = f"M{x1:.1f} {y1:.1f} H{x1 + 8:.1f} V{y2:.1f} H{x2 - 2:.1f}"
            else:  # successor starts too early: route around
                turn_y = y2 - ROW_H / 2 if y2 > y1 else y2 + ROW_H / 2
                path = (f"M{x1:.1f} {y1:.1f} H{x1 + 8:.1f} V{turn_y:.1f} "
                        f"H{x2 - 12:.1f} V{y2:.1f} H{x2 - 2:.1f}")
            arrows.append({"path": path, "conflict": link["id"] in conflict_links,
                           "cross": a["item"]["project_id"] != b["item"]["project_id"]})

    months, weeks = [], []
    d = start
    while d <= end:
        if d.weekday() == 0:
            weeks.append({"x": x(d), "label": util.week_number(d)})
        if d.day == 1 or d == start:
            months.append({"x": x(d), "label": f"{MONTHS[d.month - 1]} {d.year}"})
        d += timedelta(days=1)
    return {
        "width": LABEL_W + days * DAY_W, "height": height, "label_w": LABEL_W,
        "head_h": HEAD_H, "row_h": ROW_H, "rows": rows, "arrows": arrows,
        "months": months, "weeks": weeks, "week_w": 7 * DAY_W,
        "today_x": x(today) + DAY_W / 2 if start <= today <= end else None,
    }


MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
