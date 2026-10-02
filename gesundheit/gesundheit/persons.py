"""Persons: several profiles under one login (family, partner). Every value belongs to one.

The person shown is remembered in the cookie gs_person (only an id, checked against the
database on every request). Each person has a colour used in comparisons, their own height
and goals, and their own Withings, Garmin and Apple connections.
"""

from flask import current_app, g, has_request_context, request

from . import util

COOKIE = "gs_person"

# key: label, colour (also in gesundheit.css as .p-<key>)
COLORS = {
    "blau": ("Blau", "#4f8cff"),
    "pink": ("Pink", "#ff5fa2"),
    "gruen": ("Grün", "#2fbf71"),
    "orange": ("Orange", "#ff8a3d"),
    "violett": ("Violett", "#9b6bff"),
    "tuerkis": ("Türkis", "#1ec2c2"),
    "gelb": ("Gelb", "#f2b705"),
    "rot": ("Rot", "#ff5a5a"),
}

GOAL_FIELDS = ("goal_steps", "goal_active_min", "goal_active_kcal", "goal_sleep_min",
               "goal_workouts", "goal_weight_dg", "goal_weight_date")
EDITABLE = ("name", "color", "birth_year", "height_cm") + GOAL_FIELDS + (
    "garmin_enabled", "garmin_backfill_days")


def all_persons(db) -> list[dict]:
    return [dict(r) for r in db.execute("SELECT * FROM persons ORDER BY position, id")]


def get(db, person_id) -> dict | None:
    try:
        person_id = int(person_id)
    except (TypeError, ValueError):
        return None
    row = db.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    return dict(row) if row else None


def free_color(db) -> str:
    used = {r[0] for r in db.execute("SELECT color FROM persons")}
    return next((c for c in COLORS if c not in used), "blau")


def create(db, name: str, color: str | None = None, **fields) -> int:
    position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM persons").fetchone()[0]
    values = {"name": name, "color": color if color in COLORS else free_color(db),
              "position": position, "created_at": util.stamp()}
    values.update({k: v for k, v in fields.items() if k in EDITABLE})
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return db.execute(f"INSERT INTO persons ({columns}) VALUES ({marks})",
                      tuple(values.values())).lastrowid


def update(db, person_id: int, **fields) -> None:
    values = {k: v for k, v in fields.items() if k in EDITABLE}
    if "color" in values and values["color"] not in COLORS:
        del values["color"]
    if not values:
        return
    assignments = ", ".join(f"{k} = ?" for k in values)
    db.execute(f"UPDATE persons SET {assignments} WHERE id = ?", (*values.values(), person_id))


def delete(db, person_id: int) -> None:
    db.execute("DELETE FROM persons WHERE id = ?", (person_id,))  # values cascade


def age(person: dict, today=None) -> int | None:
    if not person.get("birth_year"):
        return None
    return (today or util.today()).year - person["birth_year"]


def initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() or "?"


def ensure_one(db, name: str) -> None:
    """There is always at least one person (named after the account on first use)."""
    if not db.execute("SELECT 1 FROM persons LIMIT 1").fetchone():
        create(db, name)
        db.commit()


def load_current():
    """before_request: g.person and g.persons for logged-in pages."""
    g.person = None
    g.persons = []
    if not g.get("user"):
        return
    from .db import get_db
    db = get_db()
    ensure_one(db, g.user["username"])
    g.persons = all_persons(db)
    wanted = request.cookies.get(COOKIE, "")
    g.person = next((p for p in g.persons if str(p["id"]) == wanted), g.persons[0])


def remember(response):
    person = g.get("person")
    if person and has_request_context() and request.cookies.get(COOKIE) != str(person["id"]):
        set_cookie(response, person["id"])
    return response


def set_cookie(response, person_id: int):
    response.set_cookie(COOKIE, str(person_id), max_age=365 * 24 * 3600, httponly=True,
                        samesite="Lax", secure=current_app.config["SECURE_COOKIES"], path="/")
    return response
