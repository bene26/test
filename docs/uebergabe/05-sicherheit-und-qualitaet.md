# 5. Sicherheit und Qualität

Ausführlich: `referenz-code/projekt-cockpit/SECURITY.md`. Diese Regeln gelten auch für die Übernahme in eine andere App.

## Sicherheit

- **Anmeldung:** Passwort mindestens 12 Zeichen, gehasht (scrypt). Nach 5 Fehlversuchen pro IP 15 Minuten Sperre. Serverseitige Sitzungen; Abmelden löscht die Sitzung. Erstes Konto nur mit Einrichtungscode aus dem Server-Log, damit niemand im Netz vorher ein Konto anlegt.
- **Cookies:** Sitzung `HttpOnly`, `SameSite=Lax`, `Secure` bei HTTPS. Design-Cookies enthalten nur Werte aus festen Listen; der Server ignoriert alles andere.
- **CSRF:** Token auf jedem Formular und jeder POST-Anfrage, auch bei `fetch` (Formularfeld oder Kopfzeile `X-CSRF-Token`).
- **Eingaben:** Jedes Formular hat eine Liste erlaubter Felder mit Typ und Länge; unbekannte Felder werden abgelehnt. Prüfung immer auf dem Server, auch wenn der Browser schon prüft.
- **Suche und Assistent:** nur nach Anmeldung, feste SQL-Abfragen mit Parametern, `%` und `_` maskiert, Längen begrenzt (Suche 100, Frage 200 Zeichen). Kein Sprachmodell, kein externer Dienst. Antworten werden im Browser nur als Text eingefügt (`textContent`), nie als HTML.
- **Content-Security-Policy:** `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'`. Deshalb: keine Inline-Skripte, keine `style="…"`-Attribute im HTML. Bewegungen über Klassen, CSS-Variablen und `element.style`/`element.animate()` aus Skript-Dateien.
- **Weitere Kopfzeilen:** `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cache-Control: no-store` für Seiten, HSTS bei HTTPS.
- **Geheimnisse:** SMTP- und ntfy-Zugänge nur in Umgebungsvariablen (`.env`, nicht im Git). Logs enthalten keine Passwörter, Tokens oder Inhalte.
- **E-Mail:** Statusberichte nur an Adressen, die beim Versand eingegeben werden (höchstens 20, geprüft). Protokolle nur an die Teilnehmenden.
- **Datenschutz:** Stunden je Person sind personenbezogen: nur Stunden je Person, Projekt und Tag, keine Kommentare, keine Abwesenheitsgründe; nicht zur Leistungskontrolle (mit Betriebsrat abstimmen). Externe unter Werk- oder Dienstvertrag nie einzeln planen oder bewerten.
- **Schriften und Inhalte:** alles vom eigenen Server, keine Google Fonts, keine CDNs.

Für eine App mit Supabase gilt zusätzlich: Row Level Security auf jeder Tabelle, Schlüssel mit Admin-Rechten nie im Client, Suche und Assistent als Edge Function oder RPC mit Prüfung des angemeldeten Benutzers.

## Barrierefreiheit

- Kontraste nach WCAG AA (Text 4,5 : 1, Bedienelemente 3 : 1) in allen Designs und Akzentfarben geprüft.
- Sichtbarer Fokus-Rahmen (2 px Akzentfarbe, 2 px Abstand); bei Bronze innen, weil abgeschrägte Ecken Umrisse abschneiden.
- Alles per Tastatur bedienbar: Karteikasten (↑ ↓ Tab Enter Esc), Orb (Enter, Esc), Formulare, Startseiten-Editor (Pfeil-Knöpfe als Alternative zum Ziehen).
- Zähler in der Navigation mit unsichtbarem Text („: 5 überfällig“). Fallblatt-Zahlen mit unsichtbarem Klartext. Dekorative Bilder (`svg`, `canvas`) mit `aria-hidden`.
- Live-Regionen für Stärke-Anzeige, Schloss-Status, Treffer im Karteikasten, Orb-Antworten, Kassenbon.
- `prefers-reduced-motion`: alle Animationen aus, Endzustände sofort.

## Druck

Berichte und Protokolle haben eigene Druckansichten; in jedem Design schwarz auf weiß, ohne Navigation, Ampeln farbig. „Drucken / als PDF speichern“ nutzt den Druckdialog des Browsers.

## Tests der Vorlage

111 automatische Tests (`referenz-code/projekt-cockpit/tests/`, `pytest`). Für die neuen Teile besonders lesenswert:

| Datei | Prüft |
|---|---|
| `test_komponenten.py` | Suche (alle Gruppen, Login nötig, Platzhalter maskiert), Assistent-Antworten zu jedem Thema, Seite ohne JavaScript maskiert HTML, Papierflieger-JSON, Kassenbon-Inhalt, Schlüssel-Markup, Startseiten-Baustein an der richtigen Stelle |
| `test_appearance.py` | Speichern der Darstellung, Attribute am `<html>`, Cookies, ungültige und gefälschte Werte, Seitenleiste nur bei passenden Designs |
| `test_dashboard.py` | Bausteine, Layout laden und speichern |
| `test_schedule.py`, `test_orders.py`, `test_times.py`, `test_reports.py` | Fachregeln aus `04` |
| `test_design_kit.py` | Einbau-Skript und Paket für HTML-Seiten |
