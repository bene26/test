"""Selectable designs.

The key is stored per user (users.theme) and rendered as data-theme on <html>.
All colours, fonts and layout differences live in static/app.css. A cookie
remembers the last design so the login page looks the same as the app.
"""

from flask import current_app, g, has_request_context, request

COOKIE = "pc_theme"
DEFAULT = "glas"

# Order is the order on the settings page.
THEMES = {
    "violett": {
        "label": "Violett",
        "description": "Dunkles Lila, Zahlen wie auf einer Abfahrtstafel, Seitenleiste",
    },
    "glas": {
        "label": "Glas und Orange",
        "description": "Dunkles Glas, orange Akzente, schwebende Seitenleiste",
    },
    "bronze": {
        "label": "Bronze",
        "description": "Schwarz und Bronze, abgeschrägte Ecken, Menü oben",
    },
    "hell": {
        "label": "Hell",
        "description": "Mattes Glas auf Pastell, schmale Symbolleiste",
    },
    "schlicht": {
        "label": "Schlicht",
        "description": "Das bisherige ruhige Design, folgt Hell und Dunkel des Geräts",
    },
}


def resolve(value) -> str:
    return value if value in THEMES else DEFAULT


def current() -> str:
    if not has_request_context():
        return DEFAULT
    user = g.get("user")
    if user and user.get("theme") in THEMES:
        return user["theme"]
    return resolve(request.cookies.get(COOKIE))


def remember(response):
    """Keep the cookie in step with the logged-in user's choice."""
    user = g.get("user")
    if request.endpoint == "static" or not user or user.get("theme") not in THEMES:
        return response
    if request.cookies.get(COOKIE) != user["theme"]:
        response.set_cookie(
            COOKIE, user["theme"], max_age=365 * 24 * 3600, httponly=True, samesite="Lax",
            secure=current_app.config["SECURE_COOKIES"], path="/",
        )
    return response
