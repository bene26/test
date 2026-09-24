# Konzept: Projekt-Cockpit

*Arbeitstitel. Stand: Entwurf v0.2, September 2026*

**Umsetzung:** Stufe 1 ist als Version 0.1 umgesetzt, siehe [`README.md`](../README.md) und [`installation-ugreen.md`](installation-ugreen.md).

**Änderungen gegenüber v0.1:** Aufgabenverteilung, externe Firmen, Meetings mit Protokollen und Erinnerungen sind dazugekommen. Die Kapazitätsplanung aus v0.1 steht jetzt in Abschnitt 6.

## 1. Ziel

Du leitest mehrere Projekte parallel und verteilst viele Aufgaben, teils an eigene Leute, oft aber an externe Firmen. Das Tool hat vier Säulen:

1. **Aufgaben** verteilen und nachhalten: wer macht was bis wann, und was ist überfällig?
2. **Kapazität:** Auslastung der eigenen Leute und Kontingente der externen Firmen
3. **Meetings:** vorbereiten, protokollieren, Entscheidungen und Maßnahmen ablegen
4. **Erinnerungen,** damit das Tool gepflegt wird und nichts liegen bleibt

**Was das Tool bewusst nicht ist:**

- kein Ersatz für die Ticketsysteme der Entwickler: Aufgaben hier sind Arbeitspakete und Maßnahmen auf Steuerungsebene
- keine Zeiterfassung und kein HR-System
- kein Werkzeug zur Leistungskontrolle

## 2. Alltagstauglichkeit

Die Tools, die du dir angesehen hast, waren im laufenden Betrieb zu umständlich. Deshalb gelten diese Regeln für jede Funktion:

- **Schnellerfassung:** Eine Aufgabe ist mit einer Zeile erfasst (Titel, zuständig, fällig, Enter), auch vom Handy aus.
- **Eintragen wie in Excel:** direkt in Tabellen tippen, mit Tab und Enter weiter, ohne Formulare.
- **Viele Aufgaben auf einmal bearbeiten:** mehrere markieren, dann verschieben, neu zuweisen oder abschließen.
- **Wenig Pflichtfelder:** Was du nicht sofort weißt, bleibt leer.
- **Die Startseite zeigt, was heute zählt,** statt einer leeren Übersicht.
- **Das Tool meldet sich von selbst** (Abschnitt 8). Du musst nicht daran denken, es zu öffnen.

Ziel: **15 Minuten am Montag, 10 Minuten am Freitag,** dazu die Protokolle direkt im Meeting.

## 3. Interne und externe Mitarbeiter

Eigene Leute und externe Firmen werden unterschiedlich geplant:

|                           | Intern                          | Externe Firma (Werk- oder Dienstvertrag) |
|---------------------------|---------------------------------|------------------------------------------|
| **Aufgaben gehen an**     | die Person                      | die Firma, also ihren Ansprechpartner    |
| **Geplant wird**          | Stunden pro Person und Woche    | Kontingent (Stunden oder Personentage), Liefertermine |
| **Urlaub und Abwesenheit** | im Tool                        | nicht im Tool; die Firma meldet, wenn sie weniger Kapazität hat |
| **Auslastung**            | Prozent pro Person              | Kontingent-Verbrauch und Termintreue pro Firma |

**Warum der Unterschied wichtig ist:** Wenn du externen Mitarbeitenden direkt Aufgaben gibst, ihre Arbeitszeit planst und ihren Urlaub verwaltest, kann das als **verdeckte Arbeitnehmerüberlassung** gewertet werden. Mögliche Folgen sind Bußgelder, und im ungünstigsten Fall gelten die Externen rechtlich als bei euch angestellt. Bei Werk- und Dienstverträgen gehen Aufträge deshalb an die Firma, und die verteilt sie intern selbst. Nur bei einem Vertrag über Arbeitnehmerüberlassung ist es zulässig, Externe direkt anzuweisen und wie eigene Leute zu planen.

Das Tool bildet das über die **Vertragsart je Firma** ab:

- **Werk- oder Dienstvertrag:** Aufgaben gehen an die Firma, geplant wird über ein Kontingent. Einzelne externe Personen tauchen nur als Ansprechpartner oder Meeting-Teilnehmer auf.
- **Arbeitnehmerüberlassung:** Die Personen der Firma werden wie interne Mitarbeitende geplant.

Welche Vertragsart gilt, weiß euer Einkauf. Die Grenzen im Detail klärt ihr am besten mit der Rechtsabteilung.

## 4. Datenmodell

```
Projekt
 ├── Aufgaben ─────── zuständig: interne Person oder externe Firma
 ├── Zuteilungen ──── interne Person, Stunden pro Woche
 ├── Kontingente ──── externe Firma, Stunden oder Personentage, Zeitraum
 ├── Bedarf ───────── Stunden pro Woche, optional je Rolle
 ├── Meilensteine
 └── Meetings
      ├── Entscheidungen
      └── Maßnahmen ─ werden automatisch zu Aufgaben

Person ── Abwesenheiten (nur intern bzw. Arbeitnehmerüberlassung)
Firma ─── Ansprechpartner, Vertragsart
Feiertage je Bundesland
```

| Objekt          | Wichtigste Felder |
|-----------------|-------------------|
| **Projekt**     | Name, Kürzel, Auftraggeber, Status, Priorität, Start, Ende, Stundenbudget |
| **Person**      | Name, Rolle, Wochenstunden, Arbeitstage, Verfügbarkeitsfaktor, Firma (leer = intern) |
| **Firma**       | Name, Vertragsart, Ansprechpartner mit E-Mail |
| **Kontingent**  | Firma, Projekt(e), Menge in Stunden oder Personentagen, Zeitraum, Bestellnummer |
| **Aufgabe**     | Projekt, Titel, Beschreibung, zuständig (Person oder Firma), Aufwand, fällig, Status, Priorität, Herkunft (z. B. Meeting), letzte Aktualisierung |
| **Meeting**     | Projekt oder Firma, Typ, Datum, Teilnehmende, Agenda, Notizen, Protokoll-Status |
| **Entscheidung** | Meeting, Nummer, Text |
| **Zuteilung**   | Person, Projekt, Kalenderwoche, Stunden |
| **Abwesenheit** | Person, von, bis, halber Tag, Art (Urlaub, Schulung, Sonstiges) |

## 5. Aufgaben

**Status:** offen → in Arbeit → wartet (auf wen?) → erledigt → abgenommen

„Abgenommen“ ist für Lieferungen externer Firmen gedacht: Die Arbeit ist geprüft und passt. Bei Werkverträgen hängen Rechnung und Gewährleistung daran.

**Ansichten:**

- **Meine Woche:** überfällig, diese Woche fällig, seit 7 Tagen ohne Aktualisierung
- **Nach Firma:** alle offenen Aufgaben einer Firma über alle Projekte hinweg; das ist gleichzeitig die Grundlage für den Jour fixe mit ihr
- **Nach Projekt:** Liste oder Kanban-Board
- **Nach Person:** für interne Mitarbeitende

**Aufwand:** Optional. Bei externen Firmen wird er gegen das Kontingent gerechnet („verplant“), bei internen Personen fließt er in die Auslastung ein.

## 6. Kapazität

### 6.1 Interne Mitarbeitende

**Rechnung pro Person und Woche:**

```
Brutto-Kapazität = Wochenstunden − Abwesenheiten − Feiertage
Netto-Kapazität  = Brutto-Kapazität × Verfügbarkeitsfaktor (Standard 80 %)
Auslastung       = zugeteilte Stunden ÷ Netto-Kapazität
```

**Beispiel:** Anna hat 40 h/Woche und in KW 42 einen Urlaubstag.
Netto-Kapazität: (40 h − 8 h) × 0,8 = 25,6 h. Zugeteilt sind 28 h, das ergibt **109 %: überbucht**.

**Ampel** (Grenzen einstellbar):

| Auslastung  | Farbe | Bedeutung       |
|-------------|-------|-----------------|
| unter 70 %  | blau  | freie Kapazität |
| 70–95 %     | grün  | gut ausgelastet |
| 95–105 %    | gelb  | voll            |
| über 105 %  | rot   | überbucht       |

**Kapazitäts-Übersicht:**

```
Kapazität            KW 40    KW 41    KW 42    KW 43   KW 44
───────────────────────────────────────────────────────────────
▾ Anna  (40 h)        88 %     94 %    109 % ●   75 %    50 %
    Projekt A         16 h     16 h     16 h     16 h     8 h
    Projekt B         12 h     14 h     12 h      8 h     8 h
    Abwesend            –        –      1 Tag      –       –
▾ Ben   (30 h)        50 %     50 %    Urlaub    50 %    50 %
    Projekt A         12 h     12 h       –      12 h    12 h
▸ Carla (40 h)       125 % ●  125 % ●  100 %     63 %    38 %
───────────────────────────────────────────────────────────────
Projekt A  Bedarf     48 h     48 h     40 h     40 h    32 h
           zugeteilt  44 h     44 h     24 h     36 h    24 h
           fehlt      −4 h     −4 h    −16 h     −4 h    −8 h

● = überbucht (in der App rot eingefärbt)
```

### 6.2 Externe Firmen

```
Firma        Kontingent   verplant          frei    abgerechnet   läuft bis
───────────────────────────────────────────────────────────────────────────
Firma Alpha  200 h        180 h (90 %)      20 h    120 h         31.12.
Firma Beta    60 PT        64 PT (107 %) ●  −4 PT    30 PT        30.11.

● = mehr Aufgaben vergeben als bestellt: Nachbestellung oder Umfang kürzen
```

- **verplant:** Summe der Aufwände aller Aufgaben, die an die Firma gehen
- **abgerechnet:** laut Rechnung oder Leistungsnachweis, von Hand eingetragen
- **Warnungen:** bei 80 % verplant, bei Überplanung und 4 Wochen vor Ablauf

## 7. Meetings

### 7.1 Meeting-Typen mit Agenda-Vorlagen

Jeder Typ bringt eine Agenda-Vorlage mit. Offene Maßnahmen aus dem letzten Termin werden automatisch als erster Punkt eingefügt.

**Kick-off mit einer externen Firma**
*einmalig pro Auftrag, 60–90 min; du, Projektleitung der Firma, ggf. Fachbereich*

1. Ziele und Umfang des Auftrags: was gehört dazu, was nicht
2. Ansprechpartner und Vertretungen auf beiden Seiten
3. Liefergegenstände, Termine, Meilensteine
4. Abnahmekriterien: Wann gilt etwas als fertig?
5. Kommunikation: Jour fixe, Kanäle, Eskalationsweg
6. Umgang mit Änderungen und Nachträgen
7. Zugänge, Werkzeuge, Geheimhaltung, ggf. Vertrag zur Auftragsverarbeitung (falls die Firma personenbezogene Daten verarbeitet)
8. Offene Fragen, nächste Schritte

**Jour fixe mit einer Firma**
*wöchentlich oder alle 2 Wochen, 30–45 min*

1. Offene Maßnahmen aus dem letzten Termin *(automatisch)*
2. Stand der Aufgaben der Firma, überfällige zuerst *(automatisch)*
3. Blocker und Risiken: Was braucht die Firma von uns?
4. Termine und Kontingent-Stand
5. Entscheidungen
6. Neue Aufgaben und Maßnahmen

Tipp: Arbeitet eine Firma in mehreren deiner Projekte, genügt ein gemeinsamer Jour fixe. Das Tool baut die Agenda projektübergreifend.

**Internes Team-Meeting**
*wöchentlich, 30 min*

1. Kapazität: Wer ist überbucht, wer hat Luft, wer ist abwesend? *(automatisch)*
2. Überfällige und diese Woche fällige Aufgaben *(automatisch)*
3. Blocker und Abstimmungsbedarf
4. Neuigkeiten aus Projekten und Management

**Projektstatus für Management oder Lenkungskreis**
*monatlich, 30–60 min*

1. Ampel je Projekt: Termine, Budget bzw. Kontingent, Qualität *(automatisch)*
2. Erreichte und nächste Meilensteine
3. Die wichtigsten Risiken und Gegenmaßnahmen
4. Entscheidungen, die das Management treffen muss
5. Engpässe bei Kapazität und Kontingenten, Nachbestellungen

**Abnahme einer Lieferung**
*bei Lieferung, 30–60 min*

1. Was wurde geliefert? (Bezug zu Aufgabe und Bestellung)
2. Prüfung gegen die Abnahmekriterien
3. Mängel mit Frist
4. Ergebnis: abgenommen, abgenommen mit Mängeln oder nicht abgenommen

Das Protokoll ist hier das Abnahmeprotokoll und damit Grundlage für Rechnung und Gewährleistung.

**Eskalationsgespräch**
*bei Bedarf*

1. Sachverhalt: Fakten, Termine, Auswirkungen
2. Ursachen aus Sicht beider Seiten
3. Lösungsoptionen
4. Vereinbarung mit Verantwortlichen und Termin

**Lessons Learned**
*zum Projektende, 60 min*

1. Was lief gut?
2. Was lief schlecht?
3. Was machen wir im nächsten Projekt anders?
4. Bewertung der Dienstleister (nur intern)

### 7.2 Aufbau eines Protokolls

```
JOUR FIXE · Projekt A · Firma Alpha · Mi 07.10.2026, 10:00–10:40
Teilnehmende: Projektleitung (Protokoll), Projektleitung Firma Alpha, Anna

Offene Maßnahmen aus dem letzten Termin
  ✓ M-12  Testumgebung bereitstellen           Anna          02.10.
  ✗ M-14  Schnittstellenbeschreibung liefern   Firma Alpha   05.10.  überfällig

Notizen
  2. Import-Modul zu 80 % fertig, Export startet in KW 42
  3. Firma Alpha wartet auf Testdaten

Entscheidungen
  E-07  Das Export-Format wird CSV, nicht XML.

Maßnahmen
  M-14  Schnittstellenbeschreibung liefern     Firma Alpha   09.10.  (neuer Termin)
  M-15  Testdaten bereitstellen                Anna          09.10.

Nächster Termin: Mi 14.10.2026, 10:00
```

### 7.3 Ablauf

- **Vorher:** Das Tool erstellt die Agenda aus der Vorlage, den offenen Maßnahmen und den überfälligen Aufgaben. Am Vortag kommt eine Erinnerung.
- **Währenddessen:** live mitschreiben; eine Maßnahme (Was, Wer, Bis wann) ist eine Zeile und landet sofort als Aufgabe im Tool.
- **Danach:** Protokoll mit einem Klick als PDF oder E-Mail an alle Teilnehmenden. Fehlt es am nächsten Tag noch, kommt eine Erinnerung.

### 7.4 Ablage

- Protokolle liegen je Projekt und je Firma und sind durchsuchbar.
- **Entscheidungsregister:** Alle Entscheidungen eines Projekts stehen auf einer Seite. Das hilft, wenn später über Nachträge oder Umfang diskutiert wird.
- **Nach dem Versand wird ein Protokoll eingefroren.** Korrekturen werden als neue Version gespeichert, damit nachvollziehbar bleibt, was verschickt wurde.

## 8. Erinnerungen

### 8.1 Feste Routinen

| Wann                      | Erinnerung                     | Inhalt |
|---------------------------|--------------------------------|--------|
| Montag, 8:45              | Wochenplanung (15 min)         | Checkliste: Abwesenheiten, rote Zellen, überfällige Aufgaben, Meetings der Woche |
| Vortag eines Meetings     | Meeting vorbereiten            | Link zur vorbereiteten Agenda |
| Freitag, 13:45            | Wochenabschluss (10 min)       | Status der Aufgaben aktualisieren, fehlende Protokolle |
| Monatsende                | Monatsbericht                  | Kontingente prüfen, Statusbericht für das Management |

### 8.2 Erinnerungen bei Ereignissen

Das Tool prüft täglich und meldet sich, wenn:

- eine Aufgabe morgen fällig oder schon überfällig ist
- eine Aufgabe seit 7 Tagen nicht aktualisiert wurde
- ein Meeting gestern war und das Protokoll fehlt
- eine Maßnahme aus einem Meeting überfällig ist
- das Kontingent einer Firma zu 80 % verplant ist oder in 4 Wochen ausläuft
- jemand in den nächsten 2 Wochen überbucht ist
- für die nächste Woche noch keine Planung existiert

### 8.3 Kanäle

- **Push aufs Handy** über ntfy: läuft als kleiner Container neben dem Tool, mit App für Android und iOS
- **E-Mail:** eine Zusammenfassung am Morgen statt vieler Einzelmails
- **Microsoft Teams:** Nachricht in einen Kanal oder Chat, falls ihr Teams nutzt
- **Outlook-Kalender:** Fälligkeiten, Meetings und Routinen als Kalender-Abonnement

### 8.4 Damit Erinnerungen nicht nerven

- gebündelt: eine Meldung morgens, nicht zwanzig über den Tag verteilt
- direkt aus der Meldung heraus „erledigt“ oder „morgen erinnern“ wählen
- Ruhezeiten am Abend und am Wochenende
- Eine Erinnerung verschwindet erst, wenn die Sache erledigt ist. Ist die Wochenplanung am Dienstag noch offen, kommt sie noch einmal.

### 8.5 Startseite

```
Mo 05.10.2026 · KW 41
───────────────────────────────────────────────────────────────
Pflege-Stand     Planung bis KW 44 ✓ · 6 Aufgaben seit 7 Tagen ohne Update ●
Heute fällig     3 Aufgaben
Überfällig       5 Aufgaben, davon 4 bei Firma Alpha
Protokoll fehlt  Jour fixe Firma Beta vom Fr 02.10.
Heute            10:00 Jour fixe Firma Alpha · Agenda bereit
Kapazität        Carla überbucht in KW 41
Kontingente      Firma Alpha 90 % verplant · Firma Beta überplant (107 %)
```

## 9. Ausbaustufen

**Vorschlag für die Reihenfolge:** Aufgaben, Meetings und Erinnerungen zuerst. Das brauchst du jeden Tag, und dabei entstehen die Daten, auf denen die Kapazitätsplanung aufbaut. Eine einfache Auslastung (offene Aufgaben und Aufwand je Person oder Firma) gibt es schon in Stufe 1.

**Stufe 1: MVP**

- Projekte, interne Personen, Firmen mit Ansprechpartnern und Vertragsart
- Aufgaben mit Schnellerfassung, Status, Fälligkeit und Sammelbearbeitung
- Meetings mit Vorlagen, Protokoll, Entscheidungen; Maßnahmen werden zu Aufgaben
- Protokoll als PDF oder E-Mail versenden
- Erinnerungen: feste Routinen, fällige Aufgaben, fehlende Protokolle; per Push und E-Mail
- Startseite
- einfache Auslastung aus offenen Aufgaben je Person und Firma
- ein Login (nur du), Docker-Image, tägliches Backup

**Stufe 2**

- volle Kapazitätsplanung intern: Zuteilungen, Bedarf, Abwesenheiten, Feiertage, Ampel-Übersicht
- Kontingente je Firma
- Meilensteine und Projekt-Zeitleiste
- automatischer Statusbericht für das Management
- Status-Anfrage per E-Mail an Firmen vor dem Jour fixe
- Aufgaben aus weitergeleiteten E-Mails anlegen
- Kalender-Abonnement und Teams-Anbindung
- Änderungsprotokoll: wer hat wann was geändert

**Stufe 3**

- **Firmenportal:** Externe Firmen sehen ihre Aufgaben und aktualisieren den Status selbst. Das spart dir viel Nachfragen, bedeutet aber, dass das Tool von außen erreichbar sein muss (siehe Abschnitt 10).
- Zugänge für das eigene Team und das Management
- Szenarien („Was wäre, wenn …“)
- Aufwände aus Jira oder GitHub übernehmen
- Projektvorlagen, z. B. die Projektstart-Checkliste aus `lead-engineer-aufgaben.md`

## 10. Datenschutz, Recht und Sicherheit

### Recht

- **Arbeitnehmerüberlassung:** siehe Abschnitt 3.
- **DSGVO:** Das Tool speichert personenbezogene Daten von eigenen und externen Personen (Namen, Kontaktdaten, Teilnahme an Meetings, Auslastung, Abwesenheiten). Nur speichern, was nötig ist: keine Gründe für Abwesenheiten (Krankheit ist ein Gesundheitsdatum nach Art. 9 DSGVO), keine Gehälter, keine Leistungsbewertungen einzelner Personen.
- **Betriebsrat:** Falls es einen gibt, ist die Auslastungsplanung eigener Mitarbeitender sehr wahrscheinlich mitbestimmungspflichtig (§ 87 Abs. 1 Nr. 6 BetrVG). Früh ansprechen.
- **Standort:** Firmendaten auf einem privaten Raspberry Pi sollten vorher mit IT oder Datenschutz abgestimmt sein.

### Bedrohungsbild (Kurzfassung)

- **Schützenswert:** Protokolle mit Vertragsinhalten, Preisen und Entscheidungen; Kontaktdaten externer Personen; Auslastung und Abwesenheiten der eigenen Leute.
- **Schlimmster realistischer Fall:** Das Tool steht offen im Internet, und Protokolle oder Personendaten gelangen nach außen. Oder jemand ändert unbemerkt Entscheidungen oder Protokolle.

### Technische Grundregeln

- Stufen 1 und 2: nicht ins Internet stellen, nur im LAN oder über VPN erreichbar
- Login mit starkem Passwort, Rechte werden auf dem Server geprüft
- HTTPS über einen Reverse Proxy
- **Erinnerungen enthalten keine Details,** nur z. B. „3 Aufgaben überfällig“ mit Link. Push-Nachrichten laufen je nach Handy über fremde Server.
- tägliches, verschlüsseltes Backup; Wiederherstellung einmal testen
- keine Zugangsdaten im Code, Konfiguration über Umgebungsvariablen
- **Firmenportal (Stufe 3):** Jede Firma sieht nur ihre eigenen Aufgaben, streng serverseitig geprüft, mit Zwei-Faktor-Anmeldung. Das ist ein großer Sicherheitsschritt und kommt deshalb zuletzt.

Vor dem ersten Code wird daraus eine `SECURITY.md` im Projekt.

## 11. Technik (Skizze)

- Web-App im Browser, auf dem Handy als App installierbar (PWA)
- **ein Container für das Tool** plus ein kleiner Container für ntfy (Push); optional ein Reverse Proxy
- Images für ARM64 (Raspberry Pi 4/5) und x86 (normaler Docker-Host)
- **SQLite als Datenbank:** eine Datei, einfaches Backup, reicht für diese Datenmengen
- Erinnerungen laufen als geplante Jobs im Tool selbst
- E-Mail-Versand über den Mailserver der Firma (Zugang über die IT)
- PDF-Erzeugung für Protokolle und Berichte im Tool, ohne externe Dienste
- Import aus CSV/Excel, damit bestehende Listen übernommen werden können

## 12. Offene Fragen

1. Wie viele Projekte, eigene Leute, externe Firmen und offene Aufgaben sind es ungefähr?
2. Welche Vertragsarten habt ihr mit den Firmen (Werkvertrag, Dienstvertrag, Arbeitnehmerüberlassung)? Werden Kontingente in Stunden, Personentagen oder als Festpreis vereinbart?
3. Sollen die Firmen später selbst im Tool den Status pflegen, oder läuft alles über dich?
4. Über welche Kanäle willst du erinnert werden: Handy-Push, E-Mail, Teams, Outlook-Kalender?
5. Welche Meetings hast du heute schon regelmäßig?
6. Wo liegen Protokolle bisher (SharePoint, Confluence, Word-Dateien)? Muss das Tool dort etwas ablegen?
7. Passt die Reihenfolge: Aufgaben, Meetings und Erinnerungen vor der vollen Kapazitätsplanung?
8. Gibt es einen Betriebsrat? Steht der Raspberry Pi bei dir zu Hause oder in der Firma? Welches Bundesland?
