# 1. Produkt und Seiten

## Worum es geht

Das Projekt-Cockpit ist ein Werkzeug für eine Projektleitung, die mehrere Projekte gleichzeitig führt: mit eigenen Leuten, mit Personen von Firmen in Arbeitnehmerüberlassung (ANÜ) und mit Firmen unter Werk- oder Dienstvertrag. Es beantwortet jeden Morgen drei Fragen: Was ist überfällig? Was steht heute an? Wo droht ein Engpass (Termine, Kontingente, Auslastung)?

- **Nutzer:** eine Person (Projektleitung) mit einem Konto. Mehrere Benutzer mit Rechten sind noch nicht gebaut.
- **Sprache:** Deutsch, Du-Form, Datumsformat `TT.MM.JJJJ`, Wochen als „KW 40“, Wochenstart Montag, Zahlen mit Komma.
- **Fachlicher Hintergrund:** `referenz-code/projekt-cockpit/docs/konzept.md` (Ziel, Kapazität, Meetings, Erinnerungen, Datenschutz) und `docs/lead-engineer-aufgaben.md` (welche Aufgaben eine Projektleitung pro Woche hat).
- **Rechtliche Leitplanke:** Leute von Firmen mit Werk- oder Dienstvertrag werden nie einzeln eingeplant oder bewertet, nur die Firma als Ganzes (Arbeitnehmerüberlassungsgesetz). Stunden werden nur für eigene Leute und ANÜ erfasst.

## Seitenübersicht

```
Anmelden ─┬─ Start (Startseite mit Bausteinen)        ← Strg+K springt von überall überall hin
          │    └─ Startseite anpassen
          ├─ Aufgaben ── Aufgabe bearbeiten
          ├─ Meetings ── Meeting / Protokoll ── abgeschlossenes Protokoll ── Druckansicht
          ├─ Projekte ── Projekt
          ├─ Zeitplan ── Zeitplan eines Projekts ── Eintrag bearbeiten
          ├─ Zeiten ── Zeiten im Team
          ├─ Auslastung
          ├─ Berichte ── Projektstatus (drucken, per E-Mail senden)
          ├─ Team & Firmen ── Person │ Firma ── Bestellung (mit Kassenbon)
          ├─ Einstellungen (Darstellung, Startseite, Erinnerungen, Kanäle, Passwort, Sicherung)
          ├─ Frag das Cockpit (Seite ohne JavaScript; normal als Baustein auf der Startseite)
          └─ Fehlerseiten: 404 nicht gefunden, 400, 401, 403, 405, 413, 500
Konto erstellen (nur beim allerersten Start, mit Einrichtungscode)
```

Navigation in der Seitenleiste, gegliedert in drei Abschnitte:

| Abschnitt | Einträge | Zähler (rotes Abzeichen) |
|---|---|---|
| Menü | Start, Aufgaben, Meetings | Aufgaben: überfällige; Meetings: fehlende Protokolle |
| Planung | Projekte, Zeitplan, Zeiten, Auslastung | Zeitplan: Konflikte |
| Allgemein | Berichte, Team & Firmen, Einstellungen | Team & Firmen: Firmen mit Kontingent-Warnung |

Oben in der Leiste: Logo mit Name, Pfeil zum Einklappen, Profil (Kürzel im Avatar, Name, „Projektleitung“, führt zu den Einstellungen), Suche (Aufgaben, mit Knopf „Strg K“ für den Karteikasten). Unten: Abmelden. Details zu Seitenleiste, Menü-Stilen und Handy-Dock in `02-design-system.md`.

Jede Seite hat oben eine Kopfzeile (`page-head`): links Überschrift und Unterzeile, rechts Aktionen. Meldungen nach dem Speichern erscheinen als Leiste unter der Kopfzeile (grün „ok“, rot „error“).

---

## Seiten im Einzelnen

Bilder: `vorschau/seiten/` (Design Glas, Zahlen als Fallblatt), Handy: `vorschau/handy/`.

### Anmelden — `vorschau/seiten/23-anmelden-*.webp`

Login im Stil „Login form V7“: Logo und Name über einer abgeschrägten Glaskarte. Die Karte klappt beim Öffnen aus einer kleinen Logo-Kachel auf (Ablauf in `03`, Abschnitt Login V7). Felder Benutzername und Passwort mit Symbolen links, Auge rechts zum Anzeigen des Passworts, großer Knopf „Anmelden →“. Darunter: „Passwort vergessen? Auf dem Server `python -m cockpit.manage passwort NAME` ausführen“. Die Anmeldeseite merkt sich das zuletzt gewählte Design über Cookies, damit sie schon vor dem Login richtig aussieht. Nach 5 Fehlversuchen pro IP ist 15 Minuten gesperrt.

### Konto erstellen — `vorschau/seiten/24-konto-erstellen.webp`

Nur solange es kein Konto gibt. Breitere V7-Karte mit zwei Spalten: links Schlüssel und Schloss, rechts Formular: Einrichtungscode (steht im Container-Log und in `EINRICHTUNGSCODE.txt`), Benutzername, Passwort mit Stärke-Anzeige und fünf Regeln, Passwort wiederholen, „Konto anlegen →“, darunter der Schloss-Status. Auf dem Handy steht der Schlüssel über dem Formular. Ablauf von Schlüssel und Schloss in `03`.

### Start — `vorschau/seiten/01-start.webp`, `vorschau/designs/`

Kopfzeile: „Do 01.10.2026 · KW 40“, darunter „Guten Morgen./Guten Tag./Guten Abend. Das steht heute an.“ (vor 11 Uhr, vor 17 Uhr, danach). Rechts „Startseite anpassen“.

Darunter Bausteine in einem Raster (schmal = halbe Breite, breit = volle Breite). Reihenfolge, Sichtbarkeit und Breite sind je Konto gespeichert. Standard-Reihenfolge:

| Baustein | Inhalt | Standard |
|---|---|---|
| Kennzahlen | fünf Kacheln: überfällig (rot, wenn > 0), heute fällig (gelb), seit N Tagen ohne Update (gelb), Protokolle fehlen (rot), ohne Termin; jede Kachel verlinkt auf die gefilterte Liste; Zahlen als Fallblatt-Anzeige | breit |
| Frag das Cockpit | Orb-Eingabebox (siehe `03`) | breit |
| Routinen | fällige Routine mit Dauer und Checkliste, Knopf „Erledigt“ (Wochenplanung Mo–Mi, Wochenabschluss Fr, Monatsbericht in den letzten/ersten Arbeitstagen) | breit, nur sichtbar, wenn etwas fällig ist |
| Schnellerfassung | neue Aufgabe in einer Zeile: Titel, Projekt, zuständig, fällig, Aufwand (h), „Anlegen“ | breit |
| Nächstes Meeting | groß mit Countdown („in 45 min“, „in 2 h 10 min“, „morgen“, „in 3 Tagen“, „läuft“), Ort, offene Maßnahmen aus früheren Terminen | schmal |
| Überfällig | bis 12 überfällige Aufgaben, Gesamtzahl | schmal |
| Meetings | heute und am nächsten Arbeitstag | schmal |
| Diese Woche | bis Sonntag fällige Aufgaben | schmal |
| Protokoll fehlt | vergangene Meetings ohne abgeschlossenes Protokoll | schmal |
| Projekte | je aktivem Projekt Fortschritt (Balken), nächster Meilenstein, Konflikte | schmal |
| Kalender | Monat mit Punkten für Meetings, Fristen, Meilensteine; Monat blättern | schmal |
| Zeitplan | Konflikte, verpasste und nächste Meilensteine | schmal |
| Kontingente | je Firma verplant/abgerechnet mit Balken und Warnungen | schmal |
| Auslastung | wer in den nächsten zwei Wochen voll oder überbucht ist | schmal |
| Zeiten | erfasste Projektstunden dieser Woche, offene Nachweise | aus |

### Startseite anpassen — `vorschau/seiten/02-startseite-anpassen.webp`

Gleiche Seite im Bearbeitungsmodus. Jeder Baustein bekommt eine Werkzeugleiste: Griff „⠿“, Name, Häkchen „anzeigen“ und „breit“, Pfeile ↑/↓. Bausteine lassen sich mit der Maus ziehen (eine Linie zeigt die Einfügestelle). „anzeigen“ und „breit“ wirken sofort in der Vorschau. Kopfzeile: „Fertig“ (speichert), „Standard“ (mit Rückfrage), „Abbrechen“. Ohne JavaScript funktionieren die Pfeile als Formular-Knöpfe. Bausteine, die in einer späteren Version dazukommen, erscheinen bei bestehenden Konten hinter ihrem Vorgänger aus der Standard-Reihenfolge.

### Aufgaben — `vorschau/seiten/03-aufgaben.webp`

- Kopf: Anzahl, gewählte Schnellansicht, „Als CSV exportieren“ (Semikolon, mit BOM für Excel).
- Schnellerfassung wie auf der Startseite (übernimmt gewähltes Projekt und Zuständige).
- Schnellansichten als Chips: Alle offenen, Überfällig, Heute fällig, Diese Woche fällig, Ohne Update, Ohne Termin.
- Filter: Projekt (auch „ohne Projekt“), zuständig (Person, Firma oder „niemand“), Status (alle offenen, erledigt/abgenommen, alle, einzelne), Suchtext.
- Tabelle: Häkchen, Titel (überfällige rot), Projekt, zuständig, fällig, Status als Auswahl, die sofort speichert, Aktion „Stand bestätigen“ (setzt „zuletzt aktualisiert“, ohne etwas zu ändern).
- Sammelbearbeitung für markierte Aufgaben: Status setzen, verschieben (neues Datum), zuweisen, löschen (mit Rückfrage).
- Status: offen, in Arbeit, wartet (mit „wartet auf …“), erledigt, abgenommen. Priorität 1–3.

### Aufgabe bearbeiten — `vorschau/seiten/04-aufgabe-bearbeiten.webp`

Alle Felder: Titel, Beschreibung, Projekt, zuständig, Aufwand (h), Start, fällig, Status, wartet auf, Priorität, zugehöriges Meeting. Knöpfe: Speichern, Stand bestätigen, Aufgabe löschen.

### Meetings — `vorschau/seiten/05-meetings.webp`

Drei Listen: „Protokoll fehlt“ (Anker `#fehlt`), „Nächste 30 Tage“, „Abgeschlossene Protokolle“. Rechts „Neues Meeting“ (Anker `#neu`): Vorlage, Titel, Projekt, Firma, Beginn, Dauer, Ort, Teilnehmende (eine Person je Zeile).

Acht Vorlagen mit eigener Tagesordnung und Dauer: Jour fixe (45 Min.), Kick-off mit Firma (90), Internes Team-Meeting, Projektstatus Management, Abnahme einer Lieferung, Eskalationsgespräch, Lessons Learned, Sonstiges. Manche Tagesordnungspunkte füllen sich live mit Daten: offene Maßnahmen aus früheren Terminen, offene Aufgaben der Firma, überfällige und diese Woche fällige Aufgaben, Auslastung der nächsten zwei Wochen, Status der aktiven Projekte.

### Meeting / Protokoll — `vorschau/seiten/06-meeting-protokoll.webp`

Ein Bildschirm zum Mitschreiben während des Termins:
- Termin und Teilnehmende (aufklappbar).
- Tagesordnung mit Notizfeld je Punkt; Punkte hinzufügen und löschen; Live-Tabellen bei den automatischen Punkten.
- Entscheidungen: Text, wird mit fortlaufender Nummer je Projekt festgehalten (E-12).
- Maßnahmen: Titel, zuständig, fällig; werden sofort echte Aufgaben mit Verweis auf das Meeting.
- Nächster Termin: „Folgetermin anlegen“ übernimmt Vorlage, Firma, Projekt und Teilnehmende.
- Notizen speichern automatisch 1,5 Sekunden nach dem letzten Tippen, mit Statusanzeige („Gespeichert um 10:42“).
- „Protokoll abschließen“: „Abschließen“ oder „Abschließen und senden“ (E-Mail an die Teilnehmenden). Danach ist die Version eingefroren.

Abgeschlossenes Protokoll: Lesefassung, „Drucken / PDF“, „Erneut senden“, „Korrektur beginnen“ (öffnet eine neue Version), Versionsliste mit Datum und Empfängern. Druckansicht immer schwarz auf weiß.

### Projekte — `vorschau/seiten/07-projekte.webp`

Tabelle: Projekt (Kürzel und Name), Auftraggeber, Status (geplant, aktiv, pausiert, abgeschlossen), offene und überfällige Aufgaben, nächstes Meeting, Ende. Aufklappbar „Neues Projekt“ (Anker `#neu`).

### Projekt — `vorschau/seiten/08-projekt.webp`

Kopf mit Kürzel · Name, Knöpfe „Zeitplan“, „Meeting anlegen“, „Alle Aufgaben“. Inhalte: offene Aufgaben, Entscheidungsregister (Nr., Entscheidung, Meeting), Meetings, Bestellungen mit Verbrauch, Stunden Plan/Ist, Formular „Projekt bearbeiten“, „Projekt löschen“.

### Zeitplan — `vorschau/seiten/09-zeitplan-alle.webp`, `10-zeitplan-projekt.webp`, `11-zeitplan-eintrag.webp`

- Gantt-Diagramm als SVG, vom Server gezeichnet: eine Zeile je Vorgang (Balken mit Fortschritt) oder Meilenstein (Raute), Monatsraster, Linie für heute, Pfeile für Abhängigkeiten. Konflikte (Nachfolger beginnt vor dem Ende des Vorgängers plus Puffer) sind rot.
- Gesamtansicht über alle aktiven und geplanten Projekte, oder je Projekt (Auswahl oben).
- Je Projekt: Tabelle der Einträge (Art, Bezeichnung, Start, Ende, Stand, zuständig), „Neuer Eintrag“ (Anker `#neu`; Vorgang mit Start/Ende/Fortschritt oder Meilenstein mit Datum), nächste Meilensteine, „Verpasst oder verspätet“.
- Eintrag bearbeiten: Felder, Vorgänger und Nachfolger mit Puffer in Tagen (auch projektübergreifend), „Diesen Eintrag verschieben“ (Nachfolger rücken mit), Konflikt mit einem Klick lösen. Kreise in den Abhängigkeiten werden verhindert.

### Zeiten — `vorschau/seiten/12-zeiten.webp`, `13-zeiten-team.webp`

Wochen-Stundenzettel je Person: Zeilen = Projekte, Spalten = Mo–So (Wochenende abgesetzt), Summen je Zeile, Tag und Woche, die sich beim Tippen sofort aktualisieren. Woche blättern, „Woche speichern“, „Vorwoche übernehmen“. Nur eigene Leute und ANÜ. „Zeiten im Team“: Summen je Person und Tag, je Projekt.

### Auslastung — `vorschau/seiten/14-auslastung.webp`

Personen: Kapazität je Woche (Wochenstunden × Verfügbarkeit), sechs Wochen als Prozent mit Ampelfarbe (frei unter 70 %, ok unter 95 %, voll 95–105 %, überbucht über 105 %), offene Aufgaben, Aufgaben ohne Aufwand oder Termin. Firmen: Aufwand offen in Stunden je Woche, Kontingent verplant. Rechenregel in `04`.

### Berichte — `vorschau/seiten/15-berichte.webp`

- Projektstatus: Monat und Projekt wählen, „Bericht öffnen“.
- Exporte als CSV: Aufgaben, Projektstunden je Monat, Kontingente.
- Protokoll-Archiv mit Filter (Projekt, Firma, Zeitraum), Version, Empfänger, „Drucken / PDF“.

### Projektstatus — `vorschau/seiten/16-projektstatus.webp`

Monatsbericht: Übersichtstabelle mit Ampeln je Projekt (Termine, Kontingent, Aufgaben: rot „handeln“, gelb „beobachten“, grün „im Plan“, grau „keine Daten“) und Fortschritt; je Projekt Meilensteine, Risiken im Zeitplan, Aufgaben, Stunden, Entscheidungen, Meetings, Kontingente. „Drucken / als PDF speichern“. Aufklappbar „Per E-Mail senden“ mit Empfängern (bis 20 Adressen, durch Komma getrennt); das Formular faltet sich beim Senden zum Papierflieger (siehe `03`).

### Team & Firmen — `vorschau/seiten/17-team.webp`, `18-firma.webp`, `19-person.webp`

- Personen: Name, Rolle, Stunden pro Woche, Verfügbarkeit (z. B. 80 %), offene Aufgaben; Firma, falls ANÜ. „Person anlegen“ (Anker `#neue-person`).
- Firmen: Name, Vertragsart (Werkvertrag, Dienstvertrag, Arbeitnehmerüberlassung), Ansprechpartner, offene Aufgaben. „Firma anlegen“ (Anker `#neue-firma`).
- Firma: „Jour fixe anlegen“, Bestellungen und Kontingent (Bestellung, Projekt, Menge, abgerechnet, Verbrauch als Balken, läuft bis), „Neue Bestellung“, offene Aufgaben, Meetings, Personen in ANÜ, bearbeiten, löschen.
- Person: offene Aufgaben, bearbeiten, löschen.

### Bestellung — `vorschau/seiten/20-bestellung.webp`

Kopf: Bestellnummer · Bezeichnung, Menge, Projekt, Laufzeit. Vier Kennzahlen: bestellt, abgerechnet (mit %), frei, eingereicht und noch nicht geprüft. Verbrauchsbalken, Warnungen. Leistungsnachweise: Zeitraum, Leistung, Menge, Status als Auswahl (eingereicht, geprüft, abgelehnt), löschen; „Nachweis eintragen“. Aufgaben an diese Firma. Rechts der **Kassenbon** (Übersicht oder Nachweise, siehe `03`), darunter „Bestellung bearbeiten“ und „Bestellung löschen“. Einheit Stunden oder Personentage (mit Stunden pro Tag).

### Einstellungen — `vorschau/seiten/21-einstellungen.webp`, `vorschau/navigation/darstellung-einstellungen.webp`

1. **Darstellung:** Design (fünf Karten mit Mini-Vorschau), Hell oder dunkel, Akzentfarbe (Farbkreise), Schriftgröße (Aa klein/normal/groß), Ecken, Zahlen, Menü-Stil (zehn Kacheln mit Mini-Menü), Grafik für Fehlerseiten (sieben Kacheln mit kleinem Bild, darunter eine Vorschau der gewählten Grafik in Bewegung und der Link „404-Seite öffnen“). Rechts eine Vorschau (Kennzahlen, Karte, Knöpfe, Menü). Jede Änderung wirkt sofort auf die ganze Seite; unten erscheint die Leiste „N Änderungen · Verwerfen · Übernehmen“. Ablauf in `03`.
2. **Startseite:** „Startseite anpassen“, „Auf Standard zurücksetzen“.
3. **Erinnerungen:** Uhrzeiten für Morgen-Zusammenfassung (07:30), Wochenplanung (Mo 08:45), Wochenabschluss (Fr 13:45), Meeting-Vorbereitung (15:00 am Vortag), Monatsbericht (09:00); „ohne Update“ nach N Tagen (7); Erinnerungen an/aus.
4. **Kanäle:** Status von Push (ntfy) und E-Mail (SMTP), Hinweis, dass Zugangsdaten nur in `.env` stehen, „Testnachricht senden“.
5. **Passwort ändern:** aktuelles Passwort, neues mit Schlüssel und Schloss, wiederholen (Anker `#passwort`).
6. **Sicherung:** tägliche Kopie (14 Tage), „Aktuelle Datenbank herunterladen“, Liste der automatischen Sicherungen.

### Frag das Cockpit ohne JavaScript — `vorschau/seiten/22-frag-das-cockpit-ohne-js.webp`

Fallback-Seite `/assistent?frage=…`: Eingabefeld, die Frage als Sprechblase, Antwortabsätze und Linkliste. Mit JavaScript läuft alles im Baustein auf der Startseite.

### Fehlerseiten — `vorschau/fehlerseiten/`

Eine Vorlage für alle Fehler. Zwei Spalten (Handy: Grafik oben): links eine große, bewegte Grafik, rechts „FEHLER 404“ (klein, gesperrt), Überschrift, Erklärung, bei 404 die aufgerufene Adresse, Knöpfe „Zur Startseite“, „Zurück“ (geht im Verlauf zurück, wenn man von der eigenen Seite kam) und „Suchen Strg K“, darunter „Oder direkt zu: Aufgaben · Meetings · Projekte · Zeitplan · Berichte“.

| Status | Überschrift | Kurztext in der Grafik | Erklärung |
|---|---|---|---|
| 404 | Seite nicht gefunden | NICHT GEFUNDEN | Diese Seite gibt es nicht (mehr). Vielleicht wurde der Eintrag gelöscht, oder der Link ist falsch geschrieben. |
| 400 | Das hat nicht geklappt | UNGÜLTIG | Die Anfrage war ungültig. / Das Formular ist abgelaufen. Bitte Seite neu laden. |
| 401 | Bitte neu anmelden | BITTE ANMELDEN | Bitte neu anmelden. |
| 403 | Kein Zutritt | KEIN ZUTRITT | Dafür fehlt die Berechtigung. |
| 405 | So geht das nicht | NICHT ERLAUBT | Diese Adresse lässt sich so nicht aufrufen. |
| 413 | Zu groß | ZU GROSS | Die Anfrage ist zu groß. |
| 500 | Etwas ist schiefgelaufen | STÖRUNG | Ein interner Fehler ist aufgetreten. Bitte die Seite neu laden oder später noch einmal versuchen. |

Welche Grafik erscheint, stellt man unter *Einstellungen → Darstellung → Grafik für Fehlerseiten* ein; ohne Wahl passend zum Design (Violett Abfahrtstafel, Glas Schwarzes Loch, Bronze Kassenbon, Hell Papierflieger, Schlicht Karteikasten). Ablauf der Grafiken in `03`, Abschnitt 10. Anfragen mit `Accept: application/json` (und Autospeichern, Papierflieger) bekommen statt der Seite `{"ok": false, "error": "…", "nachricht": "…"}`. Scheitert die Fehlerseite selbst (z. B. Datenbank weg), kommt ein schlichter Text ohne Einzelheiten. Nicht angemeldete Besucher werden bei unbekannten Adressen zur Anmeldung geleitet.

### Überall: Karteikasten (Strg+K / ⌘K)

Auf jeder Seite nach dem Login. Siehe `03`.

---

## Handy (bis 900 px Breite) — `vorschau/handy/`

- Oben eine schmale Leiste mit Logo, Avatar und Abmelden; das Menü wird zum Dock am unteren Rand (Symbole mit Beschriftung, Zähler als rote Punkte, waagerecht scrollbar, im gewählten Menü-Stil).
- Bausteine und Spalten stehen untereinander; Tabellen scrollen in ihrem eigenen Rahmen waagerecht.
- Kennzahlen zwei pro Zeile.
- Karteikasten, Orb, Kassenbon, Schlüssel und Papierflieger funktionieren auch per Touch.
