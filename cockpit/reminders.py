"""Background jobs: reminders, daily backup and session cleanup.

A single thread checks every 30 seconds which jobs are due. Each job runs at
most once per key (e.g. per day), recorded in reminder_log. A file lock makes
sure only one process runs the scheduler even with several workers.
"""

import fcntl
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import data, notify, util
from .db import connect

log = logging.getLogger("cockpit")

# A job that was missed (e.g. NAS asleep) still runs within this window.
CATCH_UP = timedelta(hours=3)
BACKUP_KEEP = 14

_lock_handle = None


def start_scheduler(app) -> None:
    global _lock_handle
    lock_path = Path(app.config["DATA_DIR"]) / "scheduler.lock"
    handle = open(lock_path, "w")  # noqa: SIM115 (kept open for the process lifetime)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return
    _lock_handle = handle
    thread = threading.Thread(target=_loop, args=(app,), name="scheduler", daemon=True)
    thread.start()


def _loop(app) -> None:
    while True:
        try:
            run_due_jobs(app.config, util.now())
        except Exception:
            log.exception("Fehler im Erinnerungs-Dienst")
        time.sleep(30)


def _at(day, hhmm: str) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute)


def _claim(db, key: str, now: datetime) -> bool:
    """Record that a job ran; False if it already ran."""
    try:
        db.execute("INSERT INTO reminder_log (key, sent_at) VALUES (?, ?)", (key, util.stamp(now)))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def _due(now: datetime, hhmm: str) -> bool:
    start = _at(now.date(), hhmm)
    return start <= now < start + CATCH_UP


def run_due_jobs(config, now: datetime) -> list[str]:
    """Run every job that is due at `now`. Returns the keys of jobs that ran."""
    db = connect(config["DATABASE"])
    ran = []
    try:
        s = data.settings(db)
        today = now.date()
        link = config.get("BASE_URL", "")

        if not (Path(config["DATA_DIR"]) / "backups" / f"cockpit-{today}.sqlite3").exists() \
                and now.hour >= 2:
            backup(db, Path(config["DATA_DIR"]), today)
            ran.append(f"backup:{today}")
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (util.stamp(now),))
            db.execute("DELETE FROM reminder_log WHERE sent_at < ?",
                       (util.stamp(now - timedelta(days=90)),))
            db.commit()

        if s["reminders_enabled"] != "1" or not util.is_workday(today):
            return ran

        stale_days = int(s["stale_days"])

        if _due(now, s["digest_time"]):
            key = f"digest:{today}"
            c = data.counts(db, now, stale_days)
            parts = [label for label, value in (
                (f"{c['overdue']} überfällig", c["overdue"]),
                (f"{c['due_today']} heute fällig", c["due_today"]),
                (f"{c['stale']} ohne Update seit {stale_days} Tagen", c["stale"]),
                (f"{c['missing_protocols']} Protokoll(e) fehlen", c["missing_protocols"]),
                (f"{c['meetings_today']} Meeting(s) heute", c["meetings_today"]),
            ) if value]
            if parts and _claim(db, key, now):
                notify.remind("Guten Morgen", "Aufgaben: " + " · ".join(parts), link)
                ran.append(key)

        for routine in data.due_routines(db, today):
            key = f"routine:{routine['key']}:{routine['period']}:{today}"
            if _due(now, s[routine["time_setting"]]) and _claim(db, key, now):
                notify.remind(routine["label"],
                              f"{routine['label']} steht an (ca. {routine['minutes']} Minuten).",
                              link)
                ran.append(key)

        if _due(now, s["prep_time"]):
            next_day = util.next_workday(today)
            meetings = data.meetings_between(db, today + timedelta(days=1), next_day)
            key = f"prep:{today}"
            if meetings and _claim(db, key, now):
                when = "Morgen" if next_day == today + timedelta(days=1) else "Am nächsten Arbeitstag"
                notify.remind("Meetings vorbereiten",
                              f"{when}: {len(meetings)} Meeting(s). Agenden prüfen.", link)
                ran.append(key)
    finally:
        db.close()
    return ran


def backup(db, data_dir: Path, today) -> Path:
    folder = data_dir / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / f"cockpit-{today}.sqlite3"
    tmp = target.with_suffix(".tmp")
    dest = sqlite3.connect(tmp)
    try:
        db.backup(dest)
    finally:
        dest.close()
    tmp.replace(target)
    target.chmod(0o600)
    for old in sorted(folder.glob("cockpit-*.sqlite3"))[:-BACKUP_KEEP]:
        old.unlink()
    log.info("Sicherung erstellt: %s", target.name)
    return target
