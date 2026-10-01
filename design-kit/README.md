# Design-Paket: Projekt-Cockpit-Design für andere Webseiten

Mit diesem Paket bekommt jede Webseite die fünf Designs des Projekt-Cockpits: **Violett, Glas und Orange, Bronze, Hell und Schlicht**. Es besteht nur aus CSS, Schriften und einem kleinen Skript. Ein Framework ist nicht nötig, und es wird nichts von fremden Servern geladen.

## Inhalt

| Datei | Wofür |
|---|---|
| `cockpit-design.css` | alle Farben, Schriften und Bausteine (im Repository: `cockpit/static/app.css`) |
| `cockpit-basis.css` | Grundstil für bestehende Seiten ohne Cockpit-Klassen (optional) |
| `fonts/` | Schriften als WOFF2 mit Lizenz (SIL Open Font License) |
| `theme-umschalter.js` | Design wechseln und im Browser merken (optional) |
| `einbauen.py` | baut das Design automatisch in alle HTML-Seiten eines Ordners ein |
| `vorlage.html` | leere Seite mit Seitenleiste zum Kopieren für neue Seiten |
| `anmelden.html` | Anmeldeseite im Stil „Login form V7“ mit Aufklapp-Animation |
| `beispiel.html` | Beispielseite mit allen Bausteinen, einfach im Browser öffnen |
| `komponenten.js` | sechs bewegte Komponenten: Fallblatt-Zahlen, Schlüssel, Kassenbon, Karteikasten, Papierflieger, Orb (optional) |
| `komponenten.html` | alle sechs Komponenten zum Ausprobieren und Abschauen |

## Bestehende HTML-Seiten umstellen

### Automatisch, für alle Seiten auf einmal

Du brauchst Python 3. Auf Mac und Linux ist es meist schon da. Unter Windows gibt es Python kostenlos im Microsoft Store oder auf python.org; dort heißt der Befehl `py` statt `python3`.

1. Vorher eine Kopie des Webseiten-Ordners anlegen. Sicher ist sicher.
2. Ein Terminal im entpackten Ordner `design-kit` öffnen und zuerst nur ansehen, was passieren würde:

   ```
   python3 einbauen.py "/Pfad/zu/meiner-webseite"
   ```
3. Einbauen:

   ```
   python3 einbauen.py "/Pfad/zu/meiner-webseite" --grundstil --anwenden
   ```
4. Die Seiten im Browser öffnen und ansehen.

Optionen:

| Option | Wirkung |
|---|---|
| `--design hell` | Design wählen: `violett`, `glas` (Standard), `bronze`, `hell`, `schlicht` |
| `--modus hell` | helle oder dunkle Variante des Designs: `hell`, `dunkel` |
| `--akzent blau` | Akzentfarbe: `violett`, `blau`, `pink`, `gruen`, `orange`, `gelb`, `rot` |
| `--schrift gross` | Schriftgröße: `klein`, `gross` |
| `--ecken rund` | Ecken: `rund`, `weich`, `kantig` |
| `--menue kapsel` | Menü-Stil, siehe Tabelle unten |
| `--grundstil` | alte Seiten ohne neue Klassen gestalten (siehe unten), fast immer sinnvoll |
| `--umschalter` | Besucher können das Design selbst umschalten |
| `--zuruecksetzen --anwenden` | alle Seiten wieder in den Originalzustand |
| `--sicherungen-loeschen --anwenden` | die Sicherungskopien `*.vor-cockpit.bak` entfernen, wenn alles passt |

Das Skript kopiert die Design-Dateien in den Unterordner `design/` der Webseite. In jede Seite schreibt es vor `</head>` einen kurzen, markierten Block. Ein zweiter Lauf, zum Beispiel mit einem anderen Design, ersetzt diesen Block, statt einen weiteren anzuhängen. Seitenteile ohne `<head>` lässt es in Ruhe.

Lade anschließend den ganzen Ordner wie gewohnt auf den Webserver hoch, aber **ohne** die `*.vor-cockpit.bak`-Dateien.

### Von Hand, Seite für Seite

Den Ordner `design-kit` als `design` in den Webseiten-Ordner kopieren. In jeder Seite:

```html
<html lang="de" data-theme="glas">
<head>
  …
  <link rel="stylesheet" href="design/cockpit-design.css">
  <link rel="stylesheet" href="design/cockpit-basis.css">
</head>
<body class="cockpit-auto">
```

Bei Seiten in Unterordnern beginnt der Pfad mit `../design/…`.

### Was der Grundstil automatisch erledigt

Mit `cockpit-basis.css` und `<body class="cockpit-auto">` sehen übliche HTML-Seiten ohne weitere Änderungen passend aus:

- `<header>` wird zur Leiste oben, `<nav>` mit Links oder einer Liste wird zum Menü. Den aktuellen Menüpunkt mit `class="active"`, `class="aktiv"` oder `aria-current="page"` markieren.
- `<main>`, `<div id="content">`, `<div id="inhalt">`, `<div class="content">` oder `<div class="container">` wird mittig gesetzt.
- Jede `<section>` und jedes `<article>` darin wird eine Karte.
- Überschriften, Texte, Listen, Tabellen, Zitate, Formulare und Knöpfe bekommen das Design. Absende-Knöpfe werden zum Hauptknopf.
- `<footer>` wird eine ruhige Fußzeile.

Hat eine Seite ein eigenes Stylesheet (z. B. `style.css`), bleibt es eingebunden. Das Cockpit-Design steht danach und gewinnt deshalb meistens. Sieht etwas komisch aus, die Zeile mit dem alten Stylesheet testweise entfernen.

### Neue Seiten

`vorlage.html` kopieren, umbenennen und die mit „HIER“ markierten Stellen anpassen. Weitere Bausteine zum Kopieren stehen in `beispiel.html`. Liegt die neue Seite neben dem Ordner `design/`, den Pfad in der Vorlage zu `design/cockpit-design.css` ändern.

Das fertige ZIP entsteht mit `python3 tools/build_design_kit.py` (liegt danach in `dist/design-kit.zip`).

## Aussehen einstellen

Alles wird über Attribute am `<html>`-Element gesteuert, genau wie unter *Einstellungen → Darstellung* im Projekt-Cockpit:

| Attribut | Werte | Wirkung |
|---|---|---|
| `data-theme` | `violett`, `glas`, `bronze`, `hell`, `schlicht` | das Design |
| `data-mode` | `hell`, `dunkel` | helle oder dunkle Variante (weglassen = wie im Design) |
| `data-tone` | `hell`, `dunkel` | sagt den Akzentfarben, ob der Hintergrund hell oder dunkel ist; setzt `theme-umschalter.js` selbst, ohne Skript von Hand passend zum Design |
| `data-accent` | `violett`, `blau`, `pink`, `gruen`, `orange`, `gelb`, `rot` | Akzentfarbe für Knöpfe, Links, Menü |
| `data-size` | `klein`, `gross` | Schriftgröße |
| `data-shape` | `rund`, `weich`, `kantig` | Ecken (Bronze bleibt abgeschrägt) |
| `data-menu` | siehe nächste Tabelle | Stil des aktuellen Menüpunkts |
| `data-nav` | `voll`, `mini` | Seitenleiste offen oder als Symbolleiste (nur bei `violett`, `glas`, `hell`) |
| `data-digits` | `fallblatt`, `schlicht` | Kennzahlen als klappernde Abfahrtstafel (ohne Angabe nur bei Violett); braucht `komponenten.js` |

Menü-Stile (`data-menu`), nach den Vorlagen „10 Next-Gen Navigation Designs“:

| Wert | Stil |
|---|---|
| `fluessig` | Liquid Floating Bar: flüssige Pille in Akzentfarbe |
| `magnet` | Magnetic Dock: Einträge wachsen unter der Maus, der aktuelle als Kachel |
| `kapsel` | Glass Capsule Dock: Glas-Kapsel, aktueller Eintrag als runder Knopf |
| `segment` | Segmented Dynamic Bar |
| `orbit` | Orbit Navigation: Umlaufbahn um den aktuellen Eintrag |
| `welle` | Wave Indicator: laufende Welle darunter |
| `neon` | Cyber Neon Dock: dunkle Leiste, leuchtender Eintrag |
| `blob` | Morphing Blob: weicher Farbklecks, der seine Form ändert |
| `karten` | Layered Cards: aktueller Eintrag als Karte auf einem Stapel |
| `luxus` | Minimal Luxury: warmes Leuchten und ein Punkt |

Auf dem Handy wird das Menü der Seitenleiste automatisch zu einem Dock am unteren Rand, im gewählten Stil.

### Seitenleiste mit Profil, Suche und Zählern

`vorlage.html` und `beispiel.html` enthalten die komplette Seitenleiste nach dem Vorbild „SideBar UI“: Profil, Suche, Abschnitte (`span.nav-section`), Zähler (`span.nav-badge`) und den Knopf zum Einklappen (`button[data-nav-toggle]`). Den Zustand merkt sich `theme-umschalter.js` im Browser. Profil, Suche und Zähler dürfen wegbleiben.

### Anmeldeseite

`anmelden.html` zeigt die Anmeldung im Stil „Login form V7“: abgeschrägte Glaskarte, die beim Öffnen aus dem Logo aufklappt, Symbole in den Feldern und ein Auge zum Anzeigen des Passworts. Das Formular braucht auf deiner Webseite ein eigenes Ziel (`action`), etwa ein Login-Skript beim Hoster.

## Komponenten (komponenten.js)

`komponenten.html` zeigt alle sechs zum Ausprobieren. Einbinden mit
`<script src="komponenten.js" defer></script>` (oder `einbauen.py … --komponenten`). Jede Komponente startet über ein `data-`-Attribut; alles Weitere steht als Kommentar in `komponenten.html`.

| Komponente | Start mit | Was sie macht |
|---|---|---|
| Fallblatt-Zahlen | `[data-fallblatt]` um Kennzahlen, `[data-fallblatt-wert]` für einzelne Zahlen | Zahlen klappern wie auf einer Abfahrtstafel ins Bild. `data-fallblatt="immer"` gilt in jedem Design. Aus eigenem Code: `cockpitKomponenten.fallblatt(element, "12.481")` |
| Schlüssel | `[data-schluessel data-passwort="id" data-wiederholung="id"]` mit `[data-schluessel-bild]`, `[data-regel]`, `[data-staerke]` | jede erfüllte Passwort-Regel schneidet einen Zahn in den Schlüssel; sind 12 Zeichen erreicht und die Wiederholung stimmt, dreht der Schlüssel im Schloss |
| Kassenbon | `[data-bon]` mit Drucker und `[data-bon-papier]` | Preistabelle: Pakete (`data-preis`, `data-name`, `data-zeilen`), Monatlich/Jährlich mit `data-rabatt`; der Beleg wird Zeile für Zeile gedruckt, beim Wechsel abgerissen und neu gedruckt. Eigene Belege als `<template data-bon-vorlage>` |
| Karteikasten | `div.kartei[data-kartei]` und eine Liste `[data-kartei-eintraege]` | `Strg+K` / `⌘K` öffnet eine Kartei zum Suchen und Springen, ↑/↓ oder Mausrad blättert, Enter zieht die Karte. „g“ und dann ein Buchstabe springt direkt. Optional fragt `data-kartei-suche="/suche.json"` einen Server |
| Papierflieger | `[data-flieger]` mit `[data-flieger-karte]` und `[data-flieger-fertig]` | ein Formular faltet sich beim Absenden zum Flieger und fliegt davon. Mit `action="…"` wird danach ganz normal abgeschickt (z. B. an den Newsletter-Anbieter); ohne `action` ist es eine Vorschau |
| Orb | `[data-orb]` mit `canvas[data-orb-kugel]` und `form[data-orb-form]` | Eingabebox mit animierter Kugel in zwölf Stilen (Glas, Plasma, Chrom, Schwarm, Hologramm, Stimme, Aurora, Lava, Dither, Blase, Schwarzes Loch, Kristall), die auf Tippen, Nachdenken und jedes Wort reagiert. Mit `data-orb-quelle="/antwort"` kommen die Antworten von deinem Server (JSON `{"absaetze": [...], "links": [...]}`) |

Alle Komponenten funktionieren mit strenger Content-Security-Policy, folgen dem gewählten Design und laufen bei „Bewegung reduzieren“ ohne Animation.

## Grundsätzlich: so funktioniert das Design

1. Den Ordner auf den Webserver kopieren, z. B. nach `/design/`. `cockpit-design.css` und `fonts/` müssen nebeneinander liegen.
2. Im `<head>` jeder Seite:

   ```html
   <link rel="stylesheet" href="/design/cockpit-design.css">
   <script src="/design/theme-umschalter.js" defer></script>  <!-- nur wenn umschaltbar -->
   ```
3. Das Design am `<html>`-Element wählen:

   ```html
   <html lang="de" data-theme="glas">
   ```
   Möglich sind `violett`, `glas`, `bronze`, `hell` und `schlicht`.
4. Die Seite mit den Klassen aus der Tabelle unten aufbauen. Am schnellsten geht es, wenn du `beispiel.html` kopierst und anpasst.

### Design umschalten lassen

Mit `theme-umschalter.js` reicht eine Auswahlliste oder ein Knopf. Für die weiteren Einstellungen gibt es `data-look`, zum Beispiel `<select data-look="akzent">` oder `<button type="button" data-look="menue" data-value="neon">`; Beispiele stehen in `beispiel.html`. Ein einfacher Design-Wechsel geht so:

```html
<select data-theme-choice>
  <option value="violett">Violett</option>
  <option value="glas">Glas und Orange</option>
  <option value="bronze">Bronze</option>
  <option value="hell">Hell</option>
  <option value="schlicht">Schlicht</option>
</select>
<button type="button" data-theme-choice="hell">Hell</button>
```

Die Wahl wird im Browser gespeichert. Aus eigenem Code: `cockpitDesign.set("bronze")` oder `cockpitDesign.set({ theme: "hell", akzent: "blau", menue: "kapsel" })`.

### WordPress

In das (Child-)Theme kopieren und in der `functions.php`:

```php
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('cockpit-design', get_stylesheet_directory_uri() . '/design/cockpit-design.css');
    wp_enqueue_script('cockpit-design', get_stylesheet_directory_uri() . '/design/theme-umschalter.js', [], null, true);
});
add_filter('language_attributes', fn ($attr) => $attr . ' data-theme="glas"');
```

### React, Vue, Next.js und andere

Die CSS-Datei einmal global importieren (z. B. `import "./design/cockpit-design.css"`), den Ordner `fonts/` daneben legen und das Design setzen mit `document.documentElement.dataset.theme = "hell"`. In JSX heißt `class` dann `className`.

### Nur die Farben übernehmen

Wer schon ein eigenes Layout hat, kann nur die Variablen nutzen. Jedes Design setzt dieselben Variablen, z. B.:

```css
.mein-kasten {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--card-border);
  border-radius: var(--radius);
  backdrop-filter: var(--panel-filter);
}
.mein-knopf { background: var(--accent); color: var(--accent-contrast); }
```

Die wichtigsten Variablen: `--bg`, `--surface`, `--surface-2`, `--border`, `--text`, `--muted`, `--accent`, `--accent-contrast`, `--accent-text` (Links), `--danger`, `--ok`, `--warn`, `--radius`, `--font`, `--font-display`, `--font-mono`.

## Bausteine

| Baustein | Klassen |
|---|---|
| Rahmen mit Menü | `div.shell.with-nav` > `header.sidenav` (mit `a.brand`, `nav`, `.logout`) + `main` |
| Menüpunkt | `nav > a` mit `svg.icon` und `span.nav-label`, aktueller mit `aria-current="page"` |
| Kopfzeile | `.page-head` mit `h1`, `p.sub` und `.actions` |
| Karte | `section.card` mit `h2` und optional `span.count` |
| Kennzahlen | `.stats` > `a.stat` (+ `.alert` / `.warn`) mit `.value` und `.label`; mit `data-fallblatt` an `.stats` als Fallblatt-Anzeige (siehe Komponenten) |
| Spalten | `.columns` (3:2) oder `.columns-even` (1:1) |
| Tabelle | `.table-wrap > table`; erledigte Zeilen `tr.done` |
| Etiketten | `.badge` (+ `.red`, `.green`, `.offen`, `.in_arbeit`, `.wartet`, `.erledigt`) |
| Ampel | `.light.light-gruen` / `-gelb` / `-rot` / `-grau` |
| Balken | `<progress class="bar bar-ok|bar-voll|bar-ueber" max="100" value="62">` |
| Knöpfe | `.btn`, `.btn-primary`, `.btn-danger`, `.btn-small` |
| Formular | `.form-grid` oder `.inline-form` mit `.field` > `label` + Eingabefeld; Häkchen `label.check` |
| Filter-Chips | `nav.presets` > `a` (aktiv mit `aria-current="true"`) |
| Meldungen | `ul.flash > li.ok|.error`, Hinweise `p.note` oder `p.note.info` |
| Liste | `ul.plain-list` |

Ausdrucke sind in allen Designs automatisch schwarz auf weiß; was nicht gedruckt werden soll, bekommt die Klasse `no-print`.

## Gut zu wissen

- **Datenschutz:** Die Schriften liegen im Paket. Die Seite baut keine Verbindung zu Google Fonts oder anderen Servern auf.
- **Content-Security-Policy:** Das CSS kommt ohne Inline-Styles aus und funktioniert mit `style-src 'self'`.
- **Barrierefreiheit:** Kontraste sind auf WCAG AA geprüft; Fokus-Rahmen sind sichtbar; Animationen entfallen bei „Bewegung reduzieren“.
- **Browser:** aktuelle Versionen von Chrome, Edge, Firefox und Safari. Ältere Browser zeigen die Glas-Effekte ohne Unschärfe.
- **Eigenes Design:** Einen `[data-theme="..."]`-Block aus `cockpit-design.css` kopieren, umbenennen und die Farben ändern.
