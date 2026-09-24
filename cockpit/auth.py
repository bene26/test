"""Setup, login, server-side sessions, CSRF protection and login throttling."""

import hashlib
import hmac
import logging
import secrets
import threading
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import forms, util
from .db import delete_meta, get_db, get_meta, set_meta

bp = Blueprint("auth", __name__)
log = logging.getLogger("cockpit")

SESSION_COOKIE = "pc_session"
SHORT_SESSION = timedelta(hours=12)
LONG_SESSION = timedelta(days=30)
MIN_PASSWORD = 12
SETUP_FILE = "EINRICHTUNGSCODE.txt"

# Endpoints reachable without login.
PUBLIC_ENDPOINTS = {"auth.login", "auth.setup", "static", "main.health"}


class LoginThrottle:
    """At most `limit` failures per key within `window` seconds."""

    def __init__(self, limit=5, window=15 * 60):
        self.limit = limit
        self.window = window
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key, now):
        stamps = [t for t in self._failures.get(key, []) if now - t < self.window]
        self._failures[key] = stamps
        return stamps

    def blocked(self, key) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.limit

    def fail(self, key) -> None:
        with self._lock:
            now = time.monotonic()
            self._recent(key, now).append(now)

    def reset(self, key) -> None:
        with self._lock:
            self._failures.pop(key, None)


throttle = LoginThrottle()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_count(db) -> int:
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def ensure_setup_code(app) -> None:
    """Before the first account exists, a one-time code must be entered.

    The code is written to the container log and to a file in the data
    folder, so only someone with access to the NAS can claim the account.
    """
    from .db import connect

    conn = connect(app.config["DATABASE"])
    try:
        if user_count(conn):
            return
        code = get_meta(conn, "setup_code")
        if not code:
            code = "-".join(secrets.token_hex(3).upper() for _ in range(3))
            set_meta(conn, "setup_code", code)
            conn.commit()
    finally:
        conn.close()
    path = Path(app.config["DATA_DIR"]) / SETUP_FILE
    path.write_text(
        f"Einrichtungscode für das Projekt-Cockpit: {code}\n"
        "Diese Datei wird nach der Einrichtung automatisch gelöscht.\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    log.warning("Noch kein Konto eingerichtet. Einrichtungscode: %s", code)


def create_session(db, user_id: int, remember: bool) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    lifetime = LONG_SESSION if remember else SHORT_SESSION
    now = util.now()
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (_hash_token(token), user_id, secrets.token_urlsafe(32),
         util.stamp(now), util.stamp(now + lifetime)),
    )
    return token, int(lifetime.total_seconds()) if remember else None


def _set_session_cookie(response, token, max_age):
    response.set_cookie(
        SESSION_COOKIE, token, max_age=max_age, httponly=True, samesite="Lax",
        secure=current_app.config["SECURE_COOKIES"], path="/",
    )
    return response


def load_user():
    g.user = None
    g.csrf_token = None
    g.session_hash = None
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 100:
        return
    row = get_db().execute(
        "SELECT s.token_hash, s.csrf_token, u.id, u.username FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
        (_hash_token(token), util.stamp()),
    ).fetchone()
    if row:
        g.user = {"id": row["id"], "username": row["username"]}
        g.csrf_token = row["csrf_token"]
        g.session_hash = row["token_hash"]


def csrf_token() -> str:
    """Token for the current form: per session when logged in, else per browser."""
    if g.get("csrf_token"):
        return g.csrf_token
    if "anon_csrf" not in session:
        session["anon_csrf"] = secrets.token_urlsafe(32)
    return session["anon_csrf"]


def check_csrf():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = g.csrf_token if g.get("user") else session.get("anon_csrf")
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Das Formular ist abgelaufen. Bitte Seite neu laden.")


def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if g.user:
        return None
    if user_count(get_db()) == 0:
        return redirect(url_for("auth.setup"))
    if request.headers.get("X-Autosave"):
        abort(401)
    target = request.full_path if request.method == "GET" else None
    return redirect(url_for("auth.login", next=target))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def _client_key() -> str:
    return request.remote_addr or "unknown"


@bp.route("/einrichten", methods=["GET", "POST"])
def setup():
    db = get_db()
    if user_count(db):
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        key = "setup:" + _client_key()
        if throttle.blocked(key):
            flash("Zu viele Fehlversuche. Bitte 15 Minuten warten.", "error")
            return redirect(url_for("auth.setup"))
        try:
            data = forms.parse(request.form, {
                "code": forms.Text("Einrichtungscode", required=True, max_len=40),
                "username": forms.Text("Benutzername", required=True, max_len=60),
                "password": forms.Text("Passwort", required=True, max_len=200),
                "password2": forms.Text("Passwort wiederholen", required=True, max_len=200),
            })
            expected = get_meta(db, "setup_code", "")
            if not expected or not hmac.compare_digest(
                    data["code"].strip().upper(), expected):
                throttle.fail(key)
                raise forms.ValidationError("Der Einrichtungscode stimmt nicht.")
            _check_new_password(data["password"], data["password2"])
        except forms.ValidationError as exc:
            flash(str(exc), "error")
            return redirect(url_for("auth.setup"))
        db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (data["username"], generate_password_hash(data["password"]), util.stamp()),
        )
        delete_meta(db, "setup_code")
        user_id = db.execute("SELECT id FROM users WHERE username = ?",
                             (data["username"],)).fetchone()["id"]
        token, max_age = create_session(db, user_id, remember=False)
        db.commit()
        (Path(current_app.config["DATA_DIR"]) / SETUP_FILE).unlink(missing_ok=True)
        log.info("Konto eingerichtet.")
        flash("Konto eingerichtet. Willkommen!", "ok")
        return _set_session_cookie(redirect(url_for("main.dashboard")), token, max_age)
    return render_template("auth/setup.html")


@bp.route("/anmelden", methods=["GET", "POST"])
def login():
    db = get_db()
    if user_count(db) == 0:
        return redirect(url_for("auth.setup"))
    if g.user:
        return redirect(url_for("main.dashboard"))
    next_url = util.safe_next(request.values.get("next"), url_for("main.dashboard"))
    if request.method == "POST":
        key = "login:" + _client_key()
        if throttle.blocked(key):
            flash("Zu viele Fehlversuche. Bitte 15 Minuten warten.", "error")
            return redirect(url_for("auth.login"))
        try:
            data = forms.parse(request.form, {
                "username": forms.Text("Benutzername", required=True, max_len=60),
                "password": forms.Text("Passwort", required=True, max_len=200),
                "remember": forms.Checkbox("Angemeldet bleiben"),
            })
        except forms.ValidationError as exc:
            flash(str(exc), "error")
            return redirect(url_for("auth.login"))
        user = db.execute("SELECT id, password_hash FROM users WHERE username = ?",
                          (data["username"],)).fetchone()
        # Always run a hash check so timing does not reveal valid usernames.
        stored = user["password_hash"] if user else _DUMMY_HASH
        if not check_password_hash(stored, data["password"]) or not user:
            throttle.fail(key)
            time.sleep(0.5)
            flash("Benutzername oder Passwort ist falsch.", "error")
            return redirect(url_for("auth.login", next=request.form.get("next")))
        throttle.reset(key)
        token, max_age = create_session(db, user["id"], data["remember"])
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (util.stamp(),))
        db.commit()
        return _set_session_cookie(redirect(next_url), token, max_age)
    return render_template("auth/login.html", next_url=request.args.get("next", ""))


@bp.route("/abmelden", methods=["POST"])
def logout():
    if g.session_hash:
        db = get_db()
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (g.session_hash,))
        db.commit()
    response = redirect(url_for("auth.login"))
    response.delete_cookie(SESSION_COOKIE, path="/")
    flash("Abgemeldet.", "ok")
    return response


def change_password(db, user_id, current, new, new2):
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], current):
        raise forms.ValidationError("Das aktuelle Passwort stimmt nicht.")
    _check_new_password(new, new2)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
               (generate_password_hash(new), user_id))
    # Sign out every other device.
    db.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
               (user_id, g.session_hash))


def _check_new_password(password, repeat):
    if len(password) < MIN_PASSWORD:
        raise forms.ValidationError(
            f"Das Passwort muss mindestens {MIN_PASSWORD} Zeichen lang sein.")
    if password != repeat:
        raise forms.ValidationError("Die Passwörter stimmen nicht überein.")


_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(16))
