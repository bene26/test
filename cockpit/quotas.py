"""Quotas of external firms: orders (Bestellungen) and service records.

Consumption is tracked per order, never per external person (AÜG). "Planned"
is the effort of the tasks given to the firm, "billed" the checked service
records. Warnings: 80 % used or planned, over budget, expiring within four weeks.
"""

from datetime import date

from . import util

UNITS = {"h": "Stunden", "pt": "Personentage"}
UNIT_SHORT = {"h": "h", "pt": "PT"}
RECORD_STATUS = {"eingereicht": "Eingereicht", "geprueft": "Geprüft", "abgelehnt": "Abgelehnt"}
WARN_PERCENT = 80
EXPIRY_DAYS = 28


def fmt_amount(value, unit: str) -> str:
    value = round(float(value or 0), 2)
    text = f"{value:.0f}" if value == int(value) else f"{value:.2f}".rstrip("0").replace(".", ",")
    return f"{text} {UNIT_SHORT.get(unit, unit)}"


def _level(percent: float) -> str:
    if percent > 100:
        return "ueber"
    if percent >= WARN_PERCENT:
        return "voll"
    return "ok"


def orders(db, today: date, firm_id=None, project_id=None, active_only=False) -> list[dict]:
    where, params = [], []
    if firm_id:
        where.append("o.firm_id = ?")
        params.append(firm_id)
    if project_id:
        where.append("o.project_id = ?")
        params.append(project_id)
    if active_only:
        where.append("o.active = 1")
    rows = db.execute(
        "SELECT o.*, f.name AS firm_name, p.name AS project_name, p.code AS project_code, "
        "(SELECT COALESCE(SUM(amount), 0) FROM service_records r "
        " WHERE r.order_id = o.id AND r.status = 'geprueft') AS billed, "
        "(SELECT COALESCE(SUM(amount), 0) FROM service_records r "
        " WHERE r.order_id = o.id AND r.status = 'eingereicht') AS pending "
        "FROM orders o JOIN firms f ON f.id = o.firm_id "
        "LEFT JOIN projects p ON p.id = o.project_id"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY o.active DESC, f.name, o.valid_to IS NULL, o.valid_to, o.id",
        params,
    ).fetchall()
    return [_order(r, today) for r in rows]


def _order(row, today: date) -> dict:
    o = dict(row)
    o["factor"] = o["hours_per_day"] if o["unit"] == "pt" else 1.0
    o["percent"] = o["billed"] / o["amount"] * 100 if o["amount"] else 0.0
    o["remaining"] = o["amount"] - o["billed"]
    o["level"] = _level(o["percent"])
    o["label"] = " · ".join(x for x in (o["number"], o["title"]) if x)
    warnings = []
    if o["active"]:
        if o["percent"] > 100:
            warnings.append("überschritten")
        elif o["percent"] >= WARN_PERCENT:
            warnings.append(f"{o['percent']:.0f} % verbraucht")
        end = util.to_date(o["valid_to"])
        if end:
            days_left = (end - today).days
            if days_left < 0:
                warnings.append(f"abgelaufen am {util.fmt_date(end)}")
            elif days_left <= EXPIRY_DAYS:
                warnings.append(f"läuft in {days_left} Tagen ab")
    o["warnings"] = warnings
    return o


def order(db, order_id, today: date) -> dict | None:
    rows = [o for o in orders(db, today) if o["id"] == order_id]
    return rows[0] if rows else None


def firm_summary(db, today: date, firm_id=None) -> list[dict]:
    """One row per firm with active orders: ordered, planned, billed, free (in hours)."""
    by_firm: dict[int, list] = {}
    for o in orders(db, today, firm_id=firm_id, active_only=True):
        by_firm.setdefault(o["firm_id"], []).append(o)
    result = []
    for fid, items in by_firm.items():
        ordered = sum(o["amount"] * o["factor"] for o in items)
        billed = sum(o["billed"] * o["factor"] for o in items)
        project_ids = {o["project_id"] for o in items}
        sql = "SELECT COALESCE(SUM(effort_hours), 0) FROM tasks WHERE firm_id = ?"
        params = [fid]
        if None not in project_ids:
            sql += f" AND project_id IN ({','.join('?' * len(project_ids))})"
            params += sorted(project_ids)
        planned = db.execute(sql, params).fetchone()[0]
        percent_planned = planned / ordered * 100 if ordered else 0.0
        ends = [util.to_date(o["valid_to"]) for o in items if o["valid_to"]]
        warnings = []
        if planned > ordered:
            warnings.append(f"überplant ({percent_planned:.0f} %)")
        elif percent_planned >= WARN_PERCENT:
            warnings.append(f"{percent_planned:.0f} % verplant")
        for o in items:
            warnings += [f"{o['label']}: {w}" for w in o["warnings"]]
        result.append({
            "firm_id": fid, "firm_name": items[0]["firm_name"], "orders": items,
            "ordered": ordered, "planned": planned, "billed": billed,
            "free": ordered - planned, "percent_planned": percent_planned,
            "percent_billed": billed / ordered * 100 if ordered else 0.0,
            "level": _level(percent_planned), "valid_to": max(ends) if ends else None,
            "warnings": warnings,
        })
    return sorted(result, key=lambda r: (-len(r["warnings"]), r["firm_name"]))


def warning_count(db, today: date) -> int:
    return sum(1 for f in firm_summary(db, today) if f["warnings"])
