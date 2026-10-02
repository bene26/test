"""Encryption of tokens and client secrets at rest (Fernet: AES-128-CBC + HMAC-SHA256).

The key comes from GESUNDHEIT_KEY or from the file `schluessel` in the data folder, which
is created on first start with permissions 600. Losing the key only means connecting Withings
and Garmin again; the health data itself is not encrypted with it.
"""

import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KEY_FILE = "schluessel"
log = logging.getLogger("gesundheit")


class Vault:
    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    def seal(self, data: dict) -> str:
        return self._fernet.encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()

    def open(self, token: str) -> dict | None:
        """Decrypted dict, or None if empty, tampered with or sealed with another key."""
        if not token:
            return None
        try:
            data = json.loads(self._fernet.decrypt(token.encode()))
        except (InvalidToken, ValueError):
            log.warning("Gespeicherte Zugangsdaten lassen sich nicht entschlüsseln "
                        "(anderer Schlüssel?). Bitte die Verbindung neu herstellen.")
            return None
        return data if isinstance(data, dict) else None


def load_key(data_dir: Path) -> bytes:
    env = os.environ.get("GESUNDHEIT_KEY", "").strip()
    if env:
        key = env.encode()
        Fernet(key)  # raises ValueError for a malformed key, before anything is stored
        return key
    path = Path(data_dir) / KEY_FILE
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.write_bytes(key + b"\n")
    path.chmod(0o600)
    return key
