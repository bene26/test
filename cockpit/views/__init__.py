"""HTTP views, one blueprint per area."""

from flask import flash, redirect, request

from .. import forms, util


def back(default: str):
    """Redirect to the `next` field if it is a local path, else to `default`."""
    return redirect(util.safe_next(request.values.get("next"), default))


def parse_or_flash(spec, extra_allowed=frozenset()):
    """Validate request.form; on error flash the message and return None."""
    try:
        return forms.parse(request.form, spec, extra_allowed)
    except forms.ValidationError as exc:
        flash(str(exc), "error")
        return None
