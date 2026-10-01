"""Write design-kit/404.html from the app's error page graphics (templates/_grafiken.html).

The kit page is static, so the requested address is filled in by komponenten.js
(data-fehler-pfad). Run again after changing the graphics:

    python3 tools/build_404_page.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PLACEHOLDER = "/§pfad§"

HEAD = """<!doctype html>
<!-- 404-Seite für deine Webseite: sechs Grafiken (Abfahrtstafel, Schwarzes Loch, Kassenbon,
     Papierflieger, Karteikasten, Schlüssel). Welche erscheint, steuert data-grafik am <html>;
     ohne data-grafik nimmt jedes Design seine eigene (Violett Abfahrtstafel, Glas Schwarzes Loch,
     Bronze Kassenbon, Hell Papierflieger, Schlicht Karteikasten).
     Auf dem Server als 404-Seite eintragen (Apache: ErrorDocument 404 /404.html, nginx:
     error_page 404 /404.html; bei vielen Hostern genügt die Datei 404.html im Hauptordner).
     Weil die Seite unter beliebigen Adressen erscheint, die Pfade zu CSS und Skripten absolut
     schreiben, z. B. /design/cockpit-design.css. Diese Datei wird mit tools/build_404_page.py
     erzeugt. -->
<html lang="de" data-theme="glas" data-tone="dunkel">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>Seite nicht gefunden · Meine Webseite</title>
  <link rel="stylesheet" href="../cockpit/static/app.css">
  <script src="theme-umschalter.js" defer></script>
  <script src="../cockpit/static/komponenten.js" defer></script>
</head>
<body>
<main>
  <section class="fehlerseite" aria-labelledby="fehler-titel">
    <div class="fehler-bild">
"""

TAIL = """    </div>
    <div class="fehler-text">
      <p class="eyebrow">Fehler 404</p>
      <h1 id="fehler-titel">Seite nicht gefunden</h1>
      <p class="fehler-meldung">Diese Seite gibt es nicht (mehr). Vielleicht wurde sie verschoben, oder der Link ist falsch geschrieben.</p>
      <p class="fehler-pfad">Adresse: <code data-fehler-pfad>/seite</code></p>
      <div class="fehler-aktionen">
        <a class="btn btn-primary" href="/">Zur Startseite</a>
        <a class="btn" href="/" data-zurueck>Zurück</a>
      </div>
      <!-- Zum Ausprobieren; auf der echten Seite weglassen. -->
      <div class="look-schnell">
        <label class="sr-only" for="k-design">Design</label>
        <select id="k-design" data-look="theme">
          <option value="violett">Violett</option><option value="glas">Glas und Orange</option><option value="bronze">Bronze</option><option value="hell">Hell</option><option value="schlicht">Schlicht</option>
        </select>
        <label class="sr-only" for="k-grafik">Grafik</label>
        <select id="k-grafik" data-look="grafik">
          <option value="">Grafik wie im Design</option><option value="fallblatt">Abfahrtstafel</option><option value="loch">Schwarzes Loch</option><option value="bon">Kassenbon</option><option value="flieger">Papierflieger</option><option value="kartei">Karteikasten</option><option value="schluessel">Schlüssel</option>
        </select>
      </div>
    </div>
  </section>
</main>
</body>
</html>
"""


def graphics_html() -> str:
    import logging
    import os
    import tempfile
    from cockpit import create_app
    previous = os.environ.get("COCKPIT_DATA_DIR")
    logging.disable(logging.WARNING)
    try:
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["COCKPIT_DATA_DIR"] = data_dir
            app = create_app({"TESTING": True, "SCHEDULER": False})
            with app.test_request_context():
                tpl = app.jinja_env.from_string(
                    '{% from "_grafiken.html" import fehler_grafiken %}'
                    '{{ fehler_grafiken(404, "NICHT GEFUNDEN", path, "", "") }}')
                html = tpl.render(path=PLACEHOLDER)
    finally:
        logging.disable(logging.NOTSET)
        if previous is None:
            os.environ.pop("COCKPIT_DATA_DIR", None)
        else:
            os.environ["COCKPIT_DATA_DIR"] = previous
    upper = PLACEHOLDER.upper()
    html = html.replace(f"<span data-fallblatt-wert>{upper}</span>",
                        '<span data-fallblatt-wert data-fehler-pfad="kurz">/SEITE</span>')
    html = html.replace(f"<span>{upper}</span>", '<span data-fehler-pfad="kurz">/SEITE</span>')
    html = html.replace(f'<span class="kk-hinweis">{PLACEHOLDER}</span>',
                        '<span class="kk-hinweis" data-fehler-pfad>/seite</span>')
    html = html.replace(f'data-bon-barcode="404{PLACEHOLDER}"', 'data-bon-barcode="404"')
    html = html.replace("<span>Abfahrt</span><span></span>", "<span>Abfahrt</span><span data-fehler-uhr></span>")
    html = html.replace("<span>Beleg Nr. 404</span><span></span>",
                        "<span>Beleg Nr. 404</span><span data-fehler-datum></span>")
    html = re.sub(r"\n\s*\n", "\n", html)
    assert PLACEHOLDER not in html and upper not in html, "placeholder left in the page"
    return "\n".join("      " + line if line.strip() else line for line in html.strip().splitlines()) + "\n"


def build() -> str:
    return HEAD + graphics_html() + TAIL


if __name__ == "__main__":
    target = ROOT / "design-kit" / "404.html"
    target.write_text(build(), encoding="utf-8")
    print(target)
