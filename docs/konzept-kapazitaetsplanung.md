# Konzept: Kapazitäts- und Projektplaner

*Arbeitstitel. Stand: Entwurf v0.1, September 2026*

## 1. Ziel

Mehrere Projekte laufen parallel, und dieselben Leute arbeiten oft in mehreren davon. Das Tool soll diese Fragen in unter einer Minute beantworten:

1. Wer ist in welcher Woche wie stark ausgelastet?
2. Wer ist überbucht, und wer hat noch Luft?
3. Hat jedes Projekt genug Leute, um seine Termine zu halten?
4. Wie viel vom Stundenbudget eines Projekts ist schon verplant?
5. Was passiert, wenn ein Projekt früher startet oder jemand ausfällt? (ab Stufe 2)

**Was das Tool bewusst nicht ist:**

- kein Ticketsystem: Aufgaben bleiben in Jira, GitHub o. Ä.
- keine Zeiterfassung (zumindest nicht im ersten Schritt)
- kein HR-System und kein Werkzeug zur Leistungskontrolle

Es plant, wer wann wie viele Stunden an welchem Projekt arbeitet, und zeigt, ob das aufgeht.

## 2. Alltagstauglichkeit

Die Tools, die du dir angesehen hast, waren im laufenden Betrieb zu umständlich. Deshalb gelten diese Regeln für jede Funktion:

- **Eintragen wie in Excel:** direkt in die Zelle der Übersicht tippen, mit Tab und Enter weiter, ohne Formulare.
- **Zeiträume statt Einzelwochen:** „16 h/Woche von KW 40 bis KW 48“ in einem Schritt.
- **Wenig Pflichtfelder:** Für eine Person reichen Name und Wochenstunden, für ein Projekt reicht der Name. Der Rest ist optional.
- **Die Startseite zeigt, wo es brennt:** Überbuchungen und fehlende Kapazität in den nächsten 4 Wochen.
- **Jede Änderung lässt sich rückgängig machen.**

Ziel für die Routine: **10–15 Minuten pro Woche.**

## 3. Datenmodell

```
Person ──< Zuteilung >── Projekt ──< Bedarf
  │                         │
  └──< Abwesenheit           └──< Meilenstein

Feiertage (je Bundesland) wirken auf alle Personen
```

| Objekt          | Felder                                                                 | Hinweis |
|-----------------|------------------------------------------------------------------------|---------|
| **Person**      | Name, Rolle (z. B. Backend, Test), Wochenstunden, Arbeitstage, Verfügbarkeitsfaktor, aktiv | Teilzeit wird über Wochenstunden und Arbeitstage abgebildet |
| **Projekt**     | Name, Kürzel, Auftraggeber, Status, Priorität, Start, Ende, Stundenbudget, Farbe | Status: geplant, aktiv, pausiert, abgeschlossen |
| **Zuteilung**   | Person, Projekt, Kalenderwoche, Stunden, Notiz                          | Herzstück. Eingabe als Zeitraum oder in Prozent, gespeichert als Stunden pro Woche |
| **Bedarf**      | Projekt, Rolle (optional), Kalenderwoche, Stunden                       | Wie viel ein Projekt braucht, unabhängig davon, wer es macht |
| **Abwesenheit** | Person, von, bis, halber Tag, Art (Urlaub, Schulung, Sonstiges)         | Bewusst ohne „krank“, siehe Abschnitt 7 |
| **Meilenstein** | Projekt, Name, Datum                                                    | ab Stufe 2 |
| **Feiertag**    | Datum, Name, Bundesland                                                 | wird als Tabelle mitgeliefert |

**Grundentscheidungen (Vorschlag):**

- **Planung in Kalenderwochen, nicht in Tagen.** Für die Projektplanung reicht das und hält die Pflege klein. Tage wären nur für Einsätze beim Kunden nötig.
- **Stunden speichern, nicht Prozent.** So passt Teilzeit sauber hinein. Die Oberfläche zeigt beides.
- **Ein Verfügbarkeitsfaktor pro Person statt pauschaler Meeting-Stunden.** Standard ist 80 %, weil ein Teil der Woche für Meetings, E-Mails und Support draufgeht. Für Lead- und PM-Rollen liegt er eher bei 40–50 % (siehe `lead-engineer-aufgaben.md`).

## 4. Rechenlogik

**Pro Person und Woche:**

```
Brutto-Kapazität = Wochenstunden − Abwesenheiten − Feiertage
Netto-Kapazität  = Brutto-Kapazität × Verfügbarkeitsfaktor
Zugeteilt        = Summe aller Zuteilungen der Woche
Auslastung       = Zugeteilt ÷ Netto-Kapazität
```

**Beispiel:** Anna hat 40 h/Woche, einen Verfügbarkeitsfaktor von 80 % und in KW 42 einen Urlaubstag.

| Schritt          | Rechnung                               | Ergebnis   |
|------------------|----------------------------------------|------------|
| Brutto-Kapazität | 40 h − 8 h                             | 32 h       |
| Netto-Kapazität  | 32 h × 0,8                             | 25,6 h     |
| Zugeteilt        | Projekt A 16 h + Projekt B 12 h        | 28 h       |
| Auslastung       | 28 ÷ 25,6                              | **109 %, überbucht** |

**Ampel** (Grenzen einstellbar):

| Auslastung  | Farbe | Bedeutung        |
|-------------|-------|------------------|
| unter 70 %  | blau  | freie Kapazität  |
| 70–95 %     | grün  | gut ausgelastet  |
| 95–105 %    | gelb  | voll             |
| über 105 %  | rot   | überbucht        |

**Pro Projekt und Woche:**

```
Deckung      = Summe Zuteilungen ÷ Bedarf     (unter 100 % = es fehlen Leute)
Budget-Stand = Summe aller Zuteilungen des Projekts ÷ Stundenbudget
```

## 5. Ansichten

### 5.1 Kapazitäts-Übersicht (Kernansicht)

Zeilen sind Personen, Spalten sind Kalenderwochen. Jede Person lässt sich aufklappen, dann erscheinen ihre Projekte. Unten steht pro Projekt der Bedarf im Vergleich zur Zuteilung.

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

Hier wird auch eingetragen: Klick in eine Projektzeile, Stunden tippen, fertig.

### 5.2 Weitere Ansichten

| Ansicht              | Inhalt |
|----------------------|--------|
| **Startseite**       | Warnliste für die nächsten 4 Wochen: überbuchte Personen, Projekte mit fehlender Kapazität, anstehende Meilensteine und Abwesenheiten |
| **Projektsicht**     | Ein Projekt: wer wann mit wie viel Stunden dabei ist, Bedarf im Vergleich zur Zuteilung, Budget-Stand |
| **Personensicht**    | Eine Person: alle Projekte, Abwesenheiten und Auslastung über die Wochen |
| **Abwesenheiten**    | Teamkalender mit Urlaub, Schulungen und Feiertagen |
| **Stammdaten**       | Personen, Projekte, Rollen, Einstellungen (Ampelgrenzen, Bundesland) |
| **Export**           | CSV/Excel, ab Stufe 2 auch PDF-Bericht für das Management |

### 5.3 Typische Abläufe

- **Montags, 10–15 Minuten:** Startseite prüfen, neue Abwesenheiten eintragen, rote Zellen in der Übersicht auflösen.
- **Neues Projekt:** Projekt anlegen und Bedarf eintragen. Die Übersicht zeigt sofort, wer Luft hat, und du teilst die Leute zu.
- **Jemand fällt aus:** Abwesenheit eintragen. Das Tool zeigt, welche Projekte dadurch Kapazität verlieren.
- **Monatlich:** Export oder Bericht an Management und Auftraggeber.

## 6. Ausbaustufen

**Stufe 1: MVP**

- Personen, Projekte, Abwesenheiten und Feiertage pflegen
- Zuteilungen pro Woche, Eingabe als Zeitraum
- Projektbedarf pro Woche, optional je Rolle
- Kapazitäts-Übersicht mit Ampel, Projektsicht, Personensicht
- Startseite mit Warnliste
- CSV/Excel-Export
- ein Login (nur du), Docker-Image, tägliches Backup

**Stufe 2**

- Meilensteine und Projekt-Zeitleiste
- Stundenbudget je Projekt
- Szenarien („Was wäre, wenn …“) als Kopie der Planung, ohne das Original zu ändern
- Skills je Person und Filter „Wer hat in KW X Zeit und kann Y?“
- PDF-Bericht
- Änderungsprotokoll: wer hat wann was geändert

**Stufe 3**

- mehrere Benutzer mit Rollen (siehe Abschnitt 7)
- Ist-Stunden aus der Zeiterfassung importieren und mit dem Plan vergleichen
- Aufwände aus Jira oder GitHub übernehmen
- Projektvorlagen, z. B. die Projektstart-Checkliste aus `lead-engineer-aufgaben.md`
- Benachrichtigung per E-Mail oder Teams bei Überbuchung

## 7. Benutzer, Datenschutz und Sicherheit

### Rollen

| Rolle                 | Darf                                                      | ab Stufe |
|-----------------------|-----------------------------------------------------------|----------|
| Admin / Projektleitung | alles                                                    | 1        |
| Teammitglied          | eigene Planung sehen, eigenen Urlaub eintragen            | 3        |
| Management            | Übersichten und Berichte lesen                            | 3        |

### Datenschutz

Das Tool speichert personenbezogene Daten (Namen, Arbeitszeiten, Abwesenheiten, Auslastung). Damit gilt die DSGVO.

- **Datensparsamkeit:** keine Gründe für Abwesenheiten, vor allem nicht „krank“. Krankheit zählt als Gesundheitsdatum und ist nach Art. 9 DSGVO besonders geschützt. Außerdem keine Gehälter und keine Leistungsbewertungen.
- **Betriebsrat:** Falls es einen gibt, ist ein System, mit dem sich die Auslastung von Mitarbeitenden auswerten lässt, sehr wahrscheinlich mitbestimmungspflichtig (§ 87 Abs. 1 Nr. 6 BetrVG). Das gilt spätestens, wenn Ist-Stunden dazukommen (Stufe 3). Früh ansprechen, bevor echte Daten drin sind.
- **Wo läuft das Tool?** Firmendaten auf einem privaten Raspberry Pi sollten vorher mit IT oder Datenschutz abgestimmt sein. Auf einem Docker-Host der Firma ist das meist einfacher.

### Bedrohungsbild (Kurzfassung)

- **Was ein Angreifer wollen würde:** Auslastungs- und Abwesenheitsdaten aller Mitarbeitenden, oder die Planung unbemerkt verändern.
- **Schlimmster realistischer Fall:** Das Tool steht offen im Internet, und die Daten gelangen nach außen.

### Technische Grundregeln

- nicht direkt ins Internet stellen, nur im LAN oder über VPN erreichbar
- Login mit starkem Passwort, Rechte werden auf dem Server geprüft, nicht nur in der Oberfläche
- HTTPS über einen Reverse Proxy
- tägliches, verschlüsseltes Backup, Wiederherstellung einmal testen
- keine Zugangsdaten im Code, Konfiguration über Umgebungsvariablen

Vor dem ersten Code wird daraus eine `SECURITY.md` im Projekt.

## 8. Technik (Skizze)

- Web-App im Browser, damit sie vom Laptop und vom Handy aus erreichbar ist
- **ein Docker-Container** plus optional ein Reverse Proxy; Images für ARM64 (Raspberry Pi 4/5) und x86 (normaler Docker-Host)
- **Vorschlag: SQLite als Datenbank.** Eine Datei, einfaches Backup, reicht locker für 1–20 Nutzer. PostgreSQL ist möglich, wenn später mehr dazukommt.
- **Alternative Supabase (self-hosted):** Das würde zu deinen anderen Apps passen, braucht aber rund ein Dutzend Container und ist für einen Pi schwergewichtig. Für dieses Tool eher nicht.
- Feiertage aller Bundesländer als mitgelieferte Tabelle, also ohne Internetzugriff
- CSV/Excel-Import, damit bestehende Planungen übernommen werden können

## 9. Offene Fragen

1. Wie viele Personen und wie viele Projekte sind es ungefähr?
2. Arbeiten die Leute parallel in mehreren Projekten, oder sind sie meist fest einem Projekt zugeordnet?
3. Wer soll das Tool nutzen: nur du, oder auch Team und Management?
4. Gibt es Stundenbudgets pro Projekt? Gibt es eine Zeiterfassung, und wenn ja, welche?
5. Reichen Kalenderwochen, oder brauchst du Tage (z. B. für Einsätze beim Kunden)?
6. Soll das Tool Daten aus Jira, GitHub oder Excel übernehmen?
7. Gibt es einen Betriebsrat? Steht der Raspberry Pi bei dir zu Hause oder in der Firma?
8. Welches Bundesland (für die Feiertage)?
