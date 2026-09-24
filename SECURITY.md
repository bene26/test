# Sicherheit: Projekt-Cockpit

Kurzes Bedrohungsmodell. Bei jeder neuen Datenart oder Rolle überarbeiten.

## Nutzer und Rollen

- **Stufe 1:** genau ein Konto (Projektleitung), das alles darf.
- Später geplant: Teammitglieder, Management, externe Firmen (Firmenportal). Dann dieses Dokument neu durchgehen.

## Gespeicherte Daten

| Daten | personenbezogen? | Hinweis |
|---|---|---|
| Namen, Rollen, Wochenstunden interner Personen | ja | nur, was für die Planung nötig ist |
| Firmen, Ansprechpartner mit E-Mail | ja (Ansprechpartner) | |
| Aufgaben, Aufwände, Fälligkeiten | teilweise | Zuordnung zu Personen |
| Meeting-Protokolle, Teilnehmende, Entscheidungen | ja | können Vertragsinhalte und Preise enthalten |
| Passwort-Hash, Sitzungen | ja | Passwort nur als scrypt-Hash, Sitzungs-Token nur als SHA-256-Hash |

**Bewusst nicht gespeichert:** Gründe für Abwesenheiten (Krankheit), Gehälter, Leistungsbewertungen einzelner Personen.

## Vertrauensgrenzen

- **Browser ↔ App:** Der Browser ist nicht vertrauenswürdig. Jede Prüfung (Login, Rechte, Eingaben) passiert auf dem Server.
- **App ↔ SQLite:** nur parametrisierte Abfragen.
- **App → ntfy / Mailserver:** Benachrichtigungen enthalten nur Zahlen und einen Link, keine Aufgabentitel, Namen oder Protokollinhalte. Protokolle per E-Mail gehen nur an die Adressen, die im Meeting eingetragen sind.
- **NAS ↔ Internet:** Die App ist für LAN oder VPN gedacht, nicht zum direkten Freigeben ins Internet.

## Was ein Angreifer wollen würde

1. Protokolle mit Vertragsinhalten, Preisen und Entscheidungen
2. Kontaktdaten externer Personen und Auslastung der eigenen Leute
3. Unbemerkt Entscheidungen oder versendete Protokolle ändern

## Schlimmster realistischer Fall

Die App wird per Portweiterleitung ins Internet gestellt, das Passwort erraten oder ein Backup-File gelangt nach außen, und alle Protokolle und Personendaten sind öffentlich.

## Maßnahmen

- Einrichtung nur mit Einrichtungscode aus dem Container-Log, damit niemand im LAN das Konto vorher anlegt
- Passwort mindestens 12 Zeichen, gehasht mit scrypt (Werkzeug)
- Login-Begrenzung: nach 5 Fehlversuchen pro IP 15 Minuten Sperre
- serverseitige Sitzungen; Abmelden löscht die Sitzung in der Datenbank
- Sitzungs-Cookie `HttpOnly`, `SameSite=Lax`, `Secure` bei HTTPS
- CSRF-Token auf jedem Formular und jeder POST-Anfrage
- Eingaben werden je Formular gegen eine erlaubte Feldliste, Typen und Längen geprüft; unbekannte Felder werden abgelehnt
- Sicherheits-Header: Content-Security-Policy ohne Inline-Skripte, `frame-ancestors 'none'`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS bei HTTPS
- keine Zugangsdaten im Code; SMTP- und ntfy-Zugänge nur über Umgebungsvariablen (`.env`, nicht im Git)
- versendete Protokolle werden eingefroren; Korrekturen erzeugen eine neue Version
- tägliche lokale Sicherungskopie der Datenbank (14 Tage); verschlüsselte Sicherung außerhalb des NAS über die Backup-Funktion von UGOS
- Container läuft als Nicht-Root-Benutzer
- Logs enthalten keine Passwörter, Tokens oder Inhalte

## Vor jedem Update prüfen

- Tests grün (`pytest`)
- `pip-audit` ohne hohe oder kritische Befunde
- keine Zugangsdaten im Repository oder im Image
- Login, Abmelden und abgelaufene Sitzung ausprobiert
