"""Outgoing notifications: ntfy push and e-mail.

Credentials come only from environment variables. Reminder texts carry
counts and a link, never task titles, names or protocol content.
"""

import json
import logging
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

log = logging.getLogger("cockpit")


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def ntfy_configured() -> bool:
    return bool(_env("NTFY_URL") and _env("NTFY_TOPIC"))


def smtp_configured() -> bool:
    return bool(_env("SMTP_HOST") and _env("SMTP_FROM"))


def reminder_email_configured() -> bool:
    return smtp_configured() and bool(_env("REMINDER_EMAIL_TO"))


def send_ntfy(title: str, message: str, click_url: str = "", priority: int = 3) -> None:
    payload = {"topic": _env("NTFY_TOPIC"), "title": title, "message": message,
               "priority": priority, "tags": ["clipboard"]}
    if click_url:
        payload["click"] = click_url
    request = urllib.request.Request(
        _env("NTFY_URL").rstrip("/"), data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    token = _env("NTFY_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (URL from admin config)
        response.read()


def send_email(recipients: list[str], subject: str, body: str) -> None:
    if not recipients:
        raise ValueError("Keine Empfänger.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Projekt-Cockpit", _env("SMTP_FROM")))
    message["To"] = ", ".join(recipients)
    message["Message-ID"] = make_msgid(domain=_env("SMTP_FROM").split("@")[-1] or None)
    message.set_content(body)

    host = _env("SMTP_HOST")
    security = _env("SMTP_SECURITY", "starttls").lower()
    port = int(_env("SMTP_PORT") or (465 if security == "ssl" else 587))
    context = ssl.create_default_context()
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
    with server:
        if security == "starttls":
            server.starttls(context=context)
        user = _env("SMTP_USER")
        if user:
            server.login(user, os.environ.get("SMTP_PASSWORD", ""))
        server.send_message(message)


def remind(title: str, message: str, click_url: str = "") -> list[str]:
    """Send a reminder on every configured channel. Returns the channels used."""
    used = []
    if ntfy_configured():
        try:
            send_ntfy(title, message, click_url)
            used.append("ntfy")
        except Exception as exc:  # network errors must not stop the scheduler
            log.warning("ntfy-Versand fehlgeschlagen: %s", type(exc).__name__)
    if reminder_email_configured():
        try:
            body = message + (f"\n\nÖffnen: {click_url}" if click_url else "")
            send_email([_env("REMINDER_EMAIL_TO")], f"Projekt-Cockpit: {title}", body)
            used.append("email")
        except Exception as exc:
            log.warning("E-Mail-Versand fehlgeschlagen: %s", type(exc).__name__)
    return used
