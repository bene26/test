# 6. Abnahme-Checkliste

Zum Abhaken nach der Übernahme. Jeder Punkt ist im Browser oder mit einem Test prüfbar. Punkte für Teile, die nicht übernommen werden, streichen.

## Design und Darstellung

- [ ] Alle fünf Designs sehen aus wie in `vorschau/designs/` (Farben, Schriften, Ecken, Hintergrund-Lichter, Navigation).
- [ ] Jedes Design lässt sich hell und dunkel schalten; „wie im Design“ nimmt den Standard; Schlicht folgt ohne Wahl dem Gerät.
- [ ] Sieben Akzentfarben wirken auf Knöpfe, Links, aktiven Menüpunkt, Fokus-Rahmen; Kontrast in hell und dunkel mindestens 4,5 : 1.
- [ ] Schriftgröße klein/normal/groß ändert die ganze Seite (93,75 % / 100 % / 112,5 %).
- [ ] Ecken rund/weich/kantig ändern Karten, Felder und Knöpfe; Bronze bleibt abgeschrägt.
- [ ] Jede Auswahl in den Einstellungen wirkt sofort auf die ganze Seite; die Leiste zeigt die Zahl der Änderungen; „Verwerfen“ stellt den alten Stand her; „Übernehmen“ speichert und bleibt nach Neuladen und auf einem anderen Gerät erhalten.
- [ ] Die Anmeldeseite zeigt das zuletzt gewählte Design.
- [ ] Ungültige Werte (z. B. `akzent=#ff0000`) werden auf dem Server abgelehnt.

## Navigation

- [ ] Seitenleiste mit Profil, Suche, drei Abschnitten, Zählern (überfällig, Protokolle, Konflikte, Kontingent-Warnungen) und Abmelden.
- [ ] Pfeil klappt auf 84 px Symbolleiste ein und wieder aus; der Zustand bleibt nach Neuladen.
- [ ] Bronze und Schlicht zeigen die Leiste oben.
- [ ] Unter 900 px Breite ist das Menü ein Dock unten, die Seite scrollt nicht seitlich.
- [ ] Alle zehn Menü-Stile sind wählbar und sehen aus wie in `vorschau/navigation/`; Orbit, Welle und Blob bewegen sich, Liquid springt beim Laden auf.

## Komponenten

- [ ] **Fallblatt:** Kennzahlen rattern beim Öffnen von links nach rechts durch Zufallszeichen auf den Wert (1–2 s); in Violett standardmäßig, sonst mit „Zahlen: Fallblatt“; „Schlicht“ schaltet es ab, auch in Violett.
- [ ] **Schlüssel:** jede erfüllte Regel schneidet sichtbar einen Zahn mit Spänen; Stärke-Zeile zählt „N von 5“; bei 12 Zeichen und gleicher Wiederholung fährt der Schlüssel ins Schloss, dreht sich, der Bügel springt auf, Status „ENTSPERRT“; zu kurzes Passwort wird vom Server abgelehnt.
- [ ] **Kassenbon:** druckt beim ersten Sichtbarwerden Zeile für Zeile mit „DRUCKT …“ und blinkender LED; Wechsel auf „Nachweise“ reißt den alten Beleg ab und druckt neu; Werte stimmen mit der Bestellung überein.
- [ ] **Karteikasten:** Strg+K / ⌘K öffnet auf jeder Seite; ↑ ↓ blättert, hintere Karten stehen schräg dahinter, vordere fallen nach vorn; Tippen filtert, ab 2 Zeichen kommen Treffer vom Server; Enter öffnet; Esc schließt und gibt den Fokus zurück; „g“ + „a“ springt zu den Aufgaben; „Neues Meeting“ öffnet das Formular mit Cursor im ersten Feld.
- [ ] **Papierflieger:** beim Senden faltet sich das Formular in vier Schritten zum Flieger, fliegt mit Spur nach rechts oben weg, danach „Unterwegs.“ mit Adressen; bei einem Fehler faltet es sich zurück und zeigt den Grund.
- [ ] **Orb:** zwölf Kugeln wählbar, die Wahl bleibt; Kugel reagiert auf Tippen, denkt schneller, jedes Wort der Antwort gibt einen Schub; Antworten auf „Was ist überfällig?“, „Fasse meine Woche zusammen“, „Wie stehen die Kontingente?“, „Gibt es Konflikte im Zeitplan?“, „Wer ist überbucht?“ stimmen mit den Daten; unbekannte Fragen führen zur Suche; Esc zeigt die Antwort sofort.
- [ ] **Login V7:** Karte klappt aus der Logo-Kachel auf; Auge zeigt das Passwort.
- [ ] Mit „Bewegung reduzieren“ läuft keine Animation, alles ist trotzdem bedienbar.
- [ ] Ohne JavaScript lassen sich alle Formulare abschicken, Kassenbon und Zahlen sind lesbar.

## Fehlerseiten

- [ ] Eine unbekannte Adresse zeigt die 404-Seite mit Status 404, Überschrift „Seite nicht gefunden“, der Adresse (maskiert) und den Wegen zurück.
- [ ] Unter *Darstellung → Grafik für Fehlerseiten* lassen sich sechs Grafiken wählen; die Vorschau darunter wechselt und läuft sofort; nach „Übernehmen“ zeigt die 404-Seite die gewählte Grafik.
- [ ] „Wie im Design“: Violett Abfahrtstafel, Glas Schwarzes Loch, Bronze Kassenbon, Hell Papierflieger, Schlicht Karteikasten.
- [ ] Jede Grafik bewegt sich wie in `03`, Abschnitt 10; nur die sichtbare läuft; bei „Bewegung reduzieren“ steht sie still und ist lesbar.
- [ ] 400 (abgelaufenes Formular), 405 und 500 zeigen deutsche Texte ohne technische Einzelheiten; Anfragen mit `Accept: application/json` bekommen JSON.
- [ ] „Zurück“ geht im Verlauf zurück, wenn man von der eigenen Seite kam, sonst zur Startseite.

## Fachfunktionen

- [ ] Startseite: Bausteine ein-/ausblenden, breit/schmal, ziehen und mit Pfeilen sortieren; „Standard“ setzt zurück; gespeichert je Konto.
- [ ] Aufgaben: Schnellerfassung, sechs Schnellansichten, Filter, Status in der Liste, Sammelbearbeitung, CSV mit Umlauten in Excel.
- [ ] Meetings: acht Vorlagen mit Tagesordnung und Live-Tabellen; Notizen speichern automatisch; Entscheidungen nummeriert je Projekt; Maßnahmen werden Aufgaben; Folgetermin; Abschließen friert ein; Korrektur erzeugt neue Version.
- [ ] Zeitplan: Gantt mit Abhängigkeiten; Konflikt rot; „Lösen“ verschiebt Nachfolger samt Kette; Kreise werden abgelehnt.
- [ ] Kontingente: Warnungen bei 80 %, Überschreitung und 28 Tage vor Ablauf; Zähler in der Navigation.
- [ ] Auslastung: Prozent je Person und Woche wie in `04` berechnet, Stufen-Farben.
- [ ] Zeiten: Summen beim Tippen, Vorwoche übernehmen, nur eigene Leute und ANÜ.
- [ ] Berichte: Projektstatus mit Ampeln wie in `04`, Druck schwarz auf weiß, E-Mail-Versand.
- [ ] Erinnerungen kommen zu den eingestellten Zeiten genau einmal.

## Sicherheit

- [ ] Jede Seite außer Anmelden, Einrichten und Health verlangt Anmeldung (auch `/suche.json` und `/assistent`).
- [ ] POST ohne gültiges CSRF-Token wird abgelehnt.
- [ ] Die Frage `<b>Hallo</b>` erscheint als Text, nicht fett.
- [ ] Suche nach `_%` findet nichts, Suche nach `100%` findet nur Einträge mit „100%“.
- [ ] Keine Geheimnisse im Code; Content-Security-Policy ohne `unsafe-inline` funktioniert.
