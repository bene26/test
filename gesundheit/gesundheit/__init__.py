"""Gesundheits-Cockpit: Withings, Garmin and Apple Health in one place, on your own NAS."""

import logging
import os
import secrets
import tempfile
from pathlib import Path

from flask import Blueprint, Flask, g, render_template, request
from flask import Request as FlaskRequest
from jinja2 import ChoiceLoader, FileSystemLoader, TemplateNotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auswertung, auth, crypto, db, katalog, persons, themes, util

__version__ = "0.2.0"
APP_NAME = "Gesundheits-Cockpit"
log = logging.getLogger("gesundheit")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "ja", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _secret_key(data_dir: Path) -> str:
    path = data_dir / "secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    path.chmod(0o600)
    return key


def shared_dir() -> Path:
    """Design shared with the Projekt-Cockpit: app.css, app.js, komponenten.js, fonts and the
    error page graphics. In Docker it is copied to /app/shared, in the repository it is the
    cockpit folder next to this app."""
    here = Path(__file__).resolve()
    candidates = [Path(os.environ["GESUNDHEIT_SHARED_DIR"])] if os.environ.get(
        "GESUNDHEIT_SHARED_DIR") else []
    candidates += [here.parent.parent / "shared", here.parents[2] / "cockpit"]
    for candidate in candidates:
        if (candidate / "static" / "app.css").is_file():
            return candidate
    raise RuntimeError("Gemeinsames Design (app.css) nicht gefunden. GESUNDHEIT_SHARED_DIR setzen.")


class _SharedTemplates(FileSystemLoader):
    """Only the error page graphics come from the cockpit; everything else is our own."""
    ALLOWED = ("_grafiken.html",)

    def get_source(self, environment, template):
        if template not in self.ALLOWED:
            raise TemplateNotFound(template)
        return super().get_source(environment, template)

    def list_templates(self):
        return list(self.ALLOWED)


class UploadRequest(FlaskRequest):
    """Large uploads (Apple Health export) go to the data folder, not to RAM or /tmp.

    The temporary file keeps a name so the upload view can move it without copying.
    Leftovers are removed after the request (see _cleanup_uploads).
    """

    def _get_file_stream(self, total_content_length, content_type, filename=None,
                         content_length=None):
        from flask import current_app
        folder = Path(current_app.config["UPLOAD_DIR"])
        handle = tempfile.NamedTemporaryFile(dir=folder, prefix="upload-", suffix=".part",
                                             delete=False)
        g.setdefault("upload_parts", []).append(handle.name)
        return handle


def create_app(test_config: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Flask(__name__)
    app.request_class = UploadRequest

    data_dir = Path(os.environ.get("GESUNDHEIT_DATA_DIR", "/data"))
    app.config.from_mapping(
        DATA_DIR=str(data_dir),
        BASE_URL=os.environ.get("GESUNDHEIT_BASE_URL", "").rstrip("/"),
        SECURE_COOKIES=_env_bool("GESUNDHEIT_SECURE_COOKIES", False),
        TRUST_PROXY=_env_bool("GESUNDHEIT_TRUST_PROXY", False),
        TIMEZONE=os.environ.get("TZ", "Europe/Berlin"),
        SCHEDULER=_env_bool("GESUNDHEIT_SCHEDULER", True),
        SYNC_MINUTES=max(15, _env_int("GESUNDHEIT_SYNC_MINUTES", 60)),
        UPLOAD_MAX_MB=max(1, _env_int("GESUNDHEIT_UPLOAD_MAX_MB", 2048)),
        XML_MAX_MB=max(1, _env_int("GESUNDHEIT_XML_MAX_MB", 30 * 1024)),
        IMPORT_DIR=os.environ.get("GESUNDHEIT_IMPORT_DIR", "/import"),
        WITHINGS_CLIENT_ID=os.environ.get("WITHINGS_CLIENT_ID", "").strip(),
        WITHINGS_CLIENT_SECRET=os.environ.get("WITHINGS_CLIENT_SECRET", "").strip(),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        BACKGROUND_JOBS=True,
    )
    if test_config:
        app.config.update(test_config)

    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = data_dir / "uploads"
    upload_dir.mkdir(exist_ok=True)
    for stale in upload_dir.glob("upload-*.part"):
        stale.unlink(missing_ok=True)
    app.config["UPLOAD_DIR"] = str(upload_dir)
    app.config["DATABASE"] = str(data_dir / "gesundheit.sqlite3")
    app.secret_key = _secret_key(data_dir)
    app.extensions["vault"] = crypto.Vault(crypto.load_key(data_dir))
    app.config.update(
        SESSION_COOKIE_NAME="gs_form",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app.config["SECURE_COOKIES"],
    )
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    try:
        util.set_timezone(app.config["TIMEZONE"])
    except (ValueError, LookupError):
        log.warning("Unbekannte Zeitzone %r, verwende Europe/Berlin.", app.config["TIMEZONE"])
        util.set_timezone("Europe/Berlin")
    db.init_db(app.config["DATABASE"])
    auth.ensure_setup_code(app)

    shared = shared_dir()
    app.register_blueprint(Blueprint("shared", __name__, static_folder=str(shared / "static"),
                                     static_url_path="/gemeinsam"))
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(Path(__file__).parent / "templates")),
                                     _SharedTemplates(str(shared / "templates"))])

    app.teardown_appcontext(db.close_db)
    app.teardown_request(_cleanup_uploads)
    app.before_request(auth.load_user)
    app.before_request(_upload_limit)
    app.before_request(auth.check_csrf)
    app.before_request(auth.require_login)
    app.before_request(persons.load_current)
    app.after_request(persons.remember)

    from .views import (auswertungen, berichte, bereiche, daten, einstellungen, main, personen,
                        quellen, vergleich)
    for module in (auth, main, bereiche, auswertungen, vergleich, berichte, personen, quellen,
                   einstellungen, daten):
        app.register_blueprint(module.bp)

    _register_template_helpers(app)
    _register_security_headers(app)
    _register_errors(app)

    from . import jobs
    jobs.recover(app)
    if app.config["SCHEDULER"]:
        jobs.start_scheduler(app)
    return app


def _upload_limit():
    # Before the CSRF check reads the form: the Apple export may be large. Only for a
    # logged-in user, so nobody else can make the app write gigabytes to the disk.
    if request.endpoint == "quellen.apple_upload" and g.get("user"):
        from flask import current_app
        request.max_content_length = current_app.config["UPLOAD_MAX_MB"] * 1024 * 1024


def _cleanup_uploads(_exc=None):
    for name in g.pop("upload_parts", []):
        Path(name).unlink(missing_ok=True)


def _register_template_helpers(app: Flask) -> None:
    app.jinja_env.filters.update(
        datum=util.fmt_date,
        datum_wt=lambda v: util.fmt_date(v, weekday=True),
        tag=util.fmt_day,
        zeitpunkt=util.fmt_datetime,
        uhrzeit=util.fmt_time,
        vor=util.fmt_ago,
        zahl=util.fmt_num,
        dauer=util.fmt_minutes,
        delta=util.fmt_signed,
        quelle=katalog.source_label,
        quelle_kurz=lambda v: katalog.source_label(v, short=True),
        kuerzel=persons.initials,
        prozent=lambda v: "–" if v is None else f"{util.fmt_signed(v, 0)} %",
    )
    app.jinja_env.globals.update(
        csrf_token=auth.csrf_token,
        THEMES=themes.THEMES,
        APPEARANCE=themes.APPEARANCE,
        METRICS=katalog.METRICS,
        SOURCES=katalog.SOURCES,
        FAMILIES=katalog.FAMILIES,
        PERSON_COLORS=persons.COLORS,
        KEYS=auswertung.KEYS,
        WORKOUT_KINDS=katalog.WORKOUT_KINDS,
        nav_status=_nav_status,
        app_version=__version__,
        app_name=APP_NAME,
    )

    @app.context_processor
    def inject():
        theme = themes.current()
        look = themes.current_look()
        return {"current_user": g.get("user"), "today": util.today(), "theme": theme,
                "look": look, "html_attrs": themes.html_attrs(theme, look),
                "person": g.get("person"), "persons": g.get("persons", [])}

    app.after_request(themes.remember)


def _nav_status() -> int:
    """Number of connections whose last sync failed (badge at "Quellen")."""
    if "nav_status" not in g:
        g.nav_status = db.get_db().execute(
            "SELECT COUNT(*) FROM connections WHERE last_error != ''").fetchone()[0]
    return g.nav_status


def _register_security_headers(app: Flask) -> None:
    csp = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
           "font-src 'self'; connect-src 'self'; form-action 'self' https://account.withings.com; "
           "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.endpoint not in ("static", "shared.static"):
            response.headers["Cache-Control"] = "no-store"
        if app.config["SECURE_COOKIES"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


# Error pages: title, short label for the graphics (capitals) and explanation per status.
ERRORS = {
    400: ("Das hat nicht geklappt", "UNGÜLTIG", "Die Anfrage war ungültig."),
    401: ("Bitte neu anmelden", "BITTE ANMELDEN", "Bitte neu anmelden."),
    403: ("Kein Zutritt", "KEIN ZUTRITT", "Dafür fehlt die Berechtigung."),
    404: ("Seite nicht gefunden", "NICHT GEFUNDEN",
          "Diese Seite gibt es nicht (mehr). Vielleicht ist der Link falsch geschrieben."),
    405: ("So geht das nicht", "NICHT ERLAUBT", "Diese Adresse lässt sich so nicht aufrufen."),
    413: ("Zu groß", "ZU GROSS", "Die Datei oder Anfrage ist zu groß."),
    500: ("Etwas ist schiefgelaufen", "STÖRUNG",
          "Ein interner Fehler ist aufgetreten. Bitte die Seite neu laden oder später noch "
          "einmal versuchen."),
}


def _register_errors(app: Flask) -> None:
    def wants_json() -> bool:
        if request.headers.get("X-Gesundheit-Ajax"):
            return True
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        return best == "application/json"

    def page(code: int, text: str | None = None):
        title, kurz, message = ERRORS.get(code, ERRORS[500])
        message = text or message
        if wants_json():
            return {"ok": False, "error": message, "nachricht": message}, code
        if g.get("user") and not g.get("person"):  # error before persons were loaded (CSRF, 413)
            try:
                persons.load_current()
            except Exception:
                g.user = None
        return render_template("error.html", code=code, title=title, kurz=kurz, message=message,
                               path=request.path[:200],
                               now_time=util.now().strftime("%H:%M")), code

    def handler(error):
        code = getattr(error, "code", 500) or 500
        # Only show descriptions we wrote ourselves, not werkzeug's English defaults.
        text = getattr(error, "description", None)
        if code != 400 or text == getattr(type(error), "description", None):
            text = None
        if code == 413:
            text = (f"Die Datei ist zu groß (höchstens {app.config['UPLOAD_MAX_MB']} MB). Große "
                    "Exporte stattdessen in den Import-Ordner legen.")
        return page(code if code in ERRORS else 500, text)

    for code in ERRORS:
        if code != 500:
            app.register_error_handler(code, handler)

    @app.errorhandler(500)
    def server_error(_error):
        try:
            return page(500)
        except Exception:  # the error page itself failed (e.g. database): plain text, no details
            return ("Etwas ist schiefgelaufen. Bitte die Seite neu laden oder später noch "
                    "einmal versuchen."), 500, {"Content-Type": "text/plain; charset=utf-8"}
