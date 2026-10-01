# Übergabe: Projekt-Cockpit (Stand Version 0.5)

Dieses Paket beschreibt alles, was im Projekt-Cockpit gebaut wurde: alle Seiten, Funktionen, das Design-System, jede Animation und jeden Übergang. Dazu kommen Vorschaubilder, die Video-Vorlagen und der komplette funktionierende Quellcode. Es ist so geschrieben, dass ein anderer Claude-Agent die Funktionen in eine bestehende App übernehmen kann, egal ob diese mit HTML, React oder React Native gebaut ist.

## So benutzt du das Paket

1. Das ganze Paket (ZIP entpacken) dem Agenten geben, zusammen mit dem Zugang zu deiner App.
2. Den Text aus [`AGENT-PROMPT.md`](AGENT-PROMPT.md) als erste Nachricht schicken. Oben im Prompt trägst du ein, welche Teile übernommen werden sollen.
3. Der Agent liest zuerst diese Datei, dann die Leitfäden in der Reihenfolge unten.

## Inhalt

| Datei / Ordner | Was drinsteht |
|---|---|
| [`AGENT-PROMPT.md`](AGENT-PROMPT.md) | fertiger Auftrag zum Einfügen, mit Platzhaltern für deine App |
| [`01-produkt-und-seiten.md`](01-produkt-und-seiten.md) | worum es geht, Seitenübersicht, jede Seite mit Aufbau, Inhalten, Aktionen und Zuständen |
| [`02-design-system.md`](02-design-system.md) | fünf Designs mit allen Farben und Schriften, Darstellungs-Optionen, Navigation und Seitenleiste, Handy |
| [`03-komponenten-und-animationen.md`](03-komponenten-und-animationen.md) | jede bewegte Komponente mit Ablauf, Zeiten, Kurven, Zuständen, Tastatur und Barrierefreiheit |
| [`04-daten-regeln-schnittstellen.md`](04-daten-regeln-schnittstellen.md) | Datenmodell, Rechenregeln (Kontingent, Auslastung, Konflikte), Erinnerungen, Schnittstellen |
| [`05-sicherheit-und-qualitaet.md`](05-sicherheit-und-qualitaet.md) | Sicherheitsregeln, Barrierefreiheit, Druck, „Bewegung reduzieren“, Tests |
| [`06-abnahme-checkliste.md`](06-abnahme-checkliste.md) | prüfbare Punkte je Funktion, zum Abhaken |
| [`07-umsetzung-in-deiner-app.md`](07-umsetzung-in-deiner-app.md) | wie man das in HTML, React/Next.js oder React Native (Expo) mit Supabase umsetzt, empfohlene Reihenfolge |
| [`08-vorlagen-aus-den-videos.md`](08-vorlagen-aus-den-videos.md) | die zehn Instagram-Videos und die Design-Vorschläge: was sie zeigen, was übernommen wurde, wo bewusst abgewichen wurde |
| [`BILDER.md`](BILDER.md) | Verzeichnis aller Vorschaubilder mit Beschreibung |
| [`design-tokens.json`](design-tokens.json) | alle Farben und Maße je Design, Modus und Akzent als JSON (aus dem CSS erzeugt), z. B. für React Native |
| `vorschau/` | Screenshots der fertigen App (Version 0.5): Seiten, Designs, Navigation, Komponenten, Handy |
| `vorlagen-videos/` | Einzelbilder aus den Original-Videos als Referenz |
| `referenz-code/` (nur im ZIP) | der komplette Quellcode der App und das Design-Paket für HTML-Seiten |

## Wichtigste Fakten in Kürze

- **Was:** ein selbst gehostetes Werkzeug für Projektleitung mit mehreren Projekten, eigenen Leuten und externen Firmen (Werkvertrag, Dienstvertrag, Arbeitnehmerüberlassung). Sprache der Oberfläche: Deutsch, Du-Form.
- **Original-Technik:** Python 3.12, Flask, Jinja2, SQLite, ein Docker-Container (UGREEN NAS). Kein JavaScript-Framework, keine externen Dienste, keine KI.
- **Design:** fünf Designs (Violett, Glas und Orange, Bronze, Hell, Schlicht), jedes hell oder dunkel, sieben Akzentfarben, drei Schriftgrößen, drei Eckenformen, zehn Menü-Stile, Zahlen als Fallblatt-Anzeige. Alles über CSS-Variablen und `data-*`-Attribute am `<html>`.
- **Bewegte Komponenten:** Fallblatt-Zahlen, Schlüssel und Schloss, Kassenbon, Karteikasten (Strg+K), Papierflieger, Orb mit zwölf Kugeln, Login V7, zehn Menü-Stile, einklappbare Seitenleiste, Live-Vorschau mit Änderungsleiste.
- **Live-Vorschau zum Anklicken:** https://claude.ai/artifact/JELCRezbjMNzKeS2uRGacg (privat, nur mit Freigabe sichtbar). Alle Komponenten stecken zum Ausprobieren auch in `referenz-code/design-kit/komponenten.html`; die Datei einfach im Browser öffnen.

## Quellcode im Paket

Im ZIP liegt unter `referenz-code/projekt-cockpit/` der Stand des Git-Branches `claude/cool-heisenberg-ydnbag` (Repository `bene26/test`). Die wichtigsten Dateien:

| Datei | Inhalt |
|---|---|
| `cockpit/static/app.css` | das gesamte Design: Tokens je Design, Optionen, Navigation, alle Komponenten (rund 2 470 Zeilen) |
| `cockpit/static/komponenten.js` | die sechs bewegten Komponenten, ohne Bibliotheken (rund 1 200 Zeilen) |
| `cockpit/static/app.js` | Live-Vorschau, Seitenleiste, Startseiten-Editor, Autospeichern, Stundenzettel |
| `cockpit/themes.py` | Liste aller Darstellungs-Optionen, Cookies, Attribute |
| `cockpit/assistent.py` | Regeln für „Frag das Cockpit“ und die Suche |
| `cockpit/schedule.py`, `quotas.py`, `data.py`, `reports.py`, `reminders.py` | Fachlogik |
| `cockpit/templates/` | alle Seiten als HTML-Vorlagen |
| `design-kit/` | das Design für beliebige HTML-Seiten, mit Einbau-Skript und Beispielseiten |
| `docs/konzept.md` | das ursprüngliche Fachkonzept (Ziel, Kapazität, Meetings, Erinnerungen, Datenschutz) |
| `tests/` | 111 automatische Tests, die beschreiben, was gelten muss |

Unter `referenz-code/design-kit/` liegt zusätzlich das fertig gebaute Design-Paket für HTML-Seiten (CSS, Schriften, `komponenten.js`, Beispielseiten, Einbau-Skript), sofort im Browser zu öffnen.

Wer diesen Ordner direkt im Repository liest statt im ZIP: `referenz-code/projekt-cockpit/` ist das Repository selbst (zwei Ebenen höher), `referenz-code/design-kit/` entsteht mit `python3 tools/build_design_kit.py` als `dist/design-kit.zip`.

Der Code darf direkt kopiert werden. Wo deine App eine andere Technik nutzt, dient er als genaue Vorlage für Verhalten und Aussehen.
