"""HTTP views, one blueprint per area."""

import csv
import io
from datetime import timedelta

from flask import Response, flash, redirect, request

from .. import forms, util

# Choosable periods: days -> label
PERIODS = {7: "7 T", 30: "30 T", 90: "90 T", 365: "1 J"}


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


def period(default: int = 30) -> tuple[int, object, object]:
    """(days, start, end) from ?zeitraum=; unknown values fall back to the default."""
    try:
        days = int(request.args.get("zeitraum", default))
    except ValueError:
        days = default
    if days not in PERIODS:
        days = default
    end = util.today()
    return days, end - timedelta(days=days - 1), end


def csv_response(filename: str, header: list, rows) -> Response:
    """Semicolon CSV with BOM so Excel opens umlauts correctly."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([util.csv_cell(v) for v in row])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
