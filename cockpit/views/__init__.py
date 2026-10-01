"""HTTP views, one blueprint per area."""

import csv
import io

from flask import Response, flash, redirect, request

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


def csv_response(filename: str, header: list, rows) -> Response:
    """Semicolon CSV with BOM so Excel opens umlauts correctly."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([util.csv_cell(v) for v in row])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
