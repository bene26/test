# 4. Daten, Regeln und Schnittstellen

Genaue Tabellen: `referenz-code/projekt-cockpit/cockpit/schema.sql` und `migration_3.sql`; Migrationen in `cockpit/db.py` (Liste `MIGRATIONS`, Index = `PRAGMA user_version`, aktuell 4). Fachlicher Hintergrund: `docs/konzept.md`.

## Datenmodell (Kurzfassung)

| Tabelle | Wichtige Felder | Bemerkung |
|---|---|---|
| `users` | username, password_hash (scrypt), theme, appearance (JSON), dashboard (JSON) | ein Konto |
| `sessions` | token_hash, user_id, csrf_token, expires_at | serverseitige Sitzungen |
| `settings` | key, value | Uhrzeiten der Erinnerungen, „ohne Update nach N Tagen“, an/aus |
| `projects` | name, code, client, status (geplant/aktiv/pausiert/abgeschlossen), priority 1–3, start/end, notes | |
| `firms` | name, contract_type (werkvertrag/dienstvertrag/anue), Ansprechpartner, active | |
| `people` | name, role, email, weekly_hours (≤ 80), availability (0–1, z. B. 0,8), firm_id (nur bei ANÜ), active | |
| `tasks` | title, description, project_id, person_id **oder** firm_id, effort_hours, start_date, due_date, status (offen/in_arbeit/wartet/erledigt/abgenommen), waiting_for, priority, meeting_id, updated_at | eine Aufgabe gehört einer Person oder einer Firma |
| `meetings` | type, title, project_id, firm_id, starts_at, duration_min, location, participants (je Zeile), protocol_status (offen/abgeschlossen), version, previous_meeting_id | |
| `agenda_items` | meeting_id, position, title, notes, auto | `auto` = Art der Live-Tabelle |
| `decisions` | meeting_id, project_id, number, text | Nummer fortlaufend je Projekt |
| `protocol_versions` | meeting_id, version, snapshot_json, finalized_at, sent_to | eingefrorene Fassungen |
| `routine_checks` | routine, period | „Wochenplanung KW 40 erledigt“ |
| `reminder_log` | key, sent_at | jede Erinnerung genau einmal |
| `schedule_items` | project_id, kind (phase/milestone), title, start/end, progress 0–100, person_id, firm_id | Zeitplan |
| `schedule_links` | pred_id, succ_id, lag_days (−365…365) | Abhängigkeiten, keine Kreise |
| `orders` | firm_id, project_id, number, title, unit (h/pt), amount, hours_per_day, valid_from/to, notes, active | Bestellungen |
| `service_records` | order_id, period_start/end, amount, description, status (eingereicht/geprueft/abgelehnt) | Leistungsnachweise |
| `time_entries` | person_id, project_id, work_date, hours (≤ 24) | nur eigene Leute und ANÜ, keine Kommentare |

## Rechenregeln

**Kennzahlen (Startseite):** überfällig = offen/in Arbeit/wartet und fällig vor heute; heute fällig; ohne Update = offen und `updated_at` älter als N Tage (Standard 7); Protokolle fehlen = Meeting vorbei (Beginn + Dauer < jetzt) und Protokoll offen; ohne Termin = offen ohne Fälligkeit.

**Auslastung:** Kapazität je Woche = Wochenstunden × Verfügbarkeit. Der Aufwand jeder offenen Aufgabe mit Zuständigkeit, Aufwand und Fälligkeit wird gleichmäßig auf die Wochen von Start (oder dieser Woche) bis zur Fälligkeitswoche verteilt; Überfälliges landet in dieser Woche. Prozent = geplante Stunden / Kapazität. Stufen: frei < 70 %, ok < 95 %, voll ≤ 105 %, überbucht > 105 %. Aufgaben ohne Aufwand oder Termin werden gezählt („ohne Aufwand/Termin“), aber nicht verteilt. Firmen: nur Stunden, keine Prozent.

**Kontingente:**
- Bestellung: abgerechnet = Summe geprüfter Nachweise; eingereicht = noch nicht geprüft; frei = Menge − abgerechnet; Verbrauch = abgerechnet / Menge. Personentage zählen mit „Stunden pro Tag“ (Standard 8).
- Stufen: ok, voll ab 80 %, über bei mehr als 100 %.
- Warnungen je aktiver Bestellung: „überschritten“, „N % verbraucht“ (ab 80 %), „läuft in N Tagen ab“ (ab 28 Tagen vorher), „abgelaufen am …“.
- Je Firma: verplant = Aufwand der Aufgaben dieser Firma (bei projektgebundenen Bestellungen nur in diesen Projekten) gegen die Summe der aktiven Bestellungen in Stunden; Warnung „überplant“ über 100 %, „N % verplant“ ab 80 %.
- Der Zähler „Team & Firmen“ in der Navigation = Anzahl Firmen mit mindestens einer Warnung.

**Zeitplan-Konflikte:** Ein Nachfolger muss frühestens beginnen am Tag nach dem Ende eines Vorgangs (bei einem Meilenstein am selben Tag) plus Puffer. Beginnt er früher, ist es ein Konflikt mit „N Tage zu früh“. „Lösen“ verschiebt den Nachfolger samt Dauer auf den frühesten Tag; dessen Nachfolger rücken mit (Kette). Beim Verschieben eines Eintrags rücken alle Nachfolger, die sonst zu früh lägen. Neue Abhängigkeiten, die einen Kreis bilden würden, werden abgelehnt. Fortschritt eines Projekts = nach Dauer (Tage) gewichteter Fortschritt der Vorgänge; Meilensteine zählen nicht mit.

**Projektstatus-Ampeln (Monatsbericht):**
- Termine: rot bei Konflikt oder verpasstem Meilenstein; gelb bei verspätetem Vorgang oder überfälliger Aufgabe; grau ohne Zeitplan und ohne Aufgaben; sonst grün.
- Kontingent: grau ohne Bestellung; rot bei Überschreitung oder abgelaufener Bestellung; gelb bei sonstiger Warnung; sonst grün.
- Aufgaben: grau ohne Aufgaben; rot bei mindestens 3 überfälligen, die mehr als ein Viertel der offenen sind; gelb bei sonstigen überfälligen; sonst grün.
- Gesamtampel = schlechteste der drei.

**Routinen:** Wochenplanung (15 Min., Mo–Mi bis erledigt), Wochenabschluss (10 Min., Fr), Monatsbericht (30 Min., ab dem letzten Arbeitstag eines Monats bis zum dritten Arbeitstag des nächsten). „Erledigt“ gilt für die Periode (KW bzw. Monat).

**Erinnerungen** (Push über ntfy und/oder E-Mail, Uhrzeiten einstellbar): Morgen-Zusammenfassung 07:30 („Guten Morgen“: „Aufgaben: 5 überfällig · 2 heute fällig · 3 Protokoll(e) fehlen · 2 Meeting(s) heute · 1 Konflikt(e) im Zeitplan · 1 Kontingent-Warnung(en)“, nur Teile mit Wert > 0, nur wenn es etwas gibt), Wochenplanung Mo 08:45, Wochenabschluss Fr 13:45, Meeting-Vorbereitung 15:00 für Meetings am nächsten Arbeitstag, Monatsbericht 09:00. Jede Erinnerung wird höchstens einmal geschickt; verpasste werden bis zu 3 Stunden nachgeholt. Nachts eine Datenbank-Sicherung (14 Tage).

## Schnittstellen (alle nur nach Anmeldung)

Die App ist serverseitig gerendert; Formulare schicken per POST mit CSRF-Token (Feld `csrf_token` oder Kopfzeile `X-CSRF-Token`) und leiten danach weiter. Daneben gibt es vier JSON-Schnittstellen:

### `GET /suche.json?q=…` (Karteikasten)

- `q` höchstens 100 Zeichen; Wörter unter 2 Zeichen werden ignoriert, höchstens 5 Wörter; jedes Wort muss in einem der Felder vorkommen (`LIKE` mit maskierten `%` und `_`).
- Antwort: `{"treffer": [{"titel", "gruppe", "hinweis", "url"}]}`, höchstens 12, in dieser Reihenfolge: Projekte (4; Name, Kürzel, Auftraggeber; Hinweis „Kürzel · Status“), Aufgaben (5; Titel, Beschreibung; offene zuerst, nach Fälligkeit; Hinweis „Status · fällig TT.MM.JJJJ · Projekt“), Meetings (4; Titel, Art, Ort, Teilnehmende; neueste zuerst; Hinweis Datum und Uhrzeit), Personen (3), Firmen (3), Bestellungen (3; Hinweis Firma).

### `GET /assistent?frage=…` (Frag das Cockpit)

- Mit `Accept: application/json`: `{"absaetze": ["…"], "links": [{"text", "url", "info"}]}` (höchstens 6 Links). Sonst eine HTML-Seite mit derselben Antwort.
- Frage auf 200 Zeichen gekürzt. Umlaute werden für die Erkennung vereinheitlicht (ä → ae usw.). Die Themen werden in dieser Reihenfolge geprüft, das erste passende gewinnt:

| Thema | Stichwörter (Auszug) | Antwort |
|---|---|---|
| Hilfe | hilfe, was kannst, wie funktioniert | was der Assistent kann, Beispielfragen |
| Überfällig | überfällig, verspätet, verzug, zu spät | „5 Aufgaben sind überfällig.“ + die 6 ältesten mit Datum und Zuständigen + „Alle überfälligen Aufgaben“ |
| Protokolle | protokoll | Anzahl offener Protokolle + Meetings |
| Kontingente | kontingent, bestellung, budget, abrechn, leistungsnachweis | Firmen mit Warnungen oder „alle im grünen Bereich“ + „Verplant / bestellt: Firma 85 %, …“ + Links mit freien Stunden |
| Zeitplan | konflikt, zeitplan, meilenstein, gantt, verschieb | Konflikte („„Testphase“ beginnt 4 Tage zu früh nach „Export““), verpasste Meilensteine, nächster Meilenstein |
| Auslastung | auslastung, überbucht, überlast, kapazität, wer hat zeit | Personen über 100 % in den nächsten drei Wochen mit KW |
| Stunden | stunden, zeiterfassung, erfasst, zeiten | erfasste Stunden dieser Woche, Anzahl Personen |
| Meetings | meeting, termin, besprechung, jour fixe, kalender | nächstes Meeting mit Ort + bis zu 5 kommende |
| Heute | heute, steht an | heute fällige Aufgaben und heutige Meetings mit Uhrzeit |
| Woche | woche, zusammenfass, überblick, stand | KW mit Datum, fällig bis Sonntag, Meetings, überfällig, fehlende Protokolle, Meilensteine der Woche, Konflikte |
| sonst | | Suche mit den Wörtern ohne Füllwörter („was“, „ist“, „die“ …); „Dazu habe ich N Treffer gefunden:“ oder „Dazu habe ich nichts gefunden.“ mit Beispielfragen |

### `POST /berichte/status/senden` (Papierflieger)

- Formular: `monat` (JJJJ-MM), `projekt` (optional), `recipients` (bis 20 Adressen, getrennt durch Komma, Semikolon oder Leerzeichen), `csrf_token`.
- Mit Kopfzeile `X-Cockpit-Ajax: 1`: Antwort `{"ok": true|false, "nachricht": "…"}` (z. B. „Statusbericht an 2 Empfänger versendet.“, „Bitte bis zu 20 gültige E-Mail-Adressen angeben, getrennt durch Komma.“, „E-Mail-Versand ist nicht eingerichtet (siehe Einstellungen).“). Ohne die Kopfzeile: Meldung und Weiterleitung.

### `POST /meetings/<id>` mit Kopfzeile `X-Autosave: 1` (Protokoll speichern)

Antwort 204 bei Erfolg, 400 mit `{"error": "…"}` bei ungültiger Eingabe, 409 wenn das Protokoll abgeschlossen ist, 401 wenn die Sitzung abgelaufen ist.

### Fehler

Alle Fehler (400, 401, 403, 404, 405, 413, 500) als Seite mit Grafik (siehe `01`). Mit `Accept: application/json` oder den Kopfzeilen `X-Autosave` / `X-Cockpit-Ajax` stattdessen JSON `{"ok": false, "error": "…", "nachricht": "…"}` mit dem Status. Keine technischen Einzelheiten in der Antwort.

### Darstellung speichern: `POST /einstellungen/darstellung`

Felder `theme`, `modus`, `akzent`, `schrift`, `ecken`, `menue`, `zahlen`, `grafik`; jeder Wert muss aus der festen Liste stammen, sonst Fehlermeldung „… hat einen ungültigen Wert“. Unbekannte Felder werden abgelehnt.

### Startseite speichern: `POST /startseite`

`order` (Liste der Bausteine), `show`, `wide`, optional `move` („key:up|down“), `reset`, `done`. Gespeichert als JSON-Liste `[{"k": "kennzahlen", "v": true, "w": true}, …]` in `users.dashboard`.

## Weitere Seiten-Adressen

`/` Start, `/aufgaben` (Filter `ansicht=ueberfaellig|heute|woche|ohne_update|ohne_termin`, `projekt`, `zustaendig`, `status`, `q`), `/aufgaben/<id>`, `/meetings`, `/meetings/<id>`, `/meetings/<id>/druck`, `/projekte`, `/projekte/<id>`, `/zeitplan?projekt=<id>`, `/zeitplan/<id>`, `/zeiten?person=<id>&woche=JJJJ-Www`, `/zeiten/team`, `/auslastung`, `/berichte`, `/berichte/status?monat=JJJJ-MM&projekt=<id>`, `/team`, `/team/personen/<id>`, `/team/firmen/<id>`, `/bestellungen/<id>`, `/einstellungen`, `/anmelden`, `/einrichten`, `/health`. CSV: `/aufgaben/export.csv`, `/zeiten/export.csv`, `/berichte/kontingente.csv`.
