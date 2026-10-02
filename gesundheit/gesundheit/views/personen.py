"""Persons: list, create, edit (profile and goals), delete, switch the person shown."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import forms, persons, store, util
from ..db import get_db
from . import back, parse_or_flash

bp = Blueprint("personen", __name__, url_prefix="/personen")


def _fields(required_name=True):
    year = util.today().year
    return {
        "name": forms.Text("Name", required=required_name, max_len=40),
        "color": forms.Choice("Farbe", persons.COLORS, required=True),
        "birth_year": forms.Integer("Geburtsjahr", min_value=year - 120, max_value=year),
        "height_cm": forms.Integer("Größe", min_value=50, max_value=250),
        "goal_steps": forms.Integer("Schritte am Tag", required=True, min_value=500,
                                    max_value=100000),
        "goal_active_min": forms.Integer("Aktive Minuten", required=True, min_value=5,
                                         max_value=600),
        "goal_active_kcal": forms.Integer("Aktivkalorien", required=True, min_value=50,
                                          max_value=5000),
        "goal_sleep_h": forms.Number("Schlaf", required=True, min_value=4, max_value=14),
        "goal_workouts": forms.Integer("Trainings pro Woche", required=True, min_value=0,
                                       max_value=21),
        "goal_weight": forms.Number("Zielgewicht", min_value=10, max_value=300),
        "goal_weight_date": forms.Date("Zieldatum"),
    }


def _to_columns(values: dict) -> dict:
    columns = {k: values[k] for k in ("name", "color", "birth_year", "height_cm", "goal_steps",
                                      "goal_active_min", "goal_active_kcal", "goal_workouts")}
    columns["goal_sleep_min"] = round(values["goal_sleep_h"] * 60)
    columns["goal_weight_dg"] = round(values["goal_weight"] * 10) if values["goal_weight"] else None
    columns["goal_weight_date"] = values["goal_weight_date"] if columns["goal_weight_dg"] else None
    return columns


def _person_or_404(person_id):
    person = persons.get(get_db(), person_id)
    if not person:
        abort(404)
    return person


@bp.route("")
def index():
    db = get_db()
    rows = []
    for person in g.persons:
        overview = store.sources_overview(db, person["id"])
        rows.append({"person": person,
                     "count": sum(v["count"] for v in overview.values()),
                     "last": max(filter(None, (v["last"] for v in overview.values())), default=None),
                     "sources": [k for k, v in overview.items() if v["count"]],
                     "connections": [r["provider"] for r in db.execute(
                         "SELECT provider FROM connections WHERE person_id = ?", (person["id"],))]})
    return render_template("personen.html", rows=rows, colors=persons.COLORS,
                           new_color=persons.free_color(db))


@bp.route("", methods=["POST"])
def create():
    values = parse_or_flash({"name": forms.Text("Name", required=True, max_len=40),
                             "color": forms.Choice("Farbe", persons.COLORS, required=True)})
    if values is None:
        return redirect(url_for("personen.index"))
    db = get_db()
    person_id = persons.create(db, values["name"].strip(), values["color"])
    db.commit()
    flash(f"{values['name']} ist angelegt. Jetzt Ziele eintragen und unter „Quellen“ die Geräte "
          "verbinden.", "ok")
    response = redirect(url_for("personen.edit", person_id=person_id))
    return persons.set_cookie(response, person_id)


@bp.route("/<int:person_id>", methods=["GET", "POST"])
def edit(person_id):
    person = _person_or_404(person_id)
    if request.method == "POST":
        values = parse_or_flash(_fields())
        if values is not None:
            db = get_db()
            persons.update(db, person_id, **_to_columns(values))
            db.commit()
            flash(f"Profil und Ziele von {values['name']} gespeichert.", "ok")
            return redirect(url_for("personen.edit", person_id=person_id))
    return render_template("person.html", p=person, colors=persons.COLORS,
                           age=persons.age(person))


@bp.route("/<int:person_id>/zeigen", methods=["POST"])
def show(person_id):
    person = _person_or_404(person_id)
    response = back(url_for("main.index"))
    return persons.set_cookie(response, person["id"])


@bp.route("/<int:person_id>/loeschen", methods=["POST"])
def delete(person_id):
    person = _person_or_404(person_id)
    values = parse_or_flash({"bestaetigung": forms.Text("Bestätigung", required=True,
                                                        max_len=40)})
    if values is None:
        return redirect(url_for("personen.edit", person_id=person_id))
    if len(g.persons) <= 1:
        flash("Die letzte Person kann nicht gelöscht werden. Daten löschen geht unter „Daten“.",
              "error")
    elif values["bestaetigung"].strip() != person["name"]:
        flash(f"Zur Bestätigung bitte genau den Namen „{person['name']}“ eintippen.", "error")
    else:
        db = get_db()
        persons.delete(db, person_id)
        db.commit()
        db.execute("VACUUM")
        flash(f"{person['name']} und alle Werte dieser Person sind gelöscht.", "ok")
        return redirect(url_for("personen.index"))
    return redirect(url_for("personen.edit", person_id=person_id))


@bp.route("/reihenfolge", methods=["POST"])
def move():
    values = parse_or_flash({"person": forms.Integer("Person", required=True, min_value=1),
                             "richtung": forms.Choice("Richtung", ("hoch", "runter"),
                                                      required=True)})
    if values is not None:
        db = get_db()
        ids = [p["id"] for p in g.persons]
        if values["person"] in ids:
            i = ids.index(values["person"])
            j = i - 1 if values["richtung"] == "hoch" else i + 1
            if 0 <= j < len(ids):
                ids[i], ids[j] = ids[j], ids[i]
                for position, pid in enumerate(ids):
                    db.execute("UPDATE persons SET position = ? WHERE id = ?", (position, pid))
                db.commit()
    return redirect(url_for("personen.index"))
