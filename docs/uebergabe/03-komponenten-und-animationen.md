# 3. Komponenten, Animationen und Übergänge

Alle Zeiten in Millisekunden (ms) oder Sekunden (s). Kurven als `cubic-bezier`. Die Referenz-Umsetzung steht in `referenz-code/projekt-cockpit/cockpit/static/komponenten.js` (sechs Komponenten, ohne Bibliotheken), `app.js` (Live-Vorschau, Seitenleiste, Startseiten-Editor) und `app.css` (Abschnitt „Komponenten“, „Menu styles“, „Login and setup (Login form V7)“). Zum Ausprobieren: `referenz-code/design-kit/komponenten.html` im Browser öffnen.

Für alle Komponenten gilt:
- **Bewegung reduzieren** (`prefers-reduced-motion: reduce`): kein Klappern, kein Drucken, kein Falten, keine Endlos-Animationen; der Endzustand erscheint sofort. Die Funktion bleibt vollständig.
- **Ohne JavaScript** bleibt jede Seite benutzbar (Formulare schicken normal ab, Inhalte stehen statisch da).
- **Strenge Content-Security-Policy:** kein Inline-Style im HTML, kein Inline-Skript. Bewegungen über CSS-Klassen, CSS-Variablen, `element.style` per Skript und die Web Animations API (`element.animate`).
- Alles folgt den Design-Tokens; nichts hat feste Farben außer Papier, Metall und Kugeln.

---

## 1. Fallblatt-Zahlen (Split-Flap)

Vorlage: „Split-Flap Stats“. Bilder: `vorschau/komponenten/fallblatt-*.webp`, `vorlagen-videos/runde-2-split-flap*.webp`.

**Wo:** Kennzahlen auf der Startseite (und die Vorschau in den Einstellungen). An, wenn das Design Violett ist und „Zahlen“ nicht „Schlicht“ steht, oder bei „Zahlen: Fallblatt“ in jedem Design. Technisch: CSS setzt `--fallblatt: an` auf den Container `[data-fallblatt]`, das Skript liest diesen Wert. `data-fallblatt="immer"` schaltet es unabhängig vom Design ein.

**Aufbau einer Ziffer (Kachel):** 1,08 em × 1,5 em, Ecken 7 px, Hintergrund 88 % Fläche + 12 % Textfarbe, obere Hälfte mit leichtem Glanzverlauf, Trennlinie 1 px `rgba(0,0,0,.45)` genau in der Mitte, Schatten `0 2px 0 rgba(0,0,0,.28), 0 6px 14px rgba(0,0,0,.18)`. Schrift: Monospace des Designs, 600, gleich breite Ziffern. Abstand 4 px. Rote/gelbe Kennzahlen färben die Zeichen rot/gelb. Jede Kachel besteht aus vier Hälften: obere und untere feste Hälfte und zwei Klappen.

**Ein Klapp-Schritt (alt → neu, Dauer d):**
1. Obere feste Hälfte zeigt sofort das neue Zeichen, untere noch das alte.
2. Obere Klappe (altes Zeichen) fällt nach unten: `rotateX(0)` → `rotateX(-90deg)`, d/2, `ease-in`, Drehpunkt Unterkante.
3. Untere Klappe (neues Zeichen) kommt hoch: `rotateX(90deg)` → `0`, d/2, `cubic-bezier(.3,1.6,.5,1)` (leichtes Nachfedern), Drehpunkt Oberkante.
4. Untere feste Hälfte zeigt das neue Zeichen.
Perspektive 400 px, Rückseiten unsichtbar.

**Beim Laden:** Alle Kacheln starten leer. Jede Kachel beginnt verzögert (Kennzahlen-Gruppe × 120 ms + Zahl × 140 ms + Kachel × 45 ms), klappert dann durch 3 bis 6 zufällige Zeichen (plus eins je Position, also hintere Stellen länger) aus `A–Z 0–9 % + - . /` mit je 64 ms und landet auf dem Ziel mit 154 ms. Ergebnis: die Tafel „rattert“ von links nach rechts in etwa 1 bis 2 Sekunden auf die echten Werte.

**Später ändern:** `cockpitKomponenten.fallblatt(element, "12.481")` klappt nur die geänderten Stellen, mit 1 bis 3 Zwischenzeichen à 70 ms. Ändert sich die Länge, wird neu aufgebaut.

**Umschalten:** Wird die Option in den Einstellungen geändert, baut die Vorschau sofort auf (oder zurück auf normale Zahlen).

**Barrierefreiheit:** Der echte Wert steht als unsichtbarer Text daneben, die Kacheln sind `aria-hidden`.

---

## 2. Schlüssel und Schloss (Key Cut)

Vorlage: „Key Cut Signup“. Bilder: `vorschau/komponenten/schluessel-*.webp`, `vorschau/seiten/24-konto-erstellen.webp`.

**Wo:** „Konto erstellen“ und „Einstellungen → Passwort ändern“.

**Bild (SVG, viewBox 440 × 190):** links ein Metallschlüssel (Verlauf `#fdfdff → #cfd1d9 → #eceef3 → #8b8e99`): runder Kopf mit Loch, Schulter, Bart mit Rille und Spitze. Rechts ein Vorhängeschloss: Bügel (Metall, 11 px stark, runde Enden), Körper `#76747f → #3b3a45` mit Ecken 12 px und waagerechten Rippen, kleiner Zylinder links am Körper, auf den die Schlüsselspitze zeigt. Weicher Schatten darunter. Der Schlüssel wird rechts vom Schloss abgeschnitten (Clip), damit er „im“ Schloss verschwindet.

**Fünf Regeln = fünf Zähne** (oben in den Bart geschnitten, Tiefe in px: 9, 5, 11, 7, 10):

| Regel | Text | Pflicht |
|---|---|---|
| `laenge` | 12+ Zeichen (Pflicht) | ja, wie auf dem Server |
| `mix` | Groß und klein | nein |
| `zahl` | Eine Zahl | nein |
| `zeichen` | Ein Sonderzeichen | nein |
| `lang` | 16+ Zeichen | nein |

**Beim Tippen:**
- Jede neu erfüllte Regel: ihr Zahn wird eingeschliffen (Tiefe nähert sich pro Bildschirmbild um 16 % dem Ziel an, also etwa 0,3 s) und es sprühen 7 Metallspäne (Kreise 1–2,4 px) nach unten weg (500–900 ms, verblassend), gestaffelt je Regel um 90 ms.
- Nicht mehr erfüllte Regel: der Zahn wächst wieder zu.
- Regel-Liste: Kreis vor jeder Regel; erfüllt = Kreis gefüllt in Akzentfarbe mit Häkchen, Text in voller Farbe.
- Stärke-Zeile: „Stärke: 0 von 5“, sonst „Stärke: schwach/mäßig/gut/stark/sehr stark, N von 5“.

**Schloss öffnen**, sobald 12 Zeichen erreicht sind und die Wiederholung übereinstimmt:
1. Schlüssel gleitet 180 px nach rechts ins Schloss: 0,55 s, `cubic-bezier(.5,0,.2,1)`.
2. Ab 0,5 s dreht er sich: der Kopf wird schmal (`scaleX(.16)`, man sieht ihn von der Kante), 0,55 s.
3. Ab 0,8 s springt der Bügel 14 px hoch: 0,45 s, `cubic-bezier(.3,1.6,.5,1)` (federt).
4. Status unter dem Knopf (Monospace, Großbuchstaben, Akzentfarbe): „ENTSPERRT“.
Wird das Passwort danach wieder ungültig, läuft alles gleichzeitig zurück.

**Status-Texte:** „Mindestens 12 Zeichen öffnen das Schloss.“ → „Jetzt wiederholen.“ → „Die Wiederholung stimmt noch nicht.“ → „Entsperrt“.

**Wichtig:** Der Absende-Knopf bleibt immer aktiv; geprüft wird auf dem Server (mindestens 12 Zeichen, Wiederholung gleich). Die übrigen vier Regeln sind Empfehlungen.

**Layout:** Konto erstellen = breite V7-Karte (max. 900 px) mit zwei Spalten ab 820 px (Bild links, Formular rechts 380 px), darunter Bild oben. Passwort ändern = Bild links (260–360 px), Formular rechts; ist zu wenig Platz, steht das Bild darüber (Flex-Umbruch).

---

## 3. Kassenbon (Receipt)

Vorlage: „Receipt Pricing“. Bilder: `vorschau/komponenten/kassenbon-*.webp`, `vorschau/seiten/20-bestellung.webp`.

**Wo:** jede Bestellung (Ansicht „Übersicht“ oder „Nachweise“). Im Design-Paket zusätzlich als Preistabelle für Webseiten (Pakete Starter/Pro/Team, Monatlich/Jährlich mit Rabatt).

**Aufbau:**
- Drucker: dunkles Gerät (Verlauf `#3a3843 → #1c1b23`, Ecken 14/10 px, Schatten), links eine LED mit Status „BEREIT“ / „DRUCKT …“ (Monospace 0,6 rem, Sperrung .16 em), rechts ein kleiner Knopf, unten ein schwarzer Schlitz.
- Papier: kommt unter dem Gerät heraus (12 px darunter versteckt, 20 px schmaler), Farbe `#fbfaf6`, Tinte `#23222a`, Schatten. Untere Kante gezackt (Maske, Zähne 10 px breit, 7 px hoch).
- Inhalt: Monospace 0,68 rem, Großbuchstaben, Sperrung .05 em. Kopf mit Logo-Kachel und Name (gesperrt), Meta-Zeile grau (Belegart und Datum). Zeilen „Bezeichnung ……… Wert“ mit dünner Führungslinie zwischen Text und Wert. Trennlinien gestrichelt, vor der Summe doppelt. Summe fett mit großem Betrag (1,35 rem). Strichcode (aus dem Text berechnet, immer gleich für dieselbe Bestellnummer). „VIELEN DANK“ bzw. „STAND 01.10.2026“ gesperrt.

**Inhalt im Cockpit:**
- Übersicht: Firma, Bestellung, Projekt, Gültig von–bis; Bestellt; Abgerechnet (−); Eingereicht, ungeprüft (grau); Summe „Frei“; „N % verbraucht“; Warnungen fett; Strichcode; Stand.
- Nachweise: je Leistungsnachweis Datum mit ✓ geprüft / … offen / ✕ abgelehnt und Menge; Summe „Geprüft“; Legende.
- Preistabelle (Design-Paket): Paket, Leistungen „inkl.“, Zwischensumme, bei jährlich „12 × Preis“ und „Jährlich −20 %“, bei monatlich „Jährlich gespart wären …“ grau, Gesamt pro Monat, „jährlich abgerechnet: …“. Die Preise in der Paketliste und der Knopf („Pro wählen →“) ändern sich mit.

**Drucken:**
1. Start, sobald der Beleg zu 30 % sichtbar ist (einmal).
2. LED blinkt (0,7 s, zwei Stufen), Status „DRUCKT …“.
3. Für jede Zeile: Pause 40–160 ms (zufällig, wirkt mechanisch), dann wächst das Papier bis unter diese Zeile in 80 ms + 2,4 ms je Pixel, Kurve `cubic-bezier(.3,.7,.4,1)`. Die Zacken-Kante wandert mit.
4. Am Ende Status „BEREIT“, LED aus.

**Wechsel** (Ansicht, Paket, Monatlich/Jährlich), auch mitten im Druck: Der bisherige Beleg wird abgerissen: eine Kopie fällt nach unten weg (`translate(-14px, 240px) rotate(-9deg)`, ausblenden, 700 ms, `cubic-bezier(.5,0,.8,.5)`), gleichzeitig druckt der neue von vorn. Ein laufender Druck wird abgebrochen.

**Ohne JavaScript:** der Beleg „Übersicht“ steht fertig da.

---

## 4. Karteikasten (Strg+K / ⌘K)

Vorlage: „Card File Palette“. Bilder: `vorschau/komponenten/karteikasten-*.webp`.

**Öffnen:** Strg+K (Mac ⌘K) auf jeder Seite, oder Klick auf den Knopf „Strg K“ / „⌘K“ in der Suche der Seitenleiste. Nochmal Strg+K schließt.

**Fenster:** dunkler Schleier über der Seite (`rgba(8,7,12,.55)` + Unschärfe 6 px), blendet in 0,2 s ein. Fenster 620 px breit, Ecken 18 px, 9 % vom oberen Rand; erscheint mit `translateY(10px) scale(.98)` → normal in 0,28 s, `cubic-bezier(.3,1.3,.5,1)`. Oben Suchfeld mit Lupe, Platzhalter „Suchen oder springen …“, Knopf „Esc“; beim Tippen eine Akzentlinie unter dem Feld. Mitte die Bühne (300 px hoch, auf dem Handy 250 px) mit Karten auf einer Schiene. Unten die Fußzeile „↑ ↓ Blättern · ↵ Öffnen · Esc Schließen · 23 Treffer“.

**Karten:** Karteikarten 400 × 150 px (max. 84 % Breite), oben 10 px, unten 4 px abgerundet, heller Verlauf `#fbfbfd → #e9e8ef`, liniert (alle 24 px), Titel fett mit Linie darunter, rechts oben ein Reiter mit der Gruppe in Großbuchstaben (SEITEN, AKTIONEN, ANSICHTEN, AUFGABE, PROJEKT, MEETING, PERSON, FIRMA, BESTELLUNG), darunter der Hinweis in Monospace, auf der vordersten Karte unten rechts die Tasten (z. B. `G` `A`). Unter den Karten eine dunkle Schiene mit gerillten Stangen links und rechts.

**Räumliche Anordnung** (Perspektive 1000 px, von oben betrachtet, Drehpunkt jeder Karte an der Unterkante). Für eine Karte mit Abstand o zur aktuellen:
- vorne (o = 0): aufrecht, voll hell.
- dahinter (o > 0): `translate3d(0, −27·o px, −36·o px) rotateX(min(o,3) · 6deg)`, dunkler um 11 % je Stufe (höchstens 55 %), ab o > 5 unsichtbar. So schauen die Titel der hinteren Karten oben heraus.
- schon durchgeblätterte (o < 0): nach vorn umgeklappt, `translate3d(0, 12px, 40px) rotateX(−(82 + 3·(|o|−1))deg)`, Deckkraft 0,8 + 0,25·o, ab o < −2 unsichtbar.
- Jede Änderung gleitet mit 0,5 s `cubic-bezier(.3,1.3,.5,1)` (federt leicht), Deckkraft 0,35 s.
- Neue Treffer starten 30 px höher und unsichtbar und setzen sich dann an ihren Platz.
- Enter: die vordere Karte wird nach oben-vorn gezogen (`translate3d(0,-60px,80px)`, ausblenden), dann öffnet die Seite.

**Bedienung:** Tippen filtert sofort (ohne Akzente/Groß-Klein, alle Wörter müssen vorkommen, Treffer mit passendem Anfang zuerst). ↓/Tab blättert weiter, ↑/Shift+Tab zurück, Mausrad blättert (höchstens alle 110 ms), Klick auf eine hintere Karte holt sie nach vorn, Klick auf die vordere öffnet sie, Esc oder Klick auf den Schleier schließt. Danach bekommt das vorher fokussierte Element den Fokus zurück. Während der Kasten offen ist, scrollt die Seite nicht.

**Inhalt:**
- feste Einträge: zehn Seiten mit Tasten (g s Start, g a Aufgaben, g m Meetings, g p Projekte, g z Zeitplan, g h Zeiten, g l Auslastung, g b Berichte, g t Team & Firmen, g e Einstellungen), Aktionen (Neue Aufgabe, Neues Meeting, Neues Projekt, Neuer Meilenstein, Stunden erfassen, Person anlegen, Firma anlegen, Startseite anpassen, Darstellung ändern), Ansichten (Überfällige Aufgaben, Heute fällig, Diese Woche, Statusbericht).
- Suche auf dem Server ab 2 Zeichen, 160 ms nach dem letzten Tastendruck: `GET /suche.json?q=…` → bis 12 Treffer aus Projekten, Aufgaben, Meetings, Personen, Firmen, Bestellungen (siehe `04`). Treffer werden hinten angehängt; veraltete Antworten werden verworfen.
- „g“ und dann ein Buchstabe (innerhalb 1 s, nicht in Eingabefeldern) springt ohne Kasten direkt.
- Aktions-Links zeigen auf Anker (`/meetings#neu`); die Zielseite öffnet das zugeklappte Formular und setzt den Cursor ins erste Feld.

**Barrierefreiheit:** Dialog mit `aria-modal`, Suchfeld als `combobox` mit `aria-activedescendant` auf die vordere Karte, Karten als `option` in einer `listbox`, Trefferzahl als Live-Region.

---

## 5. Papierflieger (Paper Plane)

Vorlage: „Paper Plane“. Bilder: `vorschau/komponenten/papierflieger-*.webp`.

**Wo:** Berichte → Projektstatus → „Per E-Mail senden“. Im Design-Paket als Newsletter-Karte (weißes Papier).

**Ablauf beim Absenden:**
1. Browser-Prüfung der Felder; bei Fehler normale Hinweise, nichts faltet sich.
2. Die Anfrage geht sofort los (im Cockpit `fetch` mit Kopfzeile `X-Cockpit-Ajax: 1`, Antwort JSON `{ok, nachricht}`). Gleichzeitig wird die Karte unsichtbar und an ihrer Stelle liegt ein Blatt Papier gleicher Größe (immer hell `#f2f1f6`, auch in dunklen Designs).
3. Falten in vier Bildern, jeder Übergang 320 ms mit `ease-in-out` (kubisch), dazwischen 70 ms Pause:
   - Rechteck,
   - rechte Ecken nach innen gefaltet: Spitze rechts, die gefaltete untere Klappe als graues Dreieck (`#8f8d99`),
   - lange Spitze: Länge L = min(Breite, 2,6 × Höhe), mittig, Faltlinien von der Schulter (28 %) zur Mitte (55 %),
   - Seitenansicht des Fliegers: schmaler Rumpf, Flügel als graues Dreieck.
   Breite Karten falten sich also zu einem Flieger mit normalen Proportionen.
4. Warten auf die Antwort.
5. **Erfolg:** Der Flieger fliegt los (1 250 ms, `cubic-bezier(.5,0,.6,1)`): erst kurz zurück und klein (bei 28 %: 6 % nach links, 5 % nach unten, 3° gedreht, 42 % Größe), dann schräg nach rechts oben aus dem Bild (75 % Breite nach rechts, 135 % Höhe nach oben, −22°, 16 % Größe, ausblenden). Dahinter eine gestrichelte Flugspur (5/7 px), die ein- und ausblendet (1,3 s). Danach erscheint die Erfolgsansicht: Flieger-Symbol, „Unterwegs.“ (im Design-Paket „Du bist dabei.“), die Meldung des Servers („Statusbericht an 2 Empfänger versendet.“), die Adressen als Pille, Knopf „An weitere Empfänger senden“ (stellt das leere Formular wieder her).
6. **Fehler:** Der Flieger faltet sich rückwärts wieder zum Blatt (je 260 ms), die Karte erscheint wieder, darunter in Rot der Grund vom Server, der Cursor steht im Feld.

Ohne JavaScript: normales Formular mit Weiterleitung und Meldung. Im Design-Paket mit `action="https://…"`: nach dem Flug wird ganz normal an diese Adresse abgeschickt; ohne `action` ist es eine Vorschau.

---

## 6. Orb: „Frag das Cockpit“

Vorlage: „Orb Pack“. Bilder: `vorschau/komponenten/orb-*.webp`, `vorschau/handy/frag-das-cockpit.webp`.

**Wo:** Baustein auf der Startseite (breit, an zweiter Stelle).

**Aufbau im Ruhezustand:** oben eine waagerecht scrollbare Reihe mit zwölf Kugel-Stilen (je 68 px breit: kleine Vorschau 28 px, Name; gewählter Stil mit Rahmen und Fläche). Darunter die große Kugel (132 px, Canvas), „Wie kann ich helfen?“, vier Vorschlags-Chips („Fasse meine Woche zusammen“, „Was ist überfällig?“, „Wie stehen die Kontingente?“, „Gibt es Konflikte im Zeitplan?“), ein Eingabefeld in Pillenform („Frag etwas, z. B. „Wer ist überbucht?““) mit rundem Senden-Knopf (Pfeil nach oben, Akzentfarbe), darunter „Enter zum Senden · ohne KI, direkt aus deinen Daten“.

**Gespräch:** Nach der ersten Frage schrumpft die Kugel auf 58 px (0,4 s), daneben „Cockpit · Bereit/Denkt nach …/Antwortet …“, Überschrift und Chips verschwinden. Die Frage steht rechts als Sprechblase, die Antwort links als Absätze, darunter Links (Text plus graue Zusatzinfo, z. B. „24.09.2026 · Firma Alpha“). Der Verlauf scrollt in sich (max. 320 px) und läuft beim Schreiben mit. „Neu beginnen“ leert ihn.

**Zustände der Kugel:**

| Zustand | Auslöser | Bewegung |
|---|---|---|
| ruhig | Standard | Grundtempo, Pegel 0 |
| tippt | jeder Tastendruck | Pegel +0,3 (fällt pro Bild auf 90 % zurück) |
| denkt | Frage abgeschickt, mindestens 650 ms | Tempo × 2,4, Pegel pulsiert 0,55 ± 0,25 |
| spricht | Antwort kommt | Tempo × 1,6, jedes Wort erscheint nach 24–62 ms und gibt der Kugel einen Schub (Pegel 0,45–0,8) |

Der Pegel wird weich nachgeführt (15 % pro Bild). Während der Antwort wird der Knopf zum Stopp-Quadrat; Klick oder Esc zeigt den Rest sofort. Die Kugel läuft nur, wenn sie sichtbar ist und der Tab aktiv ist.

**Die zwölf Kugeln** (Canvas 2D, Größe S, Radius etwa 0,38 S, jede reagiert auf den Pegel):

| Stil | Aussehen |
|---|---|
| Glas | dunkle Glaskugel, vier halbtransparente blau-violette Bänder kreisen, Glanzlicht oben links, heller Rand |
| Plasma | dunkle Kugel mit Blitzen vom Kern zum Rand (5 bis 12 je nach Pegel, alle 70 ms neu, bläulich leuchtend), heller Kern |
| Chrom | Metallkugel mit gespiegeltem Horizont (Streifen hell–dunkel–hell), der Horizont wogt mit dem Pegel |
| Schwarm | 180 Punkte auf einer Kugeloberfläche (Fibonacci-Verteilung), drehen sich, hintere kleiner und blasser, zittern mit dem Pegel |
| Hologramm | grünes Drahtgitter (Breiten- und Längenkreise), Längenkreise drehen sich, leuchtend, eine Abtastlinie läuft von oben nach unten |
| Stimme | leuchtend orange Kugel, atmet; bei Pegel > 0,35 laufen Ringe nach außen |
| Aurora | dunkle Kugel mit vier wandernden Farbwolken (grün, violett, blau, pink), Glanz |
| Lava | orange Blase mit weich wabernder Form (überlagerte Sinuswellen), Glühen |
| Dither | Kugel aus Punkten im Bayer-Raster (26 × 26), Licht wandert um die Kugel |
| Blase | Seifenblase: durchsichtig, schillernder Rand (Farbkreis dreht sich), wabert mit dem Pegel, zwei Glanzpunkte |
| Schwarzes Loch | schwarze Scheibe mit hellem Photonenring, gekippte Akkretionsscheibe in Gold und Orange (hinterer Teil hinter, vorderer vor dem Loch), Lichtbogen darüber, Streifen laufen um |
| Kristall | sechseckiger Doppelkegel aus violetten Facetten, dreht sich, Facetten nach Licht schattiert |

Der gewählte Stil wird im Browser gespeichert (`localStorage` „cockpit-orb“), Standard Plasma.

**Antworten:** keine KI. Der Server erkennt Themen an Stichwörtern und antwortet aus der Datenbank; alles andere wird gesucht (Regeln in `04`). Die Antwort wird immer als Text eingefügt, nie als HTML.

---

## 7. Login V7

Vorlage: „Login form V7“. Bilder: `vorschau/seiten/23-anmelden-*.webp`.

- Karte: max. 440 px breit, Fläche 74 % deckend mit Unschärfe 22 px, Rahmen, Schatten `0 30px 60px rgba(0,0,0,.3)`, zwei gegenüberliegende Ecken abgeschrägt (26 px, `clip-path`) mit je einer schrägen Akzentlinie (2 px).
- **Öffnen:** Zuerst nur eine kleine Logo-Kachel (68 × 68 px, ebenfalls mit abgeschrägten Ecken) in der Mitte. Nach 0,45 s klappt die Karte daraus auf (`clip-path` von der Kachel zur vollen Form, 1 s, `cubic-bezier(.7,0,.2,1)`). Ab 1,15 s blendet das Logo aus (0,35 s), ab 1,1 s blendet der Inhalt ein und rutscht 6 px nach oben (0,45 s).
- Überschrift „Willkommen *zurück*“ (zweites Wort in Akzentfarbe), Felder 46 px hoch mit Symbol links und Auge rechts (Passwort anzeigen/verbergen, `aria-pressed`), großer Knopf mit Pfeil.
- Bei „Bewegung reduzieren“ steht die Karte sofort da.

## 8. Seitenleiste ein- und ausklappen

Klick auf den Pfeil: `data-nav` wechselt zwischen `voll` und `mini`; Breite und Beschriftungen wechseln, der Pfeil dreht sich in 0,3 s um 180°. Zustand im Cookie `pc_nav`, `aria-expanded` am Knopf.

## 9. Startseite anpassen (Ziehen)

Bausteine sind ziehbar (`draggable`); der gezogene wird auf 30 % Deckkraft gesetzt (`.dragging`), eine Linie vor oder hinter dem Ziel zeigt die Einfügestelle (bei breiten Bausteinen oben/unten, sonst links/rechts). Loslassen ordnet um; gespeichert wird mit „Fertig“. Häkchen „anzeigen“ und „breit“ wirken sofort.

## 10. Kleinere Übergänge

- Kennzahl-Kacheln: Rahmen in Akzentfarbe beim Überfahren, in Glas und Hell heben sie sich zusätzlich um 2 px an.
- Knöpfe, Links, Chips: Farbwechsel beim Überfahren; sichtbarer Fokus-Rahmen 2 px in Akzentfarbe mit 2 px Abstand.
- Protokoll-Notizen: Status „Ungespeicherte Änderungen“ → „Gespeichert um 10:42“, bei Fehler rot „Nicht gespeichert: …“; gespeichert wird 1,5 s nach dem letzten Tippen und vor jedem Absenden.
- Stundenzettel: Summen ändern sich beim Tippen.
- Sammelbearbeitung: nur das Feld der gewählten Aktion ist sichtbar.
- Zeitplan-Formular: zeigt je nach Art (Vorgang/Meilenstein) die passenden Felder.
