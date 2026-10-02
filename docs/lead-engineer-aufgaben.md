# Lead Engineer: Aufgaben und Zeitaufwand

Diese Übersicht listet, was neben der eigenen Entwicklungsarbeit auf einen Lead Engineer zukommt, und schätzt den Aufwand pro Woche.

**Annahmen, auf denen die Zahlen beruhen:**

- Team mit 4–7 Personen in der Entwicklung
- Scrum oder Kanban mit 2-Wochen-Sprints
- 40-Stunden-Woche
- Es gibt einen Product Owner oder Projektleiter, der fachliche Prioritäten und Budget verantwortet. Der Lead Engineer führt fachlich und technisch, nicht disziplinarisch.

Weichen die Rahmenbedingungen ab, verschieben sich die Stunden (siehe [Wie sich die Stunden verschieben](#wie-sich-die-stunden-verschieben)).

## Überblick

| #  | Bereich                                   | h/Woche   | Ø       |
|----|-------------------------------------------|-----------|---------|
|    | **A. Projektmanagement & Organisation**   |           |         |
| 1  | Agile Regeltermine                        | 4–5       | 4,5     |
| 2  | Anforderungen, Backlog & Tickets          | 3–5       | 4       |
| 3  | Stakeholder-Kommunikation & Reporting     | 1,5–3     | 2       |
| 4  | Risiken, Abhängigkeiten & Blocker         | 1–2       | 1,5     |
| 5  | Release-Planung & -Koordination           | 0,5–1,5   | 1       |
| 6  | Kapazität, Prozess & Tooling              | 0,5–1,5   | 1       |
|    | **B. Technische Führung**                 |           |         |
| 7  | Architektur & technische Entscheidungen   | 2–4       | 3       |
| 8  | Code Reviews & Qualitätssicherung         | 3–5       | 4       |
| 9  | Team-Führung & Mentoring                  | 2–3,5     | 2,5     |
| 10 | Dokumentation & Wissensmanagement         | 0,5–1,5   | 1       |
| 11 | Betrieb & Incidents                       | 0–2       | 1       |
|    | **Summe Lead-Aufgaben**                   | **18–34** | **~25** |
|    | Verbleibend für eigene Entwicklung        |           | ~15     |

**Faustregel:** etwa 60 % Führung und Organisation, 40 % selbst entwickeln.

Phasenweise kommen dazu: Recruiting und Bewerbungsgespräche (0–4 h/Woche).

---

## A. Projektmanagement & Organisation

### 1. Agile Regeltermine (4–5 h)

| Termin               | Rhythmus      | Dauer  | h/Woche |
|----------------------|---------------|--------|---------|
| Daily Stand-up       | täglich       | 15 min | 1,25    |
| Sprint Planning      | alle 2 Wochen | 2 h    | 1,0     |
| Backlog Refinement   | wöchentlich   | 1 h    | 1,0     |
| Sprint Review / Demo | alle 2 Wochen | 1 h    | 0,5     |
| Retrospektive        | alle 2 Wochen | 1 h    | 0,5     |
| Vor- und Nachbereitung |             |        | 0,5     |

### 2. Anforderungen, Backlog & Tickets (3–5 h)

- Anforderungen mit PO bzw. Fachbereich klären, Rückfragen beantworten
- Epics in Stories und technische Tasks zerlegen
- Akzeptanzkriterien und technische Hinweise in Tickets schreiben
- Aufwände gemeinsam mit dem Team schätzen, Abhängigkeiten markieren
- Technische Schulden sichtbar machen und einplanen (Richtwert: 15–20 % der Sprint-Kapazität)
- Board aktuell halten, Tickets zuweisen

### 3. Stakeholder-Kommunikation & Reporting (1,5–3 h)

- Abstimmung mit PO, Projektleitung und Management
- Absprachen mit anderen Teams (Schnittstellen, APIs, gemeinsame Termine)
- Statusbericht: Fortschritt, Risiken, nächste Meilensteine
- Erwartungen steuern: Was ist bis wann realistisch?

### 4. Risiken, Abhängigkeiten & Blocker (1–2 h)

- Risikoliste führen (Wahrscheinlichkeit, Auswirkung, Gegenmaßnahme)
- Blocker aus dem Daily aktiv auflösen
- Externe Abhängigkeiten nachverfolgen (Dienstleister, andere Teams, Freigaben)

### 5. Release-Planung & -Koordination (0,5–1,5 h)

- Umfang des Releases festlegen, Versionierung, Release Notes
- Deployment-Termine abstimmen, Go/No-Go-Entscheidung
- Rollback-Plan bereithalten

### 6. Kapazität, Prozess & Tooling (0,5–1,5 h)

- Kapazität pro Sprint planen (Urlaub, Krankheit, Feiertage)
- Kennzahlen beobachten: Velocity, Cycle Time, offene Bugs
- Maßnahmen aus der Retro umsetzen und nachhalten
- Board, Workflows und Vorlagen (Issue-/PR-Templates) pflegen

---

## B. Technische Führung

### 7. Architektur & technische Entscheidungen (2–4 h)

- Architektur entwerfen und weiterentwickeln
- Entscheidungen festhalten (Architecture Decision Records, ADRs)
- Technologien auswählen, Spikes und Prototypen bewerten
- Coding-Standards und Richtlinien festlegen

### 8. Code Reviews & Qualitätssicherung (3–5 h)

- Pull Requests reviewen, vor allem kritische und architekturrelevante
- Teststrategie und Testabdeckung, CI/CD-Pipeline stabil halten
- Definition of Done durchsetzen
- Sicherheit und Performance im Blick behalten

### 9. Team-Führung & Mentoring (2–3,5 h)

- 1:1-Gespräche, z. B. 30 min alle 2 Wochen pro Person (bei 6 Personen: 1,5 h/Woche)
- Mentoring, Pair Programming, fachliche Unterstützung
- Onboarding neuer Teammitglieder
- Feedback geben, Konflikte früh ansprechen

### 10. Dokumentation & Wissensmanagement (0,5–1,5 h)

- README, Architekturübersicht, Setup-Anleitung
- Runbooks für den Betrieb
- Wissen im Team verteilen, damit nichts an einer einzelnen Person hängt

### 11. Betrieb & Incidents (0–2 h, schwankt stark)

- Rufbereitschaft bzw. Eskalationsstelle
- Incidents koordinieren, Postmortems durchführen

---

## Einmalige Aufgaben zum Projektstart

Diese Punkte fallen einmal an, verteilt auf die ersten 2–4 Wochen.

| Aufgabe                                                        | Aufwand |
|----------------------------------------------------------------|---------|
| Kick-off vorbereiten und durchführen                           | 4–6 h   |
| Ziele, Umfang und Nicht-Ziele festhalten                       | 2–4 h   |
| Rollen und Verantwortlichkeiten klären (wer entscheidet was?)  | 1–2 h   |
| Board aufsetzen (Spalten, Labels, Issue-/PR-Templates)         | 2–3 h   |
| Definition of Ready und Definition of Done festlegen           | 1–2 h   |
| Repository, Branching-Strategie, CI/CD-Grundgerüst             | 4–8 h   |
| Coding-Guidelines, Linting, Formatierung                       | 2–3 h   |
| Erste Architektur-Skizze und erste ADRs                        | 4–8 h   |
| Initiales Backlog, Grobschätzung, Roadmap mit Meilensteinen    | 4–8 h   |
| Risikoliste anlegen                                            | 1–2 h   |
| Kommunikationsplan (Termine, Kanäle, Reporting-Rhythmus)       | 1 h     |
| Onboarding-Doku und Setup-Anleitung                            | 2–4 h   |
| **Summe**                                                      | **ca. 30–50 h** |

---

## Wie sich die Stunden verschieben

| Situation                                                    | Auswirkung auf Lead-Aufgaben |
|--------------------------------------------------------------|------------------------------|
| Kleines Team (2–3 Personen)                                  | 10–15 h/Woche                |
| Mittleres Team (4–7 Personen), Basis dieser Liste            | 20–30 h/Woche                |
| Großes Team (8+ Personen)                                    | 30–40 h/Woche, kaum noch eigenes Coding. Team teilen oder Scrum Master/PM dazuholen |
| Kein PO oder Projektleiter vorhanden                         | +4–8 h (Priorisierung, Budget, Zeitplan, Stakeholder) |
| Scrum Master vorhanden                                       | −1–2 h (Moderation der Termine entfällt) |
| Disziplinarische Führung (Beurteilungen, Gehalt, Urlaub)     | +2–4 h                       |

Auch die Projektphase spielt mit: Am Anfang fallen mehr Architektur und Planung an, kurz vor Releases mehr Koordination und Reviews.

## Tipps

- Feste Fokuszeit für die eigene Entwicklung blocken, z. B. 2–3 Vormittage ohne Meetings. Sonst frisst die Koordination die ganze Woche.
- Reviews auf das Team verteilen und selbst nur die kritischen Stellen übernehmen, damit du nicht zum Flaschenhals wirst.
- Einmal pro Woche 30 min zurückschauen: Wofür ging die Zeit drauf? Nach 3–4 Wochen die Schätzungen oben an die eigene Realität anpassen.
