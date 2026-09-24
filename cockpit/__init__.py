"""Projekt-Cockpit: tasks, meetings, reminders and workload for project leads."""

import logging
import os
import secrets
from pathlib import Path

from flask import Flask, g, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, db, util
from .meeting_types import MEETING_TYPES

__version__ = "0.1.0"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "ja", "on")


def _secret_key(data_dir: Path) -> str:
    path = data_dir / "secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    path.chmod(0o600)
    return key


def create_app(test_config: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Flask(__name__)

    data_dir = Path(os.environ.get("COCKPIT_DATA_DIR", "/data"))
    app.config.from_mapping(
        DATA_DIR=str(data_dir),
        BASE_URL=os.environ.get("COCKPIT_BASE_URL", "").rstrip("/"),
        SECURE_COOKIES=_env_bool("COCKPIT_SECURE_COOKIES", False),
        TRUST_PROXY=_env_bool("COCKPIT_TRUST_PROXY", False),
        TIMEZONE=os.environ.get("TZ", "Europe/Berlin"),
        SCHEDULER=_env_bool("COCKPIT_SCHEDULER", True),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE"] = str(data_dir / "cockpit.sqlite3")
    app.secret_key = _secret_key(data_dir)
    app.config.update(
        SESSION_COOKIE_NAME="pc_form",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app.config["SECURE_COOKIES"],
    )
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    try:
        util.set_timezone(app.config["TIMEZONE"])
    except (ValueError, LookupError):
        logging.getLogger("cockpit").warning(
            "Unbekannte Zeitzone %r, verwende Europe/Berlin.", app.config["TIMEZONE"])
        util.set_timezone("Europe/Berlin")
    db.init_db(app.config["DATABASE"])
    auth.ensure_setup_code(app)

    app.teardown_appcontext(db.close_db)
    app.before_request(auth.load_user)
    app.before_request(auth.check_csrf)
    app.before_request(auth.require_login)

    from .views import main, meetings, projects, settings, tasks, team, workload
    for module in (auth, main, tasks, meetings, projects, team, workload, settings):
        app.register_blueprint(module.bp)

    _register_template_helpers(app)
    _register_security_headers(app)
    _register_errors(app)

    if app.config["SCHEDULER"]:
        from .reminders import start_scheduler
        start_scheduler(app)
    return app


def _register_template_helpers(app: Flask) -> None:
    app.jinja_env.filters.update(
        datum=util.fmt_date,
        datum_wt=lambda v: util.fmt_date(v, weekday=True),
        zeitpunkt=util.fmt_datetime,
        stunden=util.fmt_hours,
    )

    # Globals are visible inside imported macros too; context processors are not.
    app.jinja_env.globals.update(
        csrf_token=auth.csrf_token,
        TASK_STATUS=util.TASK_STATUS,
        PRIORITY=util.PRIORITY,
        PROJECT_STATUS=util.PROJECT_STATUS,
        CONTRACT_TYPES=util.CONTRACT_TYPES,
        MEETING_TYPES=MEETING_TYPES,
        app_version=__version__,
    )

    @app.context_processor
    def inject():
        return {"current_user": g.get("user"), "today": util.today()}


def _register_security_headers(app: Flask) -> None:
    csp = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
           "font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; "
           "base-uri 'none'; object-src 'none'")

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        if app.config["SECURE_COOKIES"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


def _register_errors(app: Flask) -> None:
    messages = {
        400: "Die Anfrage war ungültig.",
        401: "Bitte neu anmelden.",
        404: "Diese Seite gibt es nicht.",
        413: "Die Anfrage ist zu groß.",
    }

    def handler(error):
        code = getattr(error, "code", 500) or 500
        # Only show descriptions we wrote ourselves, not werkzeug's English defaults.
        text = getattr(error, "description", None)
        if code != 400 or text == getattr(type(error), "description", None):
            text = None
        if request.headers.get("X-Autosave"):
            return {"error": messages.get(code, "Fehler")}, code
        return render_template("error.html", code=code,
                               message=text or messages.get(code, "Ein Fehler ist aufgetreten.")), code

    for code in messages:
        app.register_error_handler(code, handler)

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", code=500,
                               message="Ein interner Fehler ist aufgetreten."), 500
