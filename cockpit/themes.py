"""Selectable designs and appearance options.

The design is stored per user (users.theme), the finer options (light or dark,
accent colour, text size, corners, menu style) as JSON in users.appearance.
Everything ends up as data-* attributes on <html>; all colours, fonts and
layout differences live in static/app.css. Cookies remember the last choice
so the login page looks the same as the app, and whether the sidebar is
collapsed (set by the browser, see app.js).
"""

import json

from flask import current_app, g, has_request_context, request

COOKIE = "pc_theme"
LOOK_COOKIE = "pc_look"
NAV_COOKIE = "pc_nav"
DEFAULT = "glas"

# Order is the order on the settings page.
THEMES = {
    "violett": {
        "label": "Violett",
        "description": "Lila, Zahlen wie auf einer Abfahrtstafel, Seitenleiste",
    },
    "glas": {
        "label": "Glas und Orange",
        "description": "Glas, orange Akzente, schwebende Seitenleiste",
    },
    "bronze": {
        "label": "Bronze",
        "description": "Bronze, abgeschrägte Ecken, Menü oben",
    },
    "hell": {
        "label": "Hell",
        "description": "Mattes Glas auf Pastell, schmale Symbolleiste",
    },
    "schlicht": {
        "label": "Schlicht",
        "description": "Das bisherige ruhige Design, Menü oben",
    },
}

# Tone of each design without a mode set ("" = follows the device).
DEFAULT_TONE = {"violett": "dunkel", "glas": "dunkel", "bronze": "dunkel", "hell": "hell",
                "schlicht": ""}
SIDEBAR_THEMES = {"violett", "glas", "hell"}
DEFAULT_NAV = {"hell": "mini"}

# key: (html attribute, {value: label}); "" means "as the design has it".
APPEARANCE = {
    "modus": ("data-mode", {"": "Wie im Design", "hell": "Hell", "dunkel": "Dunkel"}),
    "akzent": ("data-accent", {
        "": "Wie im Design", "violett": "Violett", "blau": "Blau", "pink": "Pink",
        "gruen": "Grün", "orange": "Orange", "gelb": "Gelb", "rot": "Rot"}),
    "schrift": ("data-size", {"klein": "Klein", "": "Normal", "gross": "Groß"}),
    "ecken": ("data-shape", {"": "Wie im Design", "rund": "Rund", "weich": "Weich",
                             "kantig": "Kantig"}),
    "menue": ("data-menu", {
        "": "Wie im Design", "fluessig": "Liquid", "magnet": "Magnet-Dock",
        "kapsel": "Glas-Kapsel", "segment": "Segmente", "orbit": "Orbit", "welle": "Welle",
        "neon": "Neon", "blob": "Blob", "karten": "Karten", "luxus": "Minimal Luxus"}),
}
DEFAULT_LOOK = {key: "" for key in APPEARANCE}
LABELS = {"modus": "Hell oder dunkel", "akzent": "Akzentfarbe", "schrift": "Schriftgröße",
          "ecken": "Ecken", "menue": "Menü-Stil"}


def resolve(value) -> str:
    return value if value in THEMES else DEFAULT


def clean_look(values) -> dict:
    """Only known keys and values; everything else falls back to the design default."""
    look = dict(DEFAULT_LOOK)
    if isinstance(values, dict):
        for key, (_attr, options) in APPEARANCE.items():
            value = values.get(key)
            if isinstance(value, str) and value in options:
                look[key] = value
    return look


def load_look(raw: str) -> dict:
    try:
        return clean_look(json.loads(raw) if raw else {})
    except ValueError:
        return dict(DEFAULT_LOOK)


def dump_look(look: dict) -> str:
    return json.dumps({k: v for k, v in clean_look(look).items() if v}, separators=(",", ":"))


def look_cookie(look: dict) -> str:
    return ".".join(look[key] or "-" for key in APPEARANCE)


def look_from_cookie(value) -> dict:
    parts = (value or "").split(".")
    if len(parts) != len(APPEARANCE):
        return dict(DEFAULT_LOOK)
    return clean_look({key: "" if part == "-" else part for key, part in zip(APPEARANCE, parts)})


def current() -> str:
    if not has_request_context():
        return DEFAULT
    user = g.get("user")
    if user and user.get("theme") in THEMES:
        return user["theme"]
    return resolve(request.cookies.get(COOKIE))


def current_look() -> dict:
    if not has_request_context():
        return dict(DEFAULT_LOOK)
    user = g.get("user")
    if user:
        return load_look(user.get("appearance", ""))
    return look_from_cookie(request.cookies.get(LOOK_COOKIE))


def tone(theme: str, look: dict) -> str:
    return look["modus"] or DEFAULT_TONE[theme]


def nav_state(theme: str) -> str:
    value = request.cookies.get(NAV_COOKIE) if has_request_context() else None
    return value if value in ("mini", "voll") else DEFAULT_NAV.get(theme, "voll")


def html_attrs(theme: str, look: dict) -> list[tuple[str, str]]:
    """data-* attributes for <html>; values are whitelisted above."""
    attrs = [("data-theme", theme)]
    for key, (attr, _options) in APPEARANCE.items():
        if look[key]:
            attrs.append((attr, look[key]))
    if tone(theme, look):
        attrs.append(("data-tone", tone(theme, look)))
    if theme in SIDEBAR_THEMES:
        attrs.append(("data-nav", nav_state(theme)))
    return attrs


def remember(response):
    """Keep the cookies in step with the logged-in user's choice."""
    user = g.get("user")
    if request.endpoint == "static" or not user or user.get("theme") not in THEMES:
        return response
    wanted = {COOKIE: user["theme"],
              LOOK_COOKIE: look_cookie(load_look(user.get("appearance", "")))}
    for name, value in wanted.items():
        if request.cookies.get(name) != value:
            response.set_cookie(
                name, value, max_age=365 * 24 * 3600, httponly=True, samesite="Lax",
                secure=current_app.config["SECURE_COOKIES"], path="/",
            )
    return response
