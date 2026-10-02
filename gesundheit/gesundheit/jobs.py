"""Background work: Apple import, Withings and Garmin sync, nightly clean-up.

Runs as threads inside the single gunicorn worker. Each kind of job runs at most once at a
time; one Withings or Garmin run goes through every person that is connected.
"""

import json
import logging
import threading
import time
from datetime import timedelta
from pathlib import Path

from . import apple, garmin, persons, settings, store, util, withings
from .db import connect, delete_meta, get_meta, set_meta

log = logging.getLogger("gesundheit")
_locks = {name: threading.Lock() for name in ("withings", "garmin", "apple")}


# ---------- Connections (tokens stored encrypted, one row per provider and person) ----------

def connection(db, provider: str, pid: int):
    return db.execute("SELECT * FROM connections WHERE provider = ? AND person_id = ?",
                      (provider, pid)).fetchone()


def load_secret(app, db, provider: str, pid: int) -> dict:
    row = connection(db, provider, pid)
    return (app.extensions["vault"].open(row["secret_enc"]) if row else None) or {}


def save_secret(app, db, provider: str, pid: int, data: dict, label: str | None = None) -> None:
    sealed = app.extensions["vault"].seal(data) if data else ""
    db.execute(
        "INSERT INTO connections (provider, person_id, secret_enc, account_label) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(provider, person_id) DO UPDATE SET "
        "secret_enc = excluded.secret_enc"
        + (", account_label = excluded.account_label" if label is not None else ""),
        (provider, pid, sealed, label or ""))


def mark(db, provider: str, pid: int, error: str = "", ok: bool = True,
         cursor: dict | None = None):
    stamp = util.stamp()
    db.execute(
        "UPDATE connections SET last_sync = ?, last_error = ?"
        + (", last_ok = ?" if ok else "") + (", cursor = ?" if cursor is not None else "")
        + " WHERE provider = ? AND person_id = ?",
        (stamp, error, *([stamp] if ok else []),
         *([json.dumps(cursor)] if cursor is not None else []), provider, pid))


def disconnect(db, provider: str, pid: int) -> None:
    db.execute("DELETE FROM connections WHERE provider = ? AND person_id = ?", (provider, pid))


def connected_persons(app, db, provider: str) -> list[int]:
    rows = db.execute("SELECT person_id, secret_enc FROM connections WHERE provider = ?",
                      (provider,)).fetchall()
    return [r["person_id"] for r in rows
            if (app.extensions["vault"].open(r["secret_enc"]) or {}).get("tokens")]


# ---------- The Withings application (one for everybody) ----------

def withings_app(app, db) -> tuple[str, str]:
    """Client ID and secret: environment first, then what was entered on the Quellen page."""
    stored = app.extensions["vault"].open(get_meta(db, "withings_app", "")) or {}
    return (app.config["WITHINGS_CLIENT_ID"] or stored.get("client_id", ""),
            app.config["WITHINGS_CLIENT_SECRET"] or stored.get("client_secret", ""))


def save_withings_app(app, db, client_id: str, client_secret: str) -> None:
    set_meta(db, "withings_app", app.extensions["vault"].seal(
        {"client_id": client_id, "client_secret": client_secret}))


def delete_withings_app(db) -> None:
    delete_meta(db, "withings_app")


def migrate_secrets(app) -> None:
    """Version 1 kept the Withings client credentials next to the tokens; move them."""
    conn = connect(app.config["DATABASE"])
    try:
        for row in conn.execute("SELECT person_id FROM connections WHERE provider = 'withings'"):
            secret = load_secret(app, conn, "withings", row["person_id"])
            if "client_id" in secret:
                if not get_meta(conn, "withings_app"):
                    save_withings_app(app, conn, secret["client_id"],
                                      secret.get("client_secret", ""))
                tokens = secret.get("tokens")
                save_secret(app, conn, "withings", row["person_id"],
                            {"tokens": tokens} if tokens else {})
        conn.commit()
    finally:
        conn.close()


def withings_http(app):
    if "withings_http" in app.extensions:  # tests
        return app.extensions["withings_http"]
    import requests
    session = requests.Session()
    session.headers["User-Agent"] = "Gesundheits-Cockpit"
    return session


# ---------- Jobs ----------

def busy(name: str) -> bool:
    return _locks[name].locked()


def start(app, name: str, target, *args) -> bool:
    """Run target(app, *args) in the background. False if that job is already running."""
    lock = _locks[name]
    if not lock.acquire(blocking=False):
        return False

    def run():
        try:
            target(app, *args)
        except Exception:
            log.exception("Hintergrundaufgabe %s fehlgeschlagen", name)
        finally:
            lock.release()

    if app.config.get("BACKGROUND_JOBS", True):
        threading.Thread(target=run, name=f"job-{name}", daemon=True).start()
    else:  # tests: run right away
        run()
    return True


def run_withings(app, pid: int | None = None) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        client_id, client_secret = withings_app(app, conn)
        targets = [pid] if pid else connected_persons(app, conn, "withings")
        for person_id in targets:
            _withings_person(app, conn, person_id, client_id, client_secret)
    finally:
        conn.close()


def _withings_person(app, conn, pid, client_id, client_secret):
    secret = load_secret(app, conn, "withings", pid)
    if not secret.get("tokens"):
        return

    def keep(new_tokens):
        secret["tokens"] = new_tokens
        save_secret(app, conn, "withings", pid, secret)
        conn.commit()

    client = withings.Client(withings_http(app), secret["tokens"], client_id, client_secret, keep)
    row = connection(conn, "withings", pid)
    cursor = json.loads(row["cursor"] or "{}") if row else {}
    try:
        cursor, counts, error = withings.sync(
            conn, pid, client, cursor, settings.get(conn, "withings_backfill_days"),
            commit=conn.commit)
        mark(conn, "withings", pid, error=error, ok=not error, cursor=cursor)
        log.info("Withings abgeglichen (Person %s): %s", pid, counts)
    except withings.WithingsError as exc:  # AuthExpired included
        conn.rollback()
        mark(conn, "withings", pid, error=str(exc), ok=False)
    conn.commit()


def run_garmin(app, pid: int | None = None, days: int | None = None) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        targets = [pid] if pid else connected_persons(app, conn, "garmin")
        for person_id in targets:
            _garmin_person(app, conn, person_id, days)
    finally:
        conn.close()


def _garmin_person(app, conn, pid, days):
    person = persons.get(conn, pid)
    if not person or not person["garmin_enabled"]:
        return
    secret = load_secret(app, conn, "garmin", pid)
    if not secret.get("tokens"):
        return
    row = connection(conn, "garmin", pid)
    today = util.today()
    if days:
        start_day = today - timedelta(days=days - 1)
    elif row and row["last_ok"]:
        last = util.to_date(row["last_ok"])
        start_day = max(last - timedelta(days=1), today - timedelta(days=6))
    else:
        start_day = today - timedelta(days=person["garmin_backfill_days"] - 1)
    try:
        api = garmin.connect(secret["tokens"])
        counts = garmin.sync(conn, pid, api, start_day, today, commit=conn.commit)
        secret["tokens"] = garmin.dump_tokens(api)
        save_secret(app, conn, "garmin", pid, secret)
        mark(conn, "garmin", pid)
        log.info("Garmin abgeglichen (Person %s): %s", pid, counts)
    except garmin.GarminError as exc:
        conn.rollback()
        mark(conn, "garmin", pid, error=str(exc), ok=False)
    conn.commit()


def run_import(app, import_id: int, pid: int, path: str, delete_after: bool) -> None:
    conn = connect(app.config["DATABASE"])
    last = {"t": 0.0}

    def progress(percent):
        if time.monotonic() - last["t"] > 1 or percent >= 100:
            last["t"] = time.monotonic()
            conn.execute("UPDATE imports SET progress = ? WHERE id = ?", (percent, import_id))
            conn.commit()

    def finish(status, message, records=0):
        conn.execute("UPDATE imports SET status = ?, finished_at = ?, message = ?, records = ?"
                     + (", progress = 100" if status == "fertig" else "") + " WHERE id = ?",
                     (status, util.stamp(), message, records, import_id))
        conn.commit()

    try:
        conn.execute("UPDATE imports SET status = 'laeuft' WHERE id = ?", (import_id,))
        conn.commit()
        counts = apple.import_export(conn, pid, path, app.config["XML_MAX_MB"] * 1024 * 1024,
                                     progress)
        total = sum(v for k, v in counts.items() if k != "uebersprungen")
        finish("fertig", f"{counts['messwerte']} Messwerte, {counts['tageswerte']} Tageswerte, "
                         f"{counts['naechte']} Nächte, {counts['trainings']} Trainings", total)
    except apple.AppleImportError as exc:
        conn.rollback()
        finish("fehler", str(exc))
    except Exception:
        conn.rollback()
        log.exception("Apple-Import fehlgeschlagen")
        finish("fehler", "Unerwarteter Fehler beim Einlesen.")
    finally:
        conn.close()
        if delete_after:
            Path(path).unlink(missing_ok=True)


def import_folder_files(app) -> list[Path]:
    """ZIP files directly in the import folder (no subfolders, no links), newest first."""
    folder = Path(app.config["IMPORT_DIR"])
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir()
             if p.suffix.lower() == ".zip" and p.is_file() and not p.is_symlink()]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def recover(app) -> None:
    """After a restart: imports that were running are marked as interrupted."""
    conn = connect(app.config["DATABASE"])
    try:
        conn.execute("UPDATE imports SET status = 'fehler', finished_at = ?, message = "
                     "'Unterbrochen (Neustart). Bitte die Datei noch einmal hochladen.' "
                     "WHERE status IN ('wartet', 'laeuft')", (util.stamp(),))
        conn.commit()
    finally:
        conn.close()
    for leftover in Path(app.config["UPLOAD_DIR"]).glob("import-*.zip"):
        leftover.unlink(missing_ok=True)
    migrate_secrets(app)


def nightly(app) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        removed = store.apply_retention(conn, settings.get(conn, "retention_days"))
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (util.stamp(),))
        conn.execute("DELETE FROM imports WHERE id NOT IN "
                     "(SELECT id FROM imports ORDER BY id DESC LIMIT 50)")
        conn.commit()
        if removed:
            log.info("Aufbewahrung: %s alte Werte gelöscht", removed)
            conn.execute("VACUUM")
    finally:
        conn.close()


def sync_all(app) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        has_withings = bool(connected_persons(app, conn, "withings"))
        has_garmin = bool(connected_persons(app, conn, "garmin"))
    finally:
        conn.close()
    if has_withings:
        start(app, "withings", run_withings)
    if has_garmin:
        start(app, "garmin", run_garmin)


def start_scheduler(app) -> None:
    def loop():
        next_sync = time.monotonic() + 60
        cleaned = None
        while True:
            time.sleep(30)
            try:
                if time.monotonic() >= next_sync:
                    next_sync = time.monotonic() + app.config["SYNC_MINUTES"] * 60
                    sync_all(app)
                now = util.now()
                if now.hour == 3 and cleaned != now.date():
                    cleaned = now.date()
                    nightly(app)
            except Exception:
                log.exception("Zeitplan: Fehler im Durchlauf")

    threading.Thread(target=loop, name="zeitplan", daemon=True).start()
