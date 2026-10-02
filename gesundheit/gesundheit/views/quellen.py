"""Sources: connect Withings and Garmin, upload the Apple Health export, source order.

Everything on this page is for the person currently shown (g.person); only the Withings
application (client ID and secret) is shared by everyone.
"""

import hmac
import os
import secrets
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)

from .. import forms, garmin, jobs, persons, store, util, withings
from ..db import get_db
from ..katalog import FAMILIES, SOURCES
from . import parse_or_flash

bp = Blueprint("quellen", __name__, url_prefix="/quellen")


def callback_url() -> str:
    base = current_app.config["BASE_URL"]
    path = url_for("quellen.withings_callback")
    return base + path if base else url_for("quellen.withings_callback", _external=True)


def _app():
    return current_app._get_current_object()


def _back(anchor: str):
    return redirect(url_for("quellen.index") + f"#{anchor}")


@bp.route("")
def index():
    db = get_db()
    app = _app()
    pid = g.person["id"]
    client_id, client_secret = jobs.withings_app(app, db)
    connections = {row["provider"]: row for row in db.execute(
        "SELECT * FROM connections WHERE person_id = ?", (pid,))}
    everyone = {}
    for row in db.execute("SELECT provider, person_id, last_error, last_ok FROM connections"):
        everyone.setdefault(row["person_id"], {})[row["provider"]] = row
    imports = db.execute("SELECT * FROM imports WHERE person_id = ? ORDER BY id DESC LIMIT 8",
                         (pid,)).fetchall()
    orders = {family: store.priority(db, family) for family in FAMILIES}
    customized = {row["family"] for row in db.execute("SELECT family FROM source_priority")}
    mfa = session.get("garmin_mfa") or {}
    return render_template(
        "quellen.html",
        withings={"configured": bool(client_id and client_secret),
                  "from_env": bool(current_app.config["WITHINGS_CLIENT_ID"]),
                  "client_id_hint": (client_id[:4] + "…" + client_id[-3:]) if client_id else "",
                  "connected": bool(jobs.load_secret(app, db, "withings", pid).get("tokens")),
                  "row": connections.get("withings"), "busy": jobs.busy("withings")},
        garmin_state={"available": garmin.available(),
                      "enabled": bool(g.person["garmin_enabled"]),
                      "connected": bool(jobs.load_secret(app, db, "garmin", pid).get("tokens")),
                      "row": connections.get("garmin"), "busy": jobs.busy("garmin"),
                      "mfa": mfa.get("person") == pid,
                      "backfill": g.person["garmin_backfill_days"]},
        everyone=everyone, callback=callback_url(), imports=imports,
        apple_busy=jobs.busy("apple"), folder=current_app.config["IMPORT_DIR"],
        folder_files=jobs.import_folder_files(app)[:5],
        upload_max=current_app.config["UPLOAD_MAX_MB"], orders=orders, customized=customized,
        overview=store.sources_overview(db, pid), families=FAMILIES, sources=SOURCES)


# ---------- Withings ----------

@bp.route("/withings/zugang", methods=["POST"])
def withings_credentials():
    values = parse_or_flash({
        "client_id": forms.Text("Client-ID", required=True, max_len=200),
        "client_secret": forms.Text("Client-Secret", required=True, max_len=200),
    })
    if values is not None:
        if not all(c.isalnum() or c in "-_." for c in values["client_id"] + values["client_secret"]):
            flash("Client-ID und Secret enthalten ungültige Zeichen.", "error")
        else:
            db = get_db()
            jobs.save_withings_app(_app(), db, values["client_id"], values["client_secret"])
            db.commit()
            flash("Withings-Anwendung gespeichert (verschlüsselt). Jetzt je Person „Mit Withings "
                  "verbinden“.", "ok")
    return _back("withings")


@bp.route("/withings/zugang/loeschen", methods=["POST"])
def withings_credentials_delete():
    db = get_db()
    jobs.delete_withings_app(db)
    db.commit()
    flash("Withings-Anwendung gelöscht. Verbundene Personen können erst wieder abgleichen, "
          "wenn sie neu eingetragen ist.", "ok")
    return _back("withings")


@bp.route("/withings/verbinden", methods=["POST"])
def withings_connect():
    client_id, client_secret = jobs.withings_app(_app(), get_db())
    if not client_id or not client_secret:
        flash("Zuerst Client-ID und Secret der Withings-Anwendung eintragen.", "error")
        return _back("withings")
    state = secrets.token_urlsafe(24)
    session["withings_state"] = {"state": state, "person": g.person["id"]}
    return redirect(withings.authorize_url(client_id, callback_url(), state))


@bp.route("/withings/zurueck")
def withings_callback():
    expected = session.pop("withings_state", None) or {}
    state = request.args.get("state", "")
    if not expected.get("state") or not hmac.compare_digest(state, expected["state"]):
        flash("Die Rückmeldung von Withings passt nicht zu dieser Anmeldung. Bitte noch "
              "einmal verbinden.", "error")
        return _back("withings")
    if request.args.get("error"):
        flash("Die Verbindung mit Withings wurde abgebrochen.", "error")
        return _back("withings")
    code = request.args.get("code", "")
    if not code or len(code) > 200:
        abort(400)
    db = get_db()
    app = _app()
    person = persons.get(db, expected.get("person"))
    if not person:
        abort(400)
    client_id, client_secret = jobs.withings_app(app, db)
    try:
        tokens = withings.exchange_code(jobs.withings_http(app), client_id, client_secret, code,
                                        callback_url())
    except withings.WithingsError as exc:
        flash(str(exc), "error")
        return _back("withings")
    for other in jobs.connected_persons(app, db, "withings"):
        other_tokens = jobs.load_secret(app, db, "withings", other).get("tokens") or {}
        if other != person["id"] and tokens.get("userid") and \
                other_tokens.get("userid") == tokens["userid"]:
            other_name = (persons.get(db, other) or {}).get("name", "einer anderen Person")
            flash(f"Dieses Withings-Konto ist schon mit {other_name} verbunden. Bei Withings "
                  "erst mit dem Konto der richtigen Person anmelden.", "error")
            return _back("withings")
    jobs.save_secret(app, db, "withings", person["id"], {"tokens": tokens},
                     label=f"Konto …{tokens['userid'][-4:]}" if tokens.get("userid") else "")
    db.execute("UPDATE connections SET connected_at = ?, last_error = '', cursor = '{}' "
               "WHERE provider = 'withings' AND person_id = ?", (util.stamp(), person["id"]))
    db.commit()
    jobs.start(app, "withings", jobs.run_withings, person["id"])
    response = _back("withings")
    persons.set_cookie(response, person["id"])
    flash(f"Withings ist für {person['name']} verbunden. Der erste Abgleich läuft im "
          "Hintergrund.", "ok")
    return response


@bp.route("/withings/abgleichen", methods=["POST"])
def withings_sync():
    app = _app()
    pid = g.person["id"]
    if not jobs.load_secret(app, get_db(), "withings", pid).get("tokens"):
        flash("Withings ist für diese Person nicht verbunden.", "error")
    elif jobs.start(app, "withings", jobs.run_withings, pid):
        flash("Withings-Abgleich gestartet.", "ok")
    else:
        flash("Der Withings-Abgleich läuft bereits.", "info")
    return _back("withings")


@bp.route("/withings/trennen", methods=["POST"])
def withings_disconnect():
    db = get_db()
    jobs.disconnect(db, "withings", g.person["id"])
    db.commit()
    flash(f"Withings für {g.person['name']} getrennt, die Anmeldung ist gelöscht. Die bisherigen "
          "Werte bleiben, bis du sie unter „Daten“ löschst.", "ok")
    return _back("withings")


# ---------- Garmin ----------

@bp.route("/garmin/schalter", methods=["POST"])
def garmin_toggle():
    values = parse_or_flash({
        "aktiv": forms.Checkbox("Garmin direkt"),
        "tage": forms.Integer("Tage beim ersten Abgleich", min_value=1, max_value=365),
    })
    if values is not None:
        db = get_db()
        pid = g.person["id"]
        fields = {"garmin_enabled": 1 if values["aktiv"] else 0}
        if values["tage"]:
            fields["garmin_backfill_days"] = values["tage"]
        persons.update(db, pid, **fields)
        if not values["aktiv"]:
            jobs.disconnect(db, "garmin", pid)
            session.pop("garmin_mfa", None)
        db.commit()
        flash(f"Garmin direkt ist für {g.person['name']} eingeschaltet." if values["aktiv"] else
              f"Garmin direkt ist für {g.person['name']} ausgeschaltet; die Anmeldung wurde "
              "gelöscht.", "ok")
    return _back("garmin")


def _garmin_connected(pid: int, tokens: str):
    db = get_db()
    app = _app()
    jobs.save_secret(app, db, "garmin", pid, {"tokens": tokens}, label="")
    db.execute("UPDATE connections SET connected_at = ?, last_ok = NULL, last_error = '' "
               "WHERE provider = 'garmin' AND person_id = ?", (util.stamp(), pid))
    db.commit()
    person = persons.get(db, pid)
    jobs.start(app, "garmin", jobs.run_garmin, pid, person["garmin_backfill_days"])
    flash(f"Garmin ist für {person['name']} verbunden. Der erste Abgleich läuft im "
          "Hintergrund.", "ok")


@bp.route("/garmin/anmelden", methods=["POST"])
def garmin_login():
    if not g.person["garmin_enabled"] or not garmin.available():
        abort(400, description="Garmin direkt ist ausgeschaltet.")
    values = parse_or_flash({
        "email": forms.Email("E-Mail", required=True),
        "password": forms.Text("Passwort", required=True, max_len=200),
    })
    if values is not None:
        try:
            status, value = garmin.start_login(values["email"], values["password"])
        except garmin.GarminError as exc:
            flash(str(exc), "error")
        else:
            if status == "mfa":
                session["garmin_mfa"] = {"id": value, "person": g.person["id"]}
                flash("Garmin hat einen Code geschickt (E-Mail oder App). Bitte innerhalb von "
                      "5 Minuten eingeben.", "info")
            else:
                _garmin_connected(g.person["id"], value)
    return _back("garmin")


@bp.route("/garmin/code", methods=["POST"])
def garmin_code():
    values = parse_or_flash({"code": forms.Text("Code", required=True, max_len=12)})
    pending = session.pop("garmin_mfa", None) or {}
    if values is not None:
        if not pending.get("id"):
            flash("Der Anmeldevorgang ist abgelaufen. Bitte noch einmal anmelden.", "error")
        elif not values["code"].isdigit():
            flash("Der Code besteht nur aus Ziffern.", "error")
            session["garmin_mfa"] = pending
        else:
            try:
                _garmin_connected(pending["person"], garmin.finish_login(pending["id"],
                                                                         values["code"]))
            except garmin.GarminError as exc:
                flash(str(exc), "error")
    return _back("garmin")


@bp.route("/garmin/abgleichen", methods=["POST"])
def garmin_sync():
    app = _app()
    pid = g.person["id"]
    if not g.person["garmin_enabled"] or not jobs.load_secret(app, get_db(), "garmin",
                                                              pid).get("tokens"):
        flash("Garmin ist für diese Person nicht verbunden.", "error")
    elif jobs.start(app, "garmin", jobs.run_garmin, pid):
        flash("Garmin-Abgleich gestartet.", "ok")
    else:
        flash("Der Garmin-Abgleich läuft bereits.", "info")
    return _back("garmin")


@bp.route("/garmin/trennen", methods=["POST"])
def garmin_disconnect():
    db = get_db()
    jobs.disconnect(db, "garmin", g.person["id"])
    session.pop("garmin_mfa", None)
    db.commit()
    flash("Garmin getrennt, die Anmeldung ist gelöscht.", "ok")
    return _back("garmin")


# ---------- Apple Health ----------

def _new_import(db, pid: int, filename: str) -> int:
    safe = "".join(c for c in filename if c.isalnum() or c in "._- ")[:80] or "export.zip"
    cur = db.execute("INSERT INTO imports (kind, filename, status, started_at, person_id) "
                     "VALUES ('apple', ?, 'wartet', ?, ?)", (safe, util.stamp(), pid))
    db.commit()
    return cur.lastrowid


def _wants_json() -> bool:
    return bool(request.headers.get("X-Gesundheit-Ajax"))


@bp.route("/apple/hochladen", methods=["POST"])
def apple_upload():
    app = _app()
    upload = request.files.get("datei")
    if set(request.form) - {"csrf_token"} or set(request.files) - {"datei"}:
        abort(400, description="Das Formular enthält unerwartete Felder.")
    if not upload or not upload.filename:
        message, ok = "Bitte die Datei „Export.zip“ auswählen.", False
    elif not upload.filename.lower().endswith(".zip"):
        message, ok = "Bitte die ZIP-Datei aus der Health-App hochladen (Export.zip).", False
    elif jobs.busy("apple"):
        message, ok = "Es läuft bereits ein Import. Bitte warten, bis er fertig ist.", False
    else:
        db = get_db()
        pid = g.person["id"]
        import_id = _new_import(db, pid, upload.filename)
        target = Path(app.config["UPLOAD_DIR"]) / f"import-{import_id}.zip"
        part = getattr(upload.stream, "name", None)
        if isinstance(part, str) and os.path.exists(part):
            upload.stream.flush()
            os.replace(part, target)  # same folder: no copy of a large file
        else:
            upload.save(target)
        target.chmod(0o600)
        jobs.start(app, "apple", jobs.run_import, import_id, pid, str(target), True)
        message, ok = (f"Datei für {g.person['name']} hochgeladen. Das Einlesen läuft im "
                       "Hintergrund."), True
        if _wants_json():
            return jsonify({"ok": True, "nachricht": message, "import": import_id,
                            "status_url": url_for("quellen.import_status", import_id=import_id)})
    if _wants_json():
        return jsonify({"ok": ok, "nachricht": message}), (200 if ok else 400)
    flash(message, "ok" if ok else "error")
    return _back("apple")


@bp.route("/apple/ordner", methods=["POST"])
def apple_folder():
    app = _app()
    if set(request.form) - {"csrf_token"}:
        abort(400)
    files = jobs.import_folder_files(app)
    if not files:
        flash(f"Im Import-Ordner ({app.config['IMPORT_DIR']}) liegt keine ZIP-Datei.", "error")
    elif jobs.busy("apple"):
        flash("Es läuft bereits ein Import.", "info")
    else:
        pid = g.person["id"]
        import_id = _new_import(get_db(), pid, files[0].name)
        jobs.start(app, "apple", jobs.run_import, import_id, pid, str(files[0]), False)
        flash(f"„{files[0].name}“ wird für {g.person['name']} eingelesen.", "ok")
    return _back("apple")


@bp.route("/import/<int:import_id>.json")
def import_status(import_id):
    row = get_db().execute("SELECT id, status, progress, message, records FROM imports "
                           "WHERE id = ?", (import_id,)).fetchone()
    if not row:
        abort(404)
    return jsonify(dict(row))


# ---------- Source order ----------

@bp.route("/reihenfolge", methods=["POST"])
def order():
    values = parse_or_flash({
        "familie": forms.Choice("Bereich", FAMILIES, required=True),
        "quelle": forms.Choice("Quelle", SOURCES),
        "richtung": forms.Choice("Richtung", ("hoch", "runter", "standard"), required=True),
    })
    if values is not None:
        db = get_db()
        family = values["familie"]
        if values["richtung"] == "standard":
            store.reset_priority(db, family)
        elif values["quelle"]:
            current = store.priority(db, family)
            index = current.index(values["quelle"])
            other = index - 1 if values["richtung"] == "hoch" else index + 1
            if 0 <= other < len(current):
                current[index], current[other] = current[other], current[index]
                store.set_priority(db, family, current)
        db.commit()
    target = values["familie"] if values else ""
    return _back(f"reihenfolge-{target}")
