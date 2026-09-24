"""Dates, calendar weeks and German formatting."""

from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

_tz = ZoneInfo("Europe/Berlin")

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

TASK_STATUS = {
    "offen": "Offen",
    "in_arbeit": "In Arbeit",
    "wartet": "Wartet",
    "erledigt": "Erledigt",
    "abgenommen": "Abgenommen",
}
OPEN_STATUSES = ("offen", "in_arbeit", "wartet")
DONE_STATUSES = ("erledigt", "abgenommen")

PRIORITY = {1: "Hoch", 2: "Normal", 3: "Niedrig"}

PROJECT_STATUS = {
    "geplant": "Geplant",
    "aktiv": "Aktiv",
    "pausiert": "Pausiert",
    "abgeschlossen": "Abgeschlossen",
}

CONTRACT_TYPES = {
    "werkvertrag": "Werkvertrag",
    "dienstvertrag": "Dienstvertrag",
    "anue": "Arbeitnehmerüberlassung",
}


def set_timezone(name: str) -> None:
    global _tz
    _tz = ZoneInfo(name)


def now() -> datetime:
    """Current local time without tzinfo, which is how times are stored."""
    return datetime.now(_tz).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()


def stamp(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%d %H:%M:%S")


def to_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def to_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_key(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def week_number(d: date) -> int:
    return d.isocalendar()[1]


def is_workday(d: date) -> bool:
    return d.weekday() < 5


def next_workday(d: date) -> date:
    d += timedelta(days=1)
    while not is_workday(d):
        d += timedelta(days=1)
    return d


def last_workday_of_month(d: date) -> date:
    first_next = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    last = first_next - timedelta(days=1)
    while not is_workday(last):
        last -= timedelta(days=1)
    return last


def fmt_date(value, weekday: bool = False) -> str:
    d = to_date(value)
    if d is None:
        return ""
    text = d.strftime("%d.%m.%Y")
    return f"{WEEKDAYS[d.weekday()]} {text}" if weekday else text


def fmt_datetime(value, weekday: bool = True) -> str:
    dt = to_datetime(value)
    if dt is None:
        return ""
    return f"{fmt_date(dt, weekday)}, {dt.strftime('%H:%M')}"


def fmt_hours(value) -> str:
    if value is None:
        return ""
    value = round(float(value), 1)
    text = f"{value:.0f}" if value == int(value) else f"{value:.1f}".replace(".", ",")
    return f"{text} h"


def safe_next(target: str | None, default: str) -> str:
    """Only allow redirects to local paths, never to another host."""
    if not target:
        return default
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return default
    if "\\" in target:
        return default
    return target
