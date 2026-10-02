"""Dates, time zones and German number formatting."""

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

_tz = ZoneInfo("Europe/Berlin")

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
MONTHS_LONG = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
               "Oktober", "November", "Dezember"]


def set_timezone(name: str) -> None:
    global _tz
    _tz = ZoneInfo(name)


def tz() -> ZoneInfo:
    return _tz


def now() -> datetime:
    """Current local time without tzinfo, which is how times are stored."""
    return datetime.now(_tz).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()


def stamp(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%d %H:%M:%S")


def from_unix(seconds) -> datetime:
    """UNIX timestamp (UTC) to local time without tzinfo."""
    return datetime.fromtimestamp(float(seconds), _tz).replace(tzinfo=None, microsecond=0)


def to_unix(dt: datetime) -> int:
    return int(dt.replace(tzinfo=_tz).timestamp())


def localize(dt: datetime) -> datetime:
    """Aware datetime to local time without tzinfo."""
    return dt.astimezone(_tz).replace(tzinfo=None, microsecond=0)


def wallclock_ms(ms) -> datetime:
    """Garmin's *Local timestamps: milliseconds that already are local wall-clock time."""
    return datetime.fromtimestamp(float(ms) / 1000, timezone.utc).replace(tzinfo=None,
                                                                           microsecond=0)


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


def days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fmt_date(value, weekday: bool = False) -> str:
    d = to_date(value)
    if d is None:
        return ""
    text = d.strftime("%d.%m.%Y")
    return f"{WEEKDAYS[d.weekday()]} {text}" if weekday else text


def fmt_day(value) -> str:
    """Short day label: 'Mo 05.10.'"""
    d = to_date(value)
    return f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.')}" if d else ""


def fmt_datetime(value, weekday: bool = True) -> str:
    dt = to_datetime(value)
    if dt is None:
        return ""
    return f"{fmt_date(dt, weekday)}, {dt.strftime('%H:%M')}"


def fmt_time(value) -> str:
    dt = to_datetime(value)
    return dt.strftime("%H:%M") if dt else ""


def fmt_ago(value, reference: datetime | None = None) -> str:
    """'vor 5 Min.', 'vor 3 Std.', 'gestern', or the date."""
    dt = to_datetime(value)
    if dt is None:
        return "noch nie"
    reference = reference or now()
    seconds = (reference - dt).total_seconds()
    if seconds < 90:
        return "gerade eben"
    if seconds < 3600:
        return f"vor {int(seconds // 60)} Min."
    if seconds < 24 * 3600 and dt.date() == reference.date():
        return f"vor {int(seconds // 3600)} Std."
    if dt.date() == reference.date() - timedelta(days=1):
        return f"gestern, {dt.strftime('%H:%M')}"
    return fmt_datetime(dt, weekday=False)


def fmt_num(value, decimals: int = 0) -> str:
    """German number: 1234.5 -> '1.234,5'. None -> '–'."""
    if value is None:
        return "–"
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_minutes(minutes) -> str:
    """Duration: 452 -> '7 h 32 min'."""
    if minutes is None:
        return "–"
    minutes = int(round(float(minutes)))
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest:02d} min"


def fmt_signed(value, decimals: int = 1) -> str:
    """Change with sign: +1,2 / −0,4 / ±0."""
    if value is None:
        return ""
    rounded = round(float(value), decimals)
    if rounded == 0:
        return "±0"
    sign = "+" if rounded > 0 else "−"
    return sign + fmt_num(abs(rounded), decimals)


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


def csv_cell(value) -> str:
    text = "" if value is None else str(value)
    # Keep spreadsheet programs from evaluating cell content as a formula.
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text
    return text


def csv_number(value) -> str:
    """German decimal for CSV: 7.5 -> '7,5', 8.0 -> '8'."""
    if value is None:
        return ""
    value = round(float(value), 2)
    return f"{value:.0f}" if value == int(value) else f"{value:.2f}".rstrip("0").replace(".", ",")
