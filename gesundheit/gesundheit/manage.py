"""Maintenance from the command line.

    python -m gesundheit.manage passwort <benutzername>
    python -m gesundheit.manage sicherung [anzahl]

"passwort" sets a new password and signs out all devices. In Docker, run it as the app
user so new database files keep the right owner:

    docker exec -it -u 1000:1000 gesundheits-cockpit python -m gesundheit.manage passwort <name>

"sicherung" writes a consistent copy of the database to <Datenordner>/sicherungen (SQLite
backup, safe while the app runs) and keeps the newest copies (default 10). The deploy script
runs it before every update.
"""

import getpass
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

from .auth import MIN_PASSWORD
from .db import connect


def reset_password(username: str) -> int:
    path = Path(os.environ.get("GESUNDHEIT_DATA_DIR", "/data")) / "gesundheit.sqlite3"
    if not path.exists():
        print(f"Keine Datenbank unter {path} gefunden.", file=sys.stderr)
        return 1
    db = connect(path)
    try:
        user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            names = ", ".join(r[0] for r in db.execute("SELECT username FROM users"))
            print(f"Benutzer „{username}“ gibt es nicht. Vorhanden: {names or '–'}",
                  file=sys.stderr)
            return 1
        password = getpass.getpass("Neues Passwort: ")
        if len(password) < MIN_PASSWORD:
            print(f"Mindestens {MIN_PASSWORD} Zeichen.", file=sys.stderr)
            return 1
        if password != getpass.getpass("Wiederholen: "):
            print("Die Passwörter stimmen nicht überein.", file=sys.stderr)
            return 1
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(password), user["id"]))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        db.commit()
    finally:
        db.close()
    print("Passwort geändert. Alle Geräte wurden abgemeldet.")
    return 0


def backup(keep: int = 10) -> int:
    data_dir = Path(os.environ.get("GESUNDHEIT_DATA_DIR", "/data"))
    path = data_dir / "gesundheit.sqlite3"
    if not path.exists():
        print(f"Keine Datenbank unter {path} gefunden, nichts zu sichern.")
        return 0
    target_dir = data_dir / "sicherungen"
    target_dir.mkdir(mode=0o700, exist_ok=True)
    target = target_dir / f"gesundheit-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    source = sqlite3.connect(path)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    os.chmod(target, 0o600)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        # run as root (docker exec): hand the files to the owner of the data folder
        owner = data_dir.stat()
        for item in (target_dir, target):
            os.chown(item, owner.st_uid, owner.st_gid)
    copies = sorted(target_dir.glob("gesundheit-*.sqlite3"))
    for old in copies[:-keep] if keep > 0 else []:
        old.unlink()
    print(f"Sicherung: {target} ({min(len(copies), keep)} Sicherungen vorhanden)")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "passwort":
        return reset_password(argv[1])
    if argv and argv[0] == "sicherung" and len(argv) <= 2:
        if len(argv) == 2 and not argv[1].isdigit():
            print("Anzahl muss eine Zahl sein.", file=sys.stderr)
            return 2
        return backup(int(argv[1]) if len(argv) == 2 else 10)
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
