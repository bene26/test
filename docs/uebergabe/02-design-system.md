# 2. Design-System

Bilder: `vorschau/designs/` (Startseite in allen Designs), `vorschau/navigation/` (Seitenleiste, Menü-Stile, Darstellungs-Einstellungen).

## Grundprinzip

Das ganze Aussehen hängt an wenigen Attributen am `<html>`-Element. Jedes Design setzt denselben Satz CSS-Variablen (Tokens); alle Bausteine benutzen nur diese Variablen. Deshalb lässt sich jedes Design mit jeder Option kombinieren, und ein Element mit eigenem `data-theme` zeigt sein eigenes Design (so funktionieren die Mini-Vorschauen in den Einstellungen).

| Attribut | Werte | Bedeutung |
|---|---|---|
| `data-theme` | `violett`, `glas` (Standard), `bronze`, `hell`, `schlicht` | das Design |
| `data-mode` | leer, `hell`, `dunkel` | Variante; leer = wie im Design |
| `data-tone` | `hell`, `dunkel` | errechnet: tatsächliche Helligkeit (Modus oder Standard des Designs); steuert die Akzentfarben. Schlicht ohne Modus folgt dem Gerät |
| `data-accent` | leer, `violett`, `blau`, `pink`, `gruen`, `orange`, `gelb`, `rot` | Akzentfarbe |
| `data-size` | `klein` (93,75 %), leer, `gross` (112,5 %) | Schriftgröße über `html { font-size }` |
| `data-shape` | leer, `rund`, `weich`, `kantig` | Ecken; Bronze bleibt immer abgeschrägt |
| `data-menu` | leer oder einer der zehn Menü-Stile | Stil des aktuellen Menüpunkts |
| `data-digits` | leer, `fallblatt`, `schlicht` | Kennzahlen als Fallblatt-Tafel; leer = nur bei Violett |
| `data-nav` | `voll`, `mini` | Seitenleiste offen oder Symbolleiste; nur bei Violett, Glas, Hell |

Gespeichert wird je Konto (Datenbank: `users.theme` und `users.appearance` als JSON). Zusätzlich setzt der Server zwei Cookies (`pc_theme`, `pc_look` im Format `modus.akzent.schrift.ecken.menue.zahlen`, `-` für leer), damit die Anmeldeseite vor dem Login schon richtig aussieht. Ob die Seitenleiste eingeklappt ist, merkt sich der Browser im Cookie `pc_nav`. Alle Werte werden gegen eine feste Liste geprüft; unbekannte Werte fallen auf „wie im Design“ zurück.

Die vollständige Liste steht in `referenz-code/projekt-cockpit/cockpit/themes.py`, alle Tokens in `cockpit/static/app.css` ab „Design tokens“.

## Die fünf Designs

| | Violett | Glas und Orange | Bronze | Hell | Schlicht |
|---|---|---|---|---|---|
| Grundton | dunkel | dunkel | dunkel | hell | folgt dem Gerät |
| Hintergrund `--bg` | `#0e0b16` + violette Lichtflecken oben links und rechts | `#0a0a0c` + grauer Lichtbogen unten | `#060606` + bronzener Lichtbogen unten | `#eef0f3` + Pastellflecken (Pfirsich, Flieder) | `#f5f6f8` / dunkel `#12161c` |
| Fläche `--surface` | `#17131f` deckend | `rgba(24,24,28,.62)` + Unschärfe 24 px | `rgba(24,19,14,.62)` + Unschärfe 20 px | `rgba(255,255,255,.62)` + Unschärfe 26 px | `#ffffff` |
| Text / gedämpft | `#f4f2f8` / `#a7a1b8` | `#f5f5f7` / `#a1a1aa` | `#f3ede4` / `#a39b90` | `#15151a` / `#5e5e68` | `#1b2330` / `#5c6674` |
| Akzent | `#8b7cff` (Links `#b9afff`) | `#ff6a1f` (Links `#ff9a62`) | `#d99a4e` (Links `#f2c287`) | `#ff6a1f` (Links `#b4380b`) | `#2456c9` |
| Schrift | Geist, Überschriften Sora | Plus Jakarta Sans 800 | Manrope, Überschriften Saira Condensed in Großbuchstaben | Plus Jakarta Sans 800 | Systemschrift |
| Zahlenschrift | Geist Mono | JetBrains Mono | Geist Mono | JetBrains Mono | System-Monospace |
| Ecken `--radius` / Knöpfe | 18 px / Pille | 24 px / Pille | 0, abgeschrägte Ecken (`clip-path`) | 24 px / Pille | 8 px / 6 px |
| Navigation | Seitenleiste | schwebende Glas-Seitenleiste | Leiste oben, Unterstrich am aktuellen Punkt | schmale Symbolleiste (eingeklappt) | Leiste oben |
| Besonderheiten | Kennzahlen als Fallblatt-Tafel, Hauptknöpfe als weiße Pillen (ohne gewählten Akzent) | Kacheln heben sich beim Überfahren leicht an | Paneele mit abgeschrägten Ecken und bronzener Eckenlinie, Knöpfe abgeschrägt (Fokus-Rahmen innen, weil `clip-path` Umrisse abschneidet) | mattes Glas auf Pastell, weiße Kacheln mit farbiger Oberkante bei Warnungen | ruhig, das ursprüngliche Design |

Paare für hell/dunkel: „Glas“ im Modus hell sieht aus wie „Hell“, „Hell“ im Modus dunkel wie „Glas“. Violett und Bronze haben eigene helle Varianten (Grund `#f5f3fb` mit violettem Schimmer bzw. `#f6f0e7` warmes Elfenbein mit Bronzebogen). Schlicht hat beide Varianten und folgt ohne Modus dem Gerät.

Weitere Tokens je Design: `--surface-2` (zweite Fläche, Eingaben), `--border`, `--card-border`, `--input-border`, `--accent-hover`, `--accent-contrast` (Text auf Akzent), `--danger`/`--ok`/`--warn` mit `-bg`, Auslastungsstufen `--lvl-frei|ok|voll|ueber` mit `-bg`, Kennzahlen `--stat-*`, Navigation `--nav-*`, `--radius-sm`, `--radius-btn`, `--shadow`, `--panel-filter`, `--display-weight`, `--display-case`, `--display-tracking`, `--backdrop`.

Schriften liegen als WOFF2 im Projekt (`cockpit/static/fonts`, SIL Open Font License). Es wird nichts von Google Fonts oder anderen Servern geladen.

## Akzentfarben

Auf dunklem Grund helle Füllung und helle Linkfarbe, auf hellem Grund kräftigere Füllung und dunkle Linkfarbe. Alle Paare sind auf WCAG AA (4,5 : 1 für Text) geprüft.

| Akzent | dunkel: Füllung / Text auf Füllung / Link | hell: Füllung / Text auf Füllung / Link |
|---|---|---|
| Violett | `#8b7cff` / `#0e0b16` / `#b9afff` | `#6d5df5` / `#fff` / `#5443d6` |
| Blau | `#4c8dff` / `#050e1f` / `#8db8ff` | `#2563eb` / `#fff` / `#1d4ed8` |
| Pink | `#f0569d` / `#1f0512` / `#ff9cc8` | `#db2777` / `#fff` / `#be185d` |
| Grün | `#2fbf71` / `#03170b` / `#7ee2ae` | `#15803d` / `#fff` / `#15803d` |
| Orange | `#ff6a1f` / `#1a0a02` / `#ff9a62` | `#ff6a1f` / `#1a0a02` / `#b4380b` |
| Gelb | `#ffd21f` / `#1a1400` / `#ffe166` | `#facc15` / `#1a1400` / `#854d0e` |
| Rot | `#f0443a` / `#1f0403` / `#ff8f87` | `#dc2626` / `#fff` / `#b91c1c` |

`--info-bg` und die Hintergrundfarbe des aktiven Menüpunkts werden mit `color-mix()` aus dem Akzent gemischt (11 % Akzent auf Fläche).

## Ecken

| Wert | Karten | klein | Knöpfe |
|---|---|---|---|
| rund | 26 px | 16 px | Pille |
| weich | 16 px | 10 px | 12 px |
| kantig | 4 px | 3 px | 4 px |

## Seitenleiste und Navigation

Vorlage: Video „SideBar UI“ (siehe `08`). Bilder: `vorschau/navigation/`.

- **Voll** (264 px, Violett und Glas): Logo + Name und Pfeil-Knopf oben, Profil-Kachel (Avatar mit Kürzel, Name, „Projektleitung“), Suchfeld mit Knopf „Strg K“, Abschnitts-Überschriften in Großbuchstaben („MENÜ“, „PLANUNG“, „ALLGEMEIN“), Einträge mit Linien-Symbol (24-px-Raster, `currentColor`), Beschriftung und rotem Zähler (`#d92d20`, weiße Zahl, für Screenreader „: 5 überfällig“), Abmelden unten.
- **Mini** (84 px, Standard bei Hell): nur Symbole, Zähler als Punkt am Symbol, Beschriftung als Tooltip (`title`). Der Pfeil dreht sich um 180°. Umschalten ist sofort sichtbar und wird im Cookie `pc_nav` gespeichert (1 Jahr, `SameSite=Lax`), damit der Server die Seite gleich richtig ausliefert.
- **Leiste oben** (Bronze, Schlicht): Logo, Menü als Textzeile, kompakte Suche (bei 901–1500 px ausgeblendet), Avatar, Abmelden als Symbol.
- **Handy (≤ 900 px):** schmale Kopfleiste; das Menü wird zum festen Dock am unteren Rand (`position: fixed`, deckender Hintergrund aus 90 % Fläche, kein `backdrop-filter`, damit `fixed` funktioniert), waagerecht scrollbar, im gewählten Menü-Stil.

### Die zehn Menü-Stile (`data-menu`)

Vorlage: „10 Next-Gen Mobile Navigation Designs“ (siehe `08`). Sie betreffen den aktuellen Menüpunkt (`aria-current="page"`) in Seitenleiste, Leiste oben und Handy-Dock. In den Einstellungen zeigt jede Auswahl-Kachel ein Mini-Menü mit vier Einträgen.

| Wert | Name | Aussehen und Bewegung |
|---|---|---|
| `fluessig` | Liquid | Pille in Akzentfarbe, die beim Laden „flüssig“ aufspringt (0,7 s, leichtes Überschwingen `cubic-bezier(.3,1.5,.5,1)`) |
| `magnet` | Magnet-Dock | Einträge wachsen unter der Maus (Nachbarn etwas mit), der aktuelle steht als Kachel hervor |
| `kapsel` | Glas-Kapsel | das Menü sitzt in einer Glas-Kapsel, der aktuelle Eintrag ist ein runder Knopf in Akzentfarbe |
| `segment` | Segmente | eine Schiene, der aktuelle Eintrag ist das hervorgehobene Segment |
| `orbit` | Orbit | eine Umlaufbahn mit Punkt kreist um das Symbol (7 s je Runde, linear, endlos) |
| `welle` | Welle | eine laufende Welle unter dem Eintrag (1,2 s, linear, endlos) |
| `neon` | Neon | dunkle Leiste, der aktuelle Eintrag leuchtet in Akzentfarbe (Leuchtschatten) |
| `blob` | Blob | weicher Farbklecks, der langsam seine Form ändert (5 s, hin und zurück) |
| `karten` | Karten | der aktuelle Eintrag liegt wie eine Karte auf einem kleinen Stapel |
| `luxus` | Minimal Luxus | ruhig: nur ein warmes Leuchten und ein Punkt unter dem Eintrag |

Bei „Bewegung reduzieren“ laufen keine Endlos-Animationen.

## Darstellungs-Einstellungen mit Live-Vorschau

Vorlage: Video 1 der ersten Runde. Bilder: `vorschau/navigation/darstellung-einstellungen.webp`, `live-vorschau-mit-aenderungsleiste.webp`.

- Gruppen: Design (fünf Karten mit Mini-Vorschau im jeweiligen Design), Hell oder dunkel (Segmente), Akzentfarbe (Farbkreise, erster Kreis „Design“ zeigt die Farbe des gewählten Designs), Schriftgröße (Segmente mit „Aa“ in drei Größen), Ecken (Segmente mit kleiner Form), Zahlen (Segmente), Menü-Stil (zehn Kacheln).
- Jede Auswahl setzt sofort die Attribute am `<html>` und rechnet `data-tone` und `data-nav` neu aus. Die ganze Seite (auch die Seitenleiste) zeigt die Wirkung, bevor gespeichert wird.
- Unten erscheint eine feste Leiste: „2 Änderungen · Die Vorschau gilt schon für die ganze Seite. · Verwerfen · Übernehmen“. Gezählt wird gegen den gespeicherten Stand. „Verwerfen“ setzt das Formular zurück und wendet den alten Stand wieder an. „Übernehmen“ speichert (normales Formular, POST). Ohne JavaScript gibt es einen normalen Speichern-Knopf.

## Kennzahlen-Kacheln

`.stats` mit fünf `.stat`: Zahl groß (Überschriftenschrift, 1,9 rem, Ziffern gleich breit), Beschriftung darunter. Rot umrandet (`.alert`) bei Überfälligem und fehlenden Protokollen, gelb (`.warn`) bei heute fällig und ohne Update. Mit Fallblatt (Violett oder `data-digits="fallblatt"`) werden die Zahlen zur Klapptafel, siehe `03`.

## Weitere Bausteine

Karten (`section.card`), Spalten (3:2 und 1:1), Tabellen in eigenem Scroll-Rahmen, Etiketten (Status-Farben), Ampeln (grün/gelb/rot/grau), Balken als `<progress>` mit Stufen (`bar-ok`, `bar-voll`, `bar-ueber`), Knöpfe (normal, primär, Gefahr, klein), Formular-Raster, Filter-Chips, Meldungen, Hinweise. Eine Übersicht mit Klassen steht in `referenz-code/design-kit/README.md`, alle Bausteine auf einer Seite in `referenz-code/design-kit/beispiel.html`.

## Druck

In jedem Design schwarz auf weiß, ohne Navigation; Elemente mit `no-print` werden ausgeblendet, `print-only` eingeblendet. Ampeln und Balken bleiben farbig (`print-color-adjust: exact`).
