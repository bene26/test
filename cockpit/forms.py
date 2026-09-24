"""Server-side validation of submitted forms.

Every handler declares the fields it accepts. Unknown fields are rejected,
values are converted to the right type and checked for length and range.
"""

import re
from datetime import date, time

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Fields every POST may carry in addition to its own spec.
ALWAYS_ALLOWED = {"csrf_token", "next"}


class ValidationError(ValueError):
    pass


class Field:
    def __init__(self, label: str, required: bool = False):
        self.label = label
        self.required = required

    def parse(self, raw):
        raw = (raw or "").strip()
        if not raw:
            if self.required:
                raise ValidationError(f"„{self.label}“ fehlt.")
            return None
        return self.convert(raw)

    def convert(self, raw):
        return raw


class Text(Field):
    def __init__(self, label, required=False, max_len=200, multiline=False):
        super().__init__(label, required)
        self.max_len = max_len
        self.multiline = multiline

    def parse(self, raw):
        value = super().parse(raw)
        return "" if value is None else value

    def convert(self, raw):
        raw = raw.replace("\r\n", "\n")
        if not self.multiline and "\n" in raw:
            raise ValidationError(f"„{self.label}“ darf keinen Zeilenumbruch enthalten.")
        if CONTROL_CHARS.search(raw):
            raise ValidationError(f"„{self.label}“ enthält ungültige Zeichen.")
        if len(raw) > self.max_len:
            raise ValidationError(f"„{self.label}“ ist zu lang (max. {self.max_len} Zeichen).")
        return raw


class Integer(Field):
    def __init__(self, label, required=False, min_value=None, max_value=None):
        super().__init__(label, required)
        self.min_value = min_value
        self.max_value = max_value

    def convert(self, raw):
        if not re.fullmatch(r"-?\d{1,9}", raw):
            raise ValidationError(f"„{self.label}“ muss eine ganze Zahl sein.")
        return _check_range(int(raw), self)


class Number(Integer):
    def convert(self, raw):
        raw = raw.replace(",", ".")
        if not re.fullmatch(r"-?\d{1,6}(\.\d{1,2})?", raw):
            raise ValidationError(f"„{self.label}“ muss eine Zahl sein.")
        return _check_range(float(raw), self)


def _check_range(value, field):
    if field.min_value is not None and value < field.min_value:
        raise ValidationError(f"„{field.label}“ muss mindestens {field.min_value} sein.")
    if field.max_value is not None and value > field.max_value:
        raise ValidationError(f"„{field.label}“ darf höchstens {field.max_value} sein.")
    return value


class Date(Field):
    def convert(self, raw):
        try:
            value = date.fromisoformat(raw)
        except ValueError:
            raise ValidationError(f"„{self.label}“ ist kein gültiges Datum.") from None
        if not 2000 <= value.year <= 2100:
            raise ValidationError(f"„{self.label}“ liegt außerhalb des erlaubten Bereichs.")
        return value.isoformat()


class Time(Field):
    def convert(self, raw):
        if not re.fullmatch(r"\d{2}:\d{2}", raw):
            raise ValidationError(f"„{self.label}“ ist keine gültige Uhrzeit.")
        try:
            return time.fromisoformat(raw).strftime("%H:%M")
        except ValueError:
            raise ValidationError(f"„{self.label}“ ist keine gültige Uhrzeit.") from None


class Choice(Field):
    def __init__(self, label, options, required=False):
        super().__init__(label, required)
        self.options = {str(o) for o in options}

    def convert(self, raw):
        if raw not in self.options:
            raise ValidationError(f"„{self.label}“ hat einen ungültigen Wert.")
        return raw


class Checkbox(Field):
    def parse(self, raw):
        return (raw or "") in ("on", "1", "true")


class Email(Field):
    def parse(self, raw):
        value = super().parse(raw)
        return "" if value is None else value

    def convert(self, raw):
        if len(raw) > 254 or not EMAIL_RE.match(raw):
            raise ValidationError(f"„{self.label}“ ist keine gültige E-Mail-Adresse.")
        return raw


class Assignee(Field):
    """'p:<id>' for a person, 'f:<id>' for a firm. Returns (person_id, firm_id)."""

    def parse(self, raw):
        value = super().parse(raw)
        return (None, None) if value is None else value

    def convert(self, raw):
        match = re.fullmatch(r"([pf]):(\d{1,9})", raw)
        if not match:
            raise ValidationError(f"„{self.label}“ hat einen ungültigen Wert.")
        kind, ident = match.group(1), int(match.group(2))
        return (ident, None) if kind == "p" else (None, ident)


class IdList(Field):
    multi = True

    def parse(self, raw_list):
        values = []
        for raw in raw_list:
            if not re.fullmatch(r"\d{1,9}", raw or ""):
                raise ValidationError(f"„{self.label}“ enthält ungültige Werte.")
            values.append(int(raw))
        if self.required and not values:
            raise ValidationError(f"Bitte mindestens einen Eintrag für „{self.label}“ auswählen.")
        if len(values) > 1000:
            raise ValidationError("Zu viele Einträge auf einmal.")
        return values


def parse(form, spec: dict[str, Field], extra_allowed: set[str] = frozenset()) -> dict:
    unknown = set(form.keys()) - set(spec) - ALWAYS_ALLOWED - set(extra_allowed)
    if unknown:
        raise ValidationError("Das Formular enthält unerwartete Felder.")
    result = {}
    for name, field in spec.items():
        if getattr(field, "multi", False):
            result[name] = field.parse(form.getlist(name))
        else:
            values = form.getlist(name)
            if len(values) > 1:
                raise ValidationError(f"„{field.label}“ wurde mehrfach gesendet.")
            result[name] = field.parse(values[0] if values else None)
    return result
