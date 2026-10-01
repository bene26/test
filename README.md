# Projekt-Cockpit

Selbst gehostetes Werkzeug für Projektleitung mit mehreren Projekten, eigenen Leuten und externen Firmen. Läuft als ein Docker-Container, z. B. auf einem UGREEN NAS oder Raspberry Pi.

Konzept und Hintergrund: [`docs/konzept.md`](docs/konzept.md). Installation: [`docs/installation-ugreen.md`](docs/installation-ugreen.md).

## Was die Version 0.4 kann

- **Startseite zum Selbst-Zusammenstellen:** 14 Bausteine (Kennzahlen, Routinen, Schnellerfassung, nächstes Meeting, Überfällig, Diese Woche, Meetings, Protokoll fehlt, Projekte, Kalender, Zeitplan, Kontingente, Auslastung, Zeiten). Mit „Startseite anpassen“ per Ziehen oder Pfeiltasten sortieren, ein- und ausblenden, breit oder schmal; gespeichert je Konto
- **Aufgaben:** Schnellerfassung in einer Zeile, Filter und Schnellansichten, Status direkt in der Liste ändern, Sammelbearbeitung (Status, verschieben, zuweisen, löschen), CSV-Export für Excel
- **Zuständigkeit:** interne Person, Person einer Firma mit Arbeitnehmerüberlassung oder die Firma selbst (Werk-/Dienstvertrag); Externe unter Werk-/Dienstvertrag lassen sich bewusst nicht einzeln planen
- **Zeitplan:** Vorgänge und Meilensteine (z. B. Kick-off) je Projekt als Gantt-Diagramm; Abhängigkeiten „erst wenn das andere fertig ist“, auch projektübergreifend und mit Puffer; Konflikte werden rot markiert und mit einem Klick gelöst (Nachfolger rücken mit); Kreise werden verhindert; Gesamtansicht über alle Projekte
- **Meetings:** acht Vorlagen (Jour fixe, Kick-off, Team, Management, Abnahme, Eskalation, Lessons Learned, Sonstiges); Agenda mit Live-Daten; Notizen mit automatischem Speichern; Entscheidungen mit Nummer je Projekt; Maßnahmen werden sofort Aufgaben; Folgetermin mit einem Klick
- **Protokolle:** Abschluss friert das Protokoll ein, Korrekturen erzeugen neue Versionen; Druckansicht bzw. PDF; Versand per E-Mail an die Teilnehmenden
- **Berichte:** monatlicher Projektstatus mit Ampel (Termine, Kontingent, Aufgaben), Meilensteinen, Risiken, Entscheidungen, Stunden und Kontingenten; drucken, als PDF speichern oder per E-Mail senden; Archiv aller Protokolle; CSV-Exporte (Aufgaben, Projektstunden, Kontingente)
- **Kontingente externer Firmen:** Bestellungen in Stunden oder Personentagen mit Laufzeit; Leistungsnachweise je Bestellung (eingereicht, geprüft, abgelehnt); verplant, abgerechnet, frei; Warnungen bei 80 %, Überplanung und vier Wochen vor Ablauf
- **Zeiten:** Wochen-Stundenzettel je Person und Projekt mit Summen, Vorwoche übernehmen, Team-Übersicht, Plan/Ist je Projekt; nur eigene Leute und Arbeitnehmerüberlassung (Firmen über Leistungsnachweise)
- **Entscheidungsregister** je Projekt
- **Auslastung:** aus Aufwand und Fälligkeit der offenen Aufgaben, je Person in Prozent mit Ampel, je Firma in Stunden und gegen das Kontingent
- **Erinnerungen** per Push (ntfy) und/oder E-Mail: Morgen-Zusammenfassung (inkl. Zeitplan-Konflikten und Kontingent-Warnungen), Wochenplanung, Wochenabschluss, Meeting-Vorbereitung, Monatsbericht
- **Sicherung:** tägliche Datenbank-Kopie (14 Tage), Download in den Einstellungen
- **Darstellung:** unter *Einstellungen → Darstellung* je Konto: fünf Designs (Violett, Glas und Orange, Bronze, Hell, Schlicht), jeweils hell oder dunkel, sieben Akzentfarben, drei Schriftgrößen, Ecken rund, weich oder kantig und zehn Menü-Stile (Liquid, Magnet, Glas-Kapsel, Segmente, Orbit, Welle, Neon, Blob, Karten, Minimal Luxus). Alles mit Live-Vorschau und Leiste „Änderungen · Verwerfen · Übernehmen“. Schriften werden lokal ausgeliefert (keine Verbindung zu Google Fonts), Ausdrucke bleiben schwarz auf weiß
- **Seitenleiste:** Profil, Suche, Abschnitte, Zähler (überfällig, fehlende Protokolle, Konflikte, Kontingent-Warnungen), zum Einklappen als Symbolleiste; auf dem Handy wird das Menü ein Dock am unteren Rand
- **Anmeldung** im Stil „Login form V7“ mit Aufklapp-Animation und Passwort-Auge

Noch nicht enthalten (siehe Konzept): Abwesenheiten und Feiertage, Zuteilungen je Woche, Szenarien, mehrere Benutzer mit Rechten, Firmenportal, Kalender-Abonnement.

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
| `cockpit/schedule.py` | Zeitplan: Konflikte, Verschieben, Gantt-Layout |
| `cockpit/quotas.py` | Kontingente, Bestellungen, Leistungsnachweise |
| `cockpit/reports.py` | Projektstatus-Bericht |
| `cockpit/dashboard.py` | Bausteine der Startseite und gespeicherte Anordnung |
| `cockpit/themes.py` | die fünf Designs |
| `cockpit/views/` | Seiten je Bereich |
| `cockpit/templates/` | HTML-Vorlagen (Jinja), `widgets/` = Startseiten-Bausteine |
| `cockpit/static/app.css` | alle Designs als CSS-Variablen je `data-theme` |
| `cockpit/schema.sql`, `migration_3.sql` | Datenbankschema (SQLite) und Erweiterungen |
| `design-kit/` | Design zum Übernehmen in andere Webseiten |
| `tests/` | pytest |

Den Code in eine andere oder neue Webseite übernehmen: [`docs/code-uebernehmen.md`](docs/code-uebernehmen.md).

Sicherheit: siehe [`SECURITY.md`](SECURITY.md).
