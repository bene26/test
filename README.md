# Projekt-Cockpit

Selbst gehostetes Werkzeug für Projektleitung mit mehreren Projekten, eigenen Leuten und externen Firmen. Läuft als ein Docker-Container, z. B. auf einem UGREEN NAS oder Raspberry Pi.

Konzept und Hintergrund: [`docs/konzept.md`](docs/konzept.md). Installation: [`docs/installation-ugreen.md`](docs/installation-ugreen.md).

## Was die Version 0.1 kann (Stufe 1 des Konzepts)

- **Startseite:** überfällig, heute fällig, ohne Update, fehlende Protokolle, Meetings heute und am nächsten Arbeitstag, Überbuchungen, fällige Routinen mit Checkliste
- **Aufgaben:** Schnellerfassung in einer Zeile, Filter und Schnellansichten, Status direkt in der Liste ändern, Sammelbearbeitung (Status, verschieben, zuweisen, löschen), CSV-Export für Excel
- **Zuständigkeit:** interne Person, Person einer Firma mit Arbeitnehmerüberlassung oder die Firma selbst (Werk-/Dienstvertrag); Externe unter Werk-/Dienstvertrag lassen sich bewusst nicht einzeln planen
- **Meetings:** acht Vorlagen (Jour fixe, Kick-off, Team, Management, Abnahme, Eskalation, Lessons Learned, Sonstiges); Agenda mit Live-Daten (offene Maßnahmen, Aufgaben der Firma, Auslastung, Projektstatus); Notizen mit automatischem Speichern; Entscheidungen mit Nummer je Projekt; Maßnahmen werden sofort Aufgaben; Folgetermin mit einem Klick
- **Protokolle:** Abschluss friert das Protokoll ein, Korrekturen erzeugen neue Versionen; Druckansicht bzw. PDF; Versand per E-Mail an die Teilnehmenden
- **Entscheidungsregister** je Projekt
- **Auslastung:** aus Aufwand und Fälligkeit der offenen Aufgaben, je Person in Prozent mit Ampel, je Firma in Stunden
- **Erinnerungen** per Push (ntfy) und/oder E-Mail: Morgen-Zusammenfassung, Wochenplanung (Mo–Mi, bis erledigt), Wochenabschluss (Fr), Meeting-Vorbereitung am Vortag, Monatsbericht; Uhrzeiten einstellbar
- **Sicherung:** tägliche Datenbank-Kopie (14 Tage), Download in den Einstellungen

Noch nicht enthalten (Stufe 2/3 im Konzept): Abwesenheiten und Feiertage, Kontingente je Bestellung, Meilensteine, Szenarien, mehrere Benutzer, Firmenportal.

## Schnellstart mit Docker

```
cp .env.example .env        # COCKPIT_BASE_URL anpassen
docker compose up -d --build
docker logs projekt-cockpit  # Einrichtungscode ablesen
```

Dann `http://<host>:8080` öffnen und das Konto anlegen.

## Entwicklung

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
COCKPIT_DATA_DIR=./data flask --app cockpit:create_app run --debug
pytest
```

Aufbau:

| Pfad | Inhalt |
|---|---|
| `cockpit/__init__.py` | App-Fabrik, Sicherheits-Header, Template-Helfer |
| `cockpit/auth.py` | Einrichtung, Login, Sitzungen, CSRF, Login-Sperre |
| `cockpit/forms.py` | serverseitige Prüfung aller Formulare |
| `cockpit/data.py` | gemeinsame Abfragen, Auslastung, Routinen |
| `cockpit/reminders.py`, `notify.py` | Erinnerungs-Dienst, ntfy, E-Mail, Sicherungen |
| `cockpit/meeting_types.py` | Meeting-Vorlagen |
| `cockpit/views/` | Seiten je Bereich |
| `cockpit/schema.sql` | Datenbankschema (SQLite) |
| `tests/` | pytest |

Sicherheit: siehe [`SECURITY.md`](SECURITY.md).
