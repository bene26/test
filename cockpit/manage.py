"""Maintenance from the command line.

    python -m cockpit.manage passwort <benutzername>

Sets a new password and signs out all devices. In Docker, run it as the app
user so new database files keep the right owner:

    docker exec -it -u 1000:1000 projekt-cockpit python -m cockpit.manage passwort <name>
"""

import getpass
import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

from .auth import MIN_PASSWORD
from .db import connect


def reset_password(username: str) -> int:
    path = Path(os.environ.get("COCKPIT_DATA_DIR", "/data")) / "cockpit.sqlite3"
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


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "passwort":
        return reset_password(argv[1])
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
