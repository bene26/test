"""Meeting types with their agenda templates.

An agenda item with an `auto` kind shows live data from the tool
(e.g. open actions) and is captured in the protocol when it is finalized.
"""

AUTO_KINDS = {
    "open_actions": "Offene Maßnahmen aus früheren Terminen",
    "firm_tasks": "Offene Aufgaben der Firma",
    "due_tasks": "Überfällige und diese Woche fällige Aufgaben",
    "team_capacity": "Auslastung der nächsten zwei Wochen",
    "project_status": "Status der aktiven Projekte",
}

MEETING_TYPES = {
    "jourfixe": {
        "label": "Jour fixe",
        "duration": 45,
        "agenda": [
            ("Offene Maßnahmen aus dem letzten Termin", "open_actions"),
            ("Stand der Aufgaben, überfällige zuerst", "firm_tasks"),
            ("Blocker und Risiken: Was wird von uns gebraucht?", None),
            ("Termine und Kontingent-Stand", None),
            ("Sonstiges", None),
        ],
    },
    "kickoff": {
        "label": "Kick-off mit Firma",
        "duration": 90,
        "agenda": [
            ("Ziele und Umfang des Auftrags: was gehört dazu, was nicht", None),
            ("Ansprechpartner und Vertretungen auf beiden Seiten", None),
            ("Liefergegenstände, Termine, Meilensteine", None),
            ("Abnahmekriterien: Wann gilt etwas als fertig?", None),
            ("Kommunikation: Jour fixe, Kanäle, Eskalationsweg", None),
            ("Umgang mit Änderungen und Nachträgen", None),
            ("Zugänge, Werkzeuge, Geheimhaltung, ggf. Auftragsverarbeitung", None),
            ("Offene Fragen", None),
        ],
    },
    "team": {
        "label": "Internes Team-Meeting",
        "duration": 30,
        "agenda": [
            ("Kapazität: Wer ist überbucht, wer hat Luft?", "team_capacity"),
            ("Überfällige und diese Woche fällige Aufgaben", "due_tasks"),
            ("Blocker und Abstimmungsbedarf", None),
            ("Neuigkeiten aus Projekten und Management", None),
        ],
    },
    "management": {
        "label": "Projektstatus Management",
        "duration": 60,
        "agenda": [
            ("Status je Projekt", "project_status"),
            ("Erreichte und nächste Meilensteine", None),
            ("Wichtigste Risiken und Gegenmaßnahmen", None),
            ("Entscheidungsbedarf für das Management", None),
            ("Engpässe bei Kapazität und Kontingenten", None),
        ],
    },
    "abnahme": {
        "label": "Abnahme einer Lieferung",
        "duration": 45,
        "agenda": [
            ("Was wurde geliefert? (Bezug zu Aufgabe und Bestellung)", None),
            ("Prüfung gegen die Abnahmekriterien", None),
            ("Mängel mit Frist", None),
            ("Ergebnis: abgenommen, mit Mängeln abgenommen oder nicht abgenommen", None),
        ],
    },
    "eskalation": {
        "label": "Eskalationsgespräch",
        "duration": 60,
        "agenda": [
            ("Sachverhalt: Fakten, Termine, Auswirkungen", None),
            ("Ursachen aus Sicht beider Seiten", None),
            ("Lösungsoptionen", None),
            ("Vereinbarung mit Verantwortlichen und Termin", None),
        ],
    },
    "lessons": {
        "label": "Lessons Learned",
        "duration": 60,
        "agenda": [
            ("Was lief gut?", None),
            ("Was lief schlecht?", None),
            ("Was machen wir im nächsten Projekt anders?", None),
            ("Bewertung der Dienstleister (nur intern)", None),
        ],
    },
    "sonstiges": {
        "label": "Sonstiges Meeting",
        "duration": 30,
        "agenda": [("Themen", None)],
    },
}


def label(kind: str) -> str:
    return MEETING_TYPES.get(kind, {}).get("label", kind)
