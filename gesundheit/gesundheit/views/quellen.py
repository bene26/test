"""Sources: connect Withings and Garmin, upload the Apple Health export, source order."""

import hmac
import os
import secrets
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from .. import forms, garmin, jobs, settings, store, util, withings
from ..db import get_db
from ..katalog import FAMILIES, SOURCES
from . import parse_or_flash

bp = Blueprint("quellen", __name__, url_prefix="/quellen")


def callback_url() -> str:
    base = current_app.config["BASE_URL"]
    path = url_for("quellen.withings_callback")
    return base + path if base else url_for("quellen.withings_callback", _external=True)


@bp.route("")
def index():
    db = get_db()
    app = current_app._get_current_object()
    withings_secret = jobs.load_secret(app, db, "withings")
    client_id, client_secret = jobs.withings_credentials(app, withings_secret)
    connections = {row["provider"]: row for row in db.execute("SELECT * FROM connections")}
    garmin_secret = jobs.load_secret(app, db, "garmin")
    imports = db.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 8").fetchall()
    orders = {family: store.priority(db, family) for family in FAMILIES}
    customized = {row["family"] for row in db.execute("SELECT family FROM source_priority")}
    return render_template(
        "quellen.html",
        withings={"configured": bool(client_id and client_secret),
                  "from_env": bool(current_app.config["WITHINGS_CLIENT_ID"]),
                  "client_id_hint": (client_id[:4] + "…" + client_id[-3:]) if client_id else "",
                  "connected": bool(withings_secret.get("tokens")),
                  "row": connections.get("withings"), "busy": jobs.busy("withings")},
        garmin_state={"available": garmin.available(),
                      "enabled": bool(settings.get(db, "garmin_enabled")),
                      "connected": bool(garmin_secret.get("tokens")),
                      "row": connections.get("garmin"), "busy": jobs.busy("garmin"),
                      "mfa": session.get("garmin_mfa"),
                      "backfill": settings.get(db, "garmin_backfill_days")},
        callback=callback_url(), imports=imports, apple_busy=jobs.busy("apple"),
        folder=current_app.config["IMPORT_DIR"],
        folder_files=jobs.import_folder_files(app)[:5],
        upload_max=current_app.config["UPLOAD_MAX_MB"], orders=orders, customized=customized,
        overview=store.sources_overview(db), families=FAMILIES, sources=SOURCES)


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
            app = current_app._get_current_object()
            secret = jobs.load_secret(app, db, "withings")
            secret.update(client_id=values["client_id"], client_secret=values["client_secret"])
            jobs.save_secret(app, db, "withings", secret)
            db.commit()
            flash("Withings-Zugang gespeichert (verschlüsselt). Jetzt „Mit Withings verbinden“.",
                  "ok")
    return redirect(url_for("quellen.index") + "#withings")


@bp.route("/withings/verbinden", methods=["POST"])
def withings_connect():
    db = get_db()
    app = current_app._get_current_object()
    client_id, client_secret = jobs.withings_credentials(app, jobs.load_secret(app, db,
                                                                               "withings"))
    if not client_id or not client_secret:
        flash("Zuerst Client-ID und Secret der Withings-Anwendung eintragen.", "error")
        return redirect(url_for("quellen.index") + "#withings")
    state = secrets.token_urlsafe(24)
    session["withings_state"] = state
    return redirect(withings.authorize_url(client_id, callback_url(), state))


@bp.route("/withings/zurueck")
def withings_callback():
    expected = session.pop("withings_state", None)
    state = request.args.get("state", "")
    if not expected or not hmac.compare_digest(state, expected):
        flash("Die Rückmeldung von Withings passt nicht zu dieser Anmeldung. Bitte noch "
              "einmal verbinden.", "error")
        return redirect(url_for("quellen.index") + "#withings")
    if request.args.get("error"):
        flash("Die Verbindung mit Withings wurde abgebrochen.", "error")
        return redirect(url_for("quellen.index") + "#withings")
    code = request.args.get("code", "")
    if not code or len(code) > 200:
        abort(400)
    db = get_db()
    app = current_app._get_current_object()
    secret = jobs.load_secret(app, db, "withings")
    client_id, client_secret = jobs.withings_credentials(app, secret)
    try:
        tokens = withings.exchange_code(jobs.withings_http(app), client_id, client_secret, code,
                                        callback_url())
    except withings.WithingsError as exc:
        flash(str(exc), "error")
        return redirect(url_for("quellen.index") + "#withings")
    secret["tokens"] = tokens
    jobs.save_secret(app, db, "withings", secret, label=f"Konto {tokens['userid'][-4:]}"
                     if tokens.get("userid") else "")
    db.execute("UPDATE connections SET connected_at = ?, last_error = '', cursor = '{}' "
               "WHERE provider = 'withings'", (util.stamp(),))
    db.commit()
    jobs.start(app, "withings", jobs.run_withings)
    flash("Withings ist verbunden. Der erste Abgleich läuft im Hintergrund.", "ok")
    return redirect(url_for("quellen.index") + "#withings")


@bp.route("/withings/abgleichen", methods=["POST"])
def withings_sync():
    app = current_app._get_current_object()
    if not jobs.load_secret(app, get_db(), "withings").get("tokens"):
        flash("Withings ist nicht verbunden.", "error")
    elif jobs.start(app, "withings", jobs.run_withings):
        flash("Withings-Abgleich gestartet.", "ok")
    else:
        flash("Der Withings-Abgleich läuft bereits.", "info")
    return redirect(url_for("quellen.index") + "#withings")


@bp.route("/withings/trennen", methods=["POST"])
def withings_disconnect():
    values = parse_or_flash({"zugang": forms.Checkbox("Zugang ebenfalls löschen")})
    if values is None:
        return redirect(url_for("quellen.index") + "#withings")
    db = get_db()
    app = current_app._get_current_object()
    secret = jobs.load_secret(app, db, "withings")
    keep = None if values["zugang"] else {k: secret[k] for k in ("client_id", "client_secret")
                                          if k in secret}
    jobs.disconnect(db, "withings", keep_credentials=keep, app=app)
    db.commit()
    flash("Withings getrennt. Die Zugangsdaten sind gelöscht; die bisherigen Werte bleiben, "
          "bis du sie unter „Daten“ löschst.", "ok")
    return redirect(url_for("quellen.index") + "#withings")


# ---------- Garmin ----------

@bp.route("/garmin/schalter", methods=["POST"])
def garmin_toggle():
    values = parse_or_flash({
        "aktiv": forms.Checkbox("Garmin direkt"),
        "tage": forms.Integer("Tage beim ersten Abgleich", min_value=1, max_value=365),
    })
    if values is not None:
        db = get_db()
        settings.put(db, "garmin_enabled", 1 if values["aktiv"] else 0)
        if values["tage"]:
            settings.put(db, "garmin_backfill_days", values["tage"])
        if not values["aktiv"]:
            jobs.disconnect(db, "garmin")
            session.pop("garmin_mfa", None)
        db.commit()
        flash("Garmin direkt ist eingeschaltet." if values["aktiv"] else
              "Garmin direkt ist ausgeschaltet; die Anmeldung wurde gelöscht.", "ok")
    return redirect(url_for("quellen.index") + "#garmin")


def _garmin_connected(tokens: str):
    db = get_db()
    app = current_app._get_current_object()
    jobs.save_secret(app, db, "garmin", {"tokens": tokens}, label="")
    db.execute("UPDATE connections SET connected_at = ?, last_ok = NULL, last_error = '' "
               "WHERE provider = 'garmin'", (util.stamp(),))
    db.commit()
    jobs.start(app, "garmin", jobs.run_garmin, settings.get(db, "garmin_backfill_days"))
    flash("Garmin ist verbunden. Der erste Abgleich läuft im Hintergrund.", "ok")


@bp.route("/garmin/anmelden", methods=["POST"])
def garmin_login():
    db = get_db()
    if not settings.get(db, "garmin_enabled") or not garmin.available():
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
                session["garmin_mfa"] = value
                flash("Garmin hat einen Code geschickt (E-Mail oder App). Bitte innerhalb von "
                      "5 Minuten eingeben.", "info")
            else:
                _garmin_connected(value)
    return redirect(url_for("quellen.index") + "#garmin")


@bp.route("/garmin/code", methods=["POST"])
def garmin_code():
    values = parse_or_flash({"code": forms.Text("Code", required=True, max_len=12)})
    pending = session.pop("garmin_mfa", None)
    if values is not None:
        if not pending:
            flash("Der Anmeldevorgang ist abgelaufen. Bitte noch einmal anmelden.", "error")
        elif not values["code"].isdigit():
            flash("Der Code besteht nur aus Ziffern.", "error")
            session["garmin_mfa"] = pending
        else:
            try:
                _garmin_connected(garmin.finish_login(pending, values["code"]))
            except garmin.GarminError as exc:
                flash(str(exc), "error")
    return redirect(url_for("quellen.index") + "#garmin")


@bp.route("/garmin/abgleichen", methods=["POST"])
def garmin_sync():
    app = current_app._get_current_object()
    db = get_db()
    if not settings.get(db, "garmin_enabled") or not jobs.load_secret(app, db, "garmin").get(
            "tokens"):
        flash("Garmin ist nicht verbunden.", "error")
    elif jobs.start(app, "garmin", jobs.run_garmin):
        flash("Garmin-Abgleich gestartet.", "ok")
    else:
        flash("Der Garmin-Abgleich läuft bereits.", "info")
    return redirect(url_for("quellen.index") + "#garmin")


@bp.route("/garmin/trennen", methods=["POST"])
def garmin_disconnect():
    db = get_db()
    jobs.disconnect(db, "garmin")
    session.pop("garmin_mfa", None)
    db.commit()
    flash("Garmin getrennt, die Anmeldung ist gelöscht.", "ok")
    return redirect(url_for("quellen.index") + "#garmin")


# ---------- Apple Health ----------

def _new_import(db, filename: str) -> int:
    safe = "".join(c for c in filename if c.isalnum() or c in "._- ")[:80] or "export.zip"
    cur = db.execute("INSERT INTO imports (kind, filename, status, started_at) "
                     "VALUES ('apple', ?, 'wartet', ?)", (safe, util.stamp()))
    db.commit()
    return cur.lastrowid


def _wants_json() -> bool:
    return bool(request.headers.get("X-Gesundheit-Ajax"))


@bp.route("/apple/hochladen", methods=["POST"])
def apple_upload():
    app = current_app._get_current_object()
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
        import_id = _new_import(db, upload.filename)
        target = Path(app.config["UPLOAD_DIR"]) / f"import-{import_id}.zip"
        part = getattr(upload.stream, "name", None)
        if isinstance(part, str) and os.path.exists(part):
            upload.stream.flush()
            os.replace(part, target)  # same folder: no copy of a large file
        else:
            upload.save(target)
        target.chmod(0o600)
        jobs.start(app, "apple", jobs.run_import, import_id, str(target), True)
        message, ok = "Datei hochgeladen. Das Einlesen läuft im Hintergrund.", True
        if _wants_json():
            return jsonify({"ok": True, "nachricht": message, "import": import_id,
                            "status_url": url_for("quellen.import_status", import_id=import_id)})
    if _wants_json():
        return jsonify({"ok": ok, "nachricht": message}), (200 if ok else 400)
    flash(message, "ok" if ok else "error")
    return redirect(url_for("quellen.index") + "#apple")


@bp.route("/apple/ordner", methods=["POST"])
def apple_folder():
    app = current_app._get_current_object()
    if set(request.form) - {"csrf_token"}:
        abort(400)
    files = jobs.import_folder_files(app)
    if not files:
        flash(f"Im Import-Ordner ({app.config['IMPORT_DIR']}) liegt keine ZIP-Datei.", "error")
    elif jobs.busy("apple"):
        flash("Es läuft bereits ein Import.", "info")
    else:
        import_id = _new_import(get_db(), files[0].name)
        jobs.start(app, "apple", jobs.run_import, import_id, str(files[0]), False)
        flash(f"„{files[0].name}“ wird eingelesen.", "ok")
    return redirect(url_for("quellen.index") + "#apple")


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
    return redirect(url_for("quellen.index") + f"#reihenfolge-{target}")
