# Code übernehmen: für eine neue oder eine bestehende Webseite

Es gibt vier Wege, je nachdem, was du vorhast.

| Vorhaben | Weg |
|---|---|
| Das Cockpit auf einem anderen Gerät oder für ein anderes Team betreiben | **A**: App 1:1 installieren |
| Eine neue Webseite bauen, die genauso aussieht und funktioniert | **B**: App als Grundgerüst nehmen und erweitern |
| Bestehende Webseiten im gleichen Design | **C**: Design-Paket |
| Eine einzelne Funktion (z. B. Zeitplan) in eine andere Anwendung | **D**: Module herauslösen |

## Code bekommen

- Als ZIP: im GitHub-Repository den Branch auswählen und **Code → Download ZIP** klicken.
- Mit Git: `git clone` und dann `git checkout claude/cool-heisenberg-ydnbag`.

Bevor du Code weitergibst: Die Dateien `.env` und `data/` gehören nie dazu. Sie enthalten Zugangsdaten und die Datenbank und sind deshalb in `.gitignore` ausgeschlossen.

## A: App 1:1 installieren

Siehe [`installation-ugreen.md`](installation-ugreen.md). Das klappt auf jedem Rechner mit Docker, also auch auf einem Raspberry Pi oder einem Linux-Server. Jede Installation hat ihre eigene Datenbank und ihr eigenes Konto.

Name und Logo ändern:

| Was | Wo |
|---|---|
| Name im Menü und im Browser-Tab | `cockpit/templates/base.html` („Projekt-Cockpit“) |
| Name auf der Anmeldeseite | `cockpit/templates/auth/login.html` und `setup.html` |
| Symbol im Browser-Tab | `cockpit/static/icon.svg` |
| Logo-Zeichen (zwei Dreiecke) | `.logo` in `cockpit/static/app.css` |
| Standard-Design für neue Konten | `DEFAULT` in `cockpit/themes.py` |

## B: Neue Webseite auf Basis der App

Die App ist eine schlanke Flask-Anwendung (Python) mit SQLite. Eine neue Seite braucht drei Teile:

1. **Ansicht** in `cockpit/views/`, z. B. `kontakte.py`:

   ```python
   from flask import Blueprint, render_template
   from ..db import get_db

   bp = Blueprint("contacts", __name__, url_prefix="/kontakte")

   @bp.route("")
   def index():
       rows = get_db().execute("SELECT name, email FROM people ORDER BY name").fetchall()
       return render_template("contacts/index.html", rows=rows)
   ```
2. **Vorlage** `cockpit/templates/contacts/index.html`:

   ```html
   {% extends "base.html" %}
   {% block title %}Kontakte{% endblock %}
   {% block content %}
   <div class="page-head"><h1>Kontakte</h1></div>
   <section class="card">
     <ul class="plain-list">{% for r in rows %}<li>{{ r.name }} · {{ r.email }}</li>{% endfor %}</ul>
   </section>
   {% endblock %}
   ```
3. **Anmelden und ins Menü:** In `cockpit/__init__.py` das Modul in die Liste der Blueprints aufnehmen. In `cockpit/templates/base.html` eine Zeile in die Menüliste schreiben (Endpunkt, Name, Symbol, Blueprint).

Regeln, die bei neuen Seiten gelten, damit die Sicherheit erhalten bleibt:

- Jedes Formular bekommt `{{ csrf() }}` und wird serverseitig mit `forms.parse` bzw. `parse_or_flash` geprüft.
- Keine `style="…"`-Attribute und kein Inline-JavaScript. Die Content-Security-Policy blockiert beides. Stil gehört in `app.css`, Verhalten in `app.js`.
- Neue Tabellen nie in `schema.sql` ergänzen, sondern als neue Migration ans Ende von `MIGRATIONS` in `cockpit/db.py` anhängen. Dann bekommen bestehende Installationen sie beim nächsten Start automatisch.
- Für jede neue Funktion einen Test in `tests/` anlegen und `pytest` laufen lassen.

## C: Bestehende Webseiten im gleichen Design

Dafür ist das Design-Paket gedacht: [`../design-kit/README.md`](../design-kit/README.md). Es funktioniert mit reinem HTML, WordPress, React und anderen und braucht nur eine CSS-Datei und die Schriften. Bauen mit:

```
python3 tools/build_design_kit.py      # erzeugt dist/design-kit.zip
```

## D: Einzelne Funktionen herauslösen

| Funktion | Logik | Seiten und Vorlagen | Tabellen |
|---|---|---|---|
| Zeitplan mit Abhängigkeiten | `cockpit/schedule.py` | `views/schedule.py`, `templates/schedule/` | `schedule_items`, `schedule_links` |
| Kontingente | `cockpit/quotas.py` | `views/orders.py`, `templates/orders/` | `orders`, `service_records` |
| Stundenzettel | – | `views/times.py`, `templates/times/` | `time_entries` |
| Statusbericht | `cockpit/reports.py` | `views/reports.py`, `templates/reports/` | liest aus allen |
| Anpassbare Startseite | `cockpit/dashboard.py` | `views/main.py`, `templates/dashboard.html`, `templates/widgets/` | `users.dashboard` |
| Designs | `cockpit/themes.py` | `static/app.css`, Einstellungen | `users.theme` |

Die Tabellen stehen in `cockpit/schema.sql` und `cockpit/migration_3.sql`. Läuft die andere Anwendung auch mit Python und Flask, lassen sich die Dateien fast unverändert übernehmen. Bei PHP, Node oder einer App bleibt die Logik dieselbe, muss aber übersetzt werden. Am aufwendigsten ist `schedule.py`, die Regeln dazu stehen oben in der Datei.
