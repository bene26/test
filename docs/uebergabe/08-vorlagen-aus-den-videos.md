# 8. Vorlagen: Design-Vorschläge und Videos

Das Aussehen ist in drei Runden entstanden. Bilder aus den Videos liegen in `vorlagen-videos/` (je Video ein Bogen mit Einzelbildern und eine Detailansicht). Die Original-Videos (Instagram-Reels) hat der Auftraggeber; sie sind nicht im Paket.

## Runde 0: vier Design-Vorschläge

Auf einer Design-Fläche (https://claude.ai/artifact/4JcN2wV6RcbBLFQYkmRBpn, privat) entstanden vier Vorschläge für die Startseite. Alle vier wurden übernommen und sind in den Einstellungen wählbar; das ursprüngliche ruhige Design blieb als fünftes erhalten:

| Vorschlag | Design im Cockpit |
|---|---|
| 1 · Violett: Lila, Zahlen wie auf einer Abfahrtstafel, Seitenleiste | Violett |
| 2 · Glas und Orange: schwebende Glas-Seitenleiste, orange Akzente | Glas und Orange (Standard) |
| 3 · Bronze: abgeschrägte Ecken, bronzener Lichtbogen, Menü oben | Bronze |
| 4 · Hell: mattes Glas auf Pastell, schmale Symbolleiste | Hell |
| bisheriges Design | Schlicht |

## Runde 1: vier Videos (Darstellung, Navigation, Login, Seitenleiste)

| Video | Was es zeigt | Was übernommen wurde | Bewusst anders |
|---|---|---|---|
| 1 · App-Einstellungen (`runde-1-video-1-*`) | Handy-App: Profil, Einstellungen, Seite „Appearance“ mit hell/dunkel, Themenfarben als Farbkreise, Textgröße, UI-Stil, Vorschau; außerdem Sprache, Benachrichtigungen, Datenschutz | Einstellungen → Darstellung: hell/dunkel je Design, sieben Akzentfarben als Farbkreise, drei Schriftgrößen, Ecken (als „UI-Stil“), Zahlen, Menü-Stil; Vorschau, die sofort auf die ganze Seite wirkt; Leiste „Änderungen · Verwerfen · Übernehmen“ | Sprache und Benachrichtigungs-Seiten nicht übernommen (Oberfläche nur Deutsch; Benachrichtigungen sind die „Erinnerungen“ in den Einstellungen) |
| 2 · „10 Next-Gen Mobile Navigation Designs“ (`runde-1-video-2-*`) | zehn Bottom-Navigationen: Liquid Floating Bar, Magnetic Dock, Glass Capsule Dock, Segmented Dynamic Bar, Orbit Navigation, Wave Indicator, Cyber Neon Dock, Morphing Blob, Layered Cards, Minimal Luxury | alle zehn als Menü-Stile: für den aktuellen Punkt in Seitenleiste, Leiste oben und im Handy-Dock | im Desktop als Seitenleiste statt Leiste unten; Farben folgen dem Akzent |
| 3 · „Login form V7“ (`runde-1-video-3-*`) | dunkle Glaskarte mit abgeschrägten Ecken auf goldenem Lichtbogen, gelber Knopf, „Welcome Back“ / „Create Account“, Google- und Apple-Knöpfe, Karte klappt aus einem Logo auf | Anmelden und Konto erstellen als V7-Karte mit Aufklapp-Animation, Symbolen in den Feldern, Passwort-Auge; mit Bronze und Akzent Gelb fast wie im Video | keine Google-/Apple-Anmeldung (ein eigenes Konto, keine fremden Dienste) |
| 4 · „SideBar UI“ (`runde-1-video-4-*`) | dunkle Seitenleiste mit rotem Akzent: Profil, Suche, Abschnitte, rote Zähler, einklappbar | Seitenleiste mit Profil, Suche, drei Abschnitten, roten Zählern, Einklappen zur Symbolleiste, Handy-Dock | Akzent folgt der gewählten Farbe; Zähler bleiben rot |

## Runde 2: sechs Komponenten-Videos

Alle sechs sind „React Component“-Demos (dunkel, mit Code-Ausschnitten). Umgesetzt ohne React, als reines JavaScript (`komponenten.js`), und an Stellen im Cockpit eingebaut, wo sie eine echte Aufgabe haben.

| Video | Was es zeigt | Im Cockpit | Bewusst anders |
|---|---|---|---|
| **Orb Pack** (`runde-2-orb-pack*`) | KI-Eingabebox „How can I help?“ mit zwölf wählbaren Kugeln (Glass, Plasma, Chrome, Swarm, Hologram, Voice, Aurora, Lava, Dither, Bubble, Black hole, Crystal); Vorschlags-Chips; Kugel reagiert auf Tippen, Nachdenken und jedes Wort; Antwort Wort für Wort; „Esc to stop“ | Baustein „Frag das Cockpit“ auf der Startseite mit denselben zwölf Kugeln (deutsche Namen) und Zuständen | keine KI: feste Regeln über die eigenen Daten, sonst Suche; Chips mit Cockpit-Fragen |
| **Split-Flap Stats** (`runde-2-split-flap*`) | Kennzahlen „on a departure board“: Kacheln klappern durch Zufallszeichen auf die Werte, danach zählen sie live hoch | Kennzahlen der Startseite, Option „Zahlen“ für jedes Design | klappern beim Öffnen; Live-Hochzählen nur über die Funktion `fallblatt()` |
| **Receipt Pricing** (`runde-2-receipt-pricing*`) | Preistabelle (Monthly/Yearly „Save 20 %“, Starter/Pro/Team) mit Belegdrucker; der Beleg druckt Zeile für Zeile, beim Wechsel wird der halbe Beleg abgerissen und neu gedruckt; Barcode, „Thank you“ | Beleg zu jeder Bestellung (Übersicht oder Leistungsnachweise); die Preistabelle steckt im Design-Paket für Webseiten (€, „Vielen Dank“) | Inhalte auf Deutsch, Beträge aus der Bestellung |
| **Key Cut Signup** (`runde-2-key-cut-signup*`) | Registrierung, bei der jede Passwort-Regel einen Zahn in den Schlüssel schneidet (mit Spänen); bei genug Regeln fährt der Schlüssel ins Schloss, dreht sich, der Bügel springt auf, „Unlocked“, „Account created“ | Konto erstellen und Passwort ändern | Regeln: 12+ Zeichen (Pflicht), Groß und klein, Zahl, Sonderzeichen, 16+ Zeichen. Das Schloss öffnet bei 12 Zeichen und gleicher Wiederholung (wie die Server-Regel); im Video „4 von 5 Regeln“. Der Knopf ist nie gesperrt |
| **Card File Palette** (`runde-2-card-file-palette*`) | ⌘K-Befehlspalette als Karteikasten: Karten stehen hintereinander, kippen beim Blättern nach vorn, Enter zieht die Karte; Reiter „PAGES“/„ACTIONS“, Tastenkürzel „G D“; Werte LEAN 6°, DEPTH 36 px, RISE 27 px, FALL 82° | Strg+K / ⌘K auf jeder Seite: Seiten, Aktionen, Ansichten und Server-Suche; „g“ + Buchstabe | gleiche Geometrie; Inhalte aus dem Cockpit |
| **Paper Plane** (`runde-2-paper-plane*`) | Newsletter-Karte „Get the weekly digest“, die sich beim Abonnieren zum Papierflieger faltet und mit gestrichelter Spur davonfliegt; Fehler bei ungültiger Adresse; „You're in. Check your inbox.“, „Send another“ | „Statusbericht per E-Mail senden“; im Design-Paket als Newsletter-Karte | faltet, während die Anfrage läuft; bei Fehler faltet es sich zurück und zeigt den Grund vom Server |

## Was in keinem Video vorkam, aber dazugehört

Seitenleisten-Zähler mit echten Daten, „g“-Tastenkürzel, Anker-Sprung mit Fokus ins Formular, „Bewegung reduzieren“, Funktionieren ohne JavaScript, strenge Content-Security-Policy und Kontrastprüfung aller Farbkombinationen.
