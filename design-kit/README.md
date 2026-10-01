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
| `vorlage.html` | leere Seite zum Kopieren für neue Seiten |
| `beispiel.html` | Beispielseite mit allen Bausteinen, einfach im Browser öffnen |

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

Mit `theme-umschalter.js` reicht eine Auswahlliste oder ein Knopf:

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

Die Wahl wird im Browser gespeichert. Aus eigenem Code: `cockpitDesign.set("bronze")`.

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
| Kennzahlen | `.stats` > `a.stat` (+ `.alert` / `.warn`) mit `.value` und `.label`; Ziffern als `span.digit` für die Klapp-Anzeige im Design Violett |
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
