"""Background work: Apple import, Withings and Garmin sync, nightly clean-up.

Runs as threads inside the single gunicorn worker. Each kind of job runs at most once at a
time; the hourly scheduler skips a job that is still running.
"""

import json
import logging
import threading
import time
from datetime import timedelta
from pathlib import Path

from . import apple, garmin, settings, store, util, withings
from .db import connect

log = logging.getLogger("gesundheit")
_locks = {name: threading.Lock() for name in ("withings", "garmin", "apple")}


# ---------- Connections (tokens stored encrypted) ----------

def connection(db, provider: str):
    return db.execute("SELECT * FROM connections WHERE provider = ?", (provider,)).fetchone()


def load_secret(app, db, provider: str) -> dict:
    row = connection(db, provider)
    return (app.extensions["vault"].open(row["secret_enc"]) if row else None) or {}


def save_secret(app, db, provider: str, data: dict, label: str | None = None) -> None:
    sealed = app.extensions["vault"].seal(data) if data else ""
    db.execute(
        "INSERT INTO connections (provider, secret_enc, account_label) VALUES (?, ?, ?) "
        "ON CONFLICT(provider) DO UPDATE SET secret_enc = excluded.secret_enc"
        + (", account_label = excluded.account_label" if label is not None else ""),
        (provider, sealed, label or ""))


def mark(db, provider: str, error: str = "", ok: bool = True, cursor: dict | None = None):
    stamp = util.stamp()
    db.execute(
        "UPDATE connections SET last_sync = ?, last_error = ?"
        + (", last_ok = ?" if ok else "") + (", cursor = ?" if cursor is not None else "")
        + " WHERE provider = ?",
        (stamp, error, *([stamp] if ok else []),
         *([json.dumps(cursor)] if cursor is not None else []), provider))


def disconnect(db, provider: str, keep_credentials: dict | None = None, app=None) -> None:
    if keep_credentials and app is not None:
        save_secret(app, db, provider, keep_credentials, label="")
        db.execute("UPDATE connections SET connected_at = NULL, last_error = '', cursor = '{}' "
                   "WHERE provider = ?", (provider,))
    else:
        db.execute("DELETE FROM connections WHERE provider = ?", (provider,))


def withings_credentials(app, secret: dict) -> tuple[str, str]:
    """Client ID and secret: environment first, then what was entered on the Quellen page."""
    return (app.config["WITHINGS_CLIENT_ID"] or secret.get("client_id", ""),
            app.config["WITHINGS_CLIENT_SECRET"] or secret.get("client_secret", ""))


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


def run_withings(app) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        secret = load_secret(app, conn, "withings")
        tokens = secret.get("tokens")
        if not tokens:
            return
        client_id, client_secret = withings_credentials(app, secret)

        def keep(new_tokens):
            secret["tokens"] = new_tokens
            save_secret(app, conn, "withings", secret)
            conn.commit()

        client = withings.Client(withings_http(app), tokens, client_id, client_secret, keep)
        row = connection(conn, "withings")
        cursor = json.loads(row["cursor"] or "{}") if row else {}
        try:
            cursor, counts, error = withings.sync(
                conn, client, cursor, settings.get(conn, "withings_backfill_days"),
                commit=conn.commit)
            mark(conn, "withings", error=error, ok=not error, cursor=cursor)
            log.info("Withings abgeglichen: %s", counts)
        except withings.WithingsError as exc:  # AuthExpired included
            conn.rollback()
            mark(conn, "withings", error=str(exc), ok=False)
        conn.commit()
    finally:
        conn.close()


def run_garmin(app, days: int | None = None) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        if not settings.get(conn, "garmin_enabled"):
            return
        secret = load_secret(app, conn, "garmin")
        if not secret.get("tokens"):
            return
        row = connection(conn, "garmin")
        today = util.today()
        if days:
            start_day = today - timedelta(days=days - 1)
        elif row and row["last_ok"]:
            last = util.to_date(row["last_ok"])
            start_day = max(last - timedelta(days=1), today - timedelta(days=6))
        else:
            start_day = today - timedelta(days=settings.get(conn, "garmin_backfill_days") - 1)
        try:
            api = garmin.connect(secret["tokens"])
            counts = garmin.sync(conn, api, start_day, today, commit=conn.commit)
            secret["tokens"] = garmin.dump_tokens(api)
            save_secret(app, conn, "garmin", secret)
            mark(conn, "garmin")
            log.info("Garmin abgeglichen: %s", counts)
        except garmin.GarminError as exc:
            conn.rollback()
            mark(conn, "garmin", error=str(exc), ok=False)
        conn.commit()
    finally:
        conn.close()


def run_import(app, import_id: int, path: str, delete_after: bool) -> None:
    conn = connect(app.config["DATABASE"])
    last = {"t": 0.0}

    def progress(percent):
        if time.monotonic() - last["t"] > 1 or percent >= 100:
            last["t"] = time.monotonic()
            conn.execute("UPDATE imports SET progress = ? WHERE id = ?", (percent, import_id))
            conn.commit()

    try:
        conn.execute("UPDATE imports SET status = 'laeuft' WHERE id = ?", (import_id,))
        conn.commit()
        counts = apple.import_export(conn, path, app.config["XML_MAX_MB"] * 1024 * 1024,
                                     progress)
        total = sum(v for k, v in counts.items() if k != "uebersprungen")
        message = (f"{counts['messwerte']} Messwerte, {counts['tageswerte']} Tageswerte, "
                   f"{counts['naechte']} Nächte, {counts['trainings']} Trainings")
        conn.execute("UPDATE imports SET status = 'fertig', progress = 100, finished_at = ?, "
                     "records = ?, message = ? WHERE id = ?",
                     (util.stamp(), total, message, import_id))
        conn.commit()
    except apple.AppleImportError as exc:
        conn.rollback()
        conn.execute("UPDATE imports SET status = 'fehler', finished_at = ?, message = ? "
                     "WHERE id = ?", (util.stamp(), str(exc), import_id))
        conn.commit()
    except Exception:
        conn.rollback()
        log.exception("Apple-Import fehlgeschlagen")
        conn.execute("UPDATE imports SET status = 'fehler', finished_at = ?, message = ? "
                     "WHERE id = ?", (util.stamp(), "Unerwarteter Fehler beim Einlesen.",
                                      import_id))
        conn.commit()
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


def nightly(app) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        removed = store.apply_retention(conn, settings.get(conn, "retention_days"))
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (util.stamp(),))
        conn.execute("DELETE FROM imports WHERE id NOT IN "
                     "(SELECT id FROM imports ORDER BY id DESC LIMIT 20)")
        conn.commit()
        if removed:
            log.info("Aufbewahrung: %s alte Werte gelöscht", removed)
            conn.execute("VACUUM")
    finally:
        conn.close()


def sync_all(app) -> None:
    conn = connect(app.config["DATABASE"])
    try:
        has_withings = bool(load_secret(app, conn, "withings").get("tokens"))
        has_garmin = (settings.get(conn, "garmin_enabled")
                      and bool(load_secret(app, conn, "garmin").get("tokens")))
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
