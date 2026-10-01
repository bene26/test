# 7. Umsetzung in deiner App

Die Vorlage ist eine serverseitig gerenderte Web-App (Flask, Jinja2, SQLite) mit reinem CSS und JavaScript ohne Framework. Was davon direkt kopierbar ist, hängt von der Technik der Ziel-App ab.

## Empfohlene Reihenfolge

1. **Design-Tokens und Darstellungs-Optionen** (`02`): Tokens je Design, Akzente, Schriftgröße, Ecken; Speicherung je Benutzer; Einstellungsseite mit Live-Vorschau und Änderungsleiste. Alles Weitere baut darauf auf.
2. **Navigation:** Seitenleiste (voll/mini), Leiste oben, Handy-Dock, Zähler, zehn Menü-Stile.
3. **Login V7** und **Konto erstellen / Passwort ändern mit Schlüssel**.
4. **Karteikasten (Strg+K)** mit festen Einträgen, danach die Server-Suche.
5. **Kennzahlen mit Fallblatt**.
6. **Orb „Frag das Cockpit“**: erst Oberfläche und Kugeln mit der Beispielantwort, dann die Antwort-Regeln aus `04` an die eigenen Daten anpassen.
7. **Kassenbon** und **Papierflieger** dort, wo es in der Ziel-App passt (Beleg zu einem Datensatz, Versand-Formular).
8. **Fachfunktionen** (Aufgaben, Meetings, Zeitplan, Kontingente, Zeiten, Berichte), nur wenn gewünscht.

Nach jedem Schritt: Checkliste `06` für diesen Teil abhaken, Screenshots mit `vorschau/` vergleichen.

## Reine HTML-Webseiten

Das Design-Paket ist genau dafür gebaut (`referenz-code/design-kit/`, Anleitung in dessen `README.md`):

```
python3 einbauen.py "Pfad/zur/Webseite"                      # Vorschau, ändert nichts
python3 einbauen.py "Pfad/zur/Webseite" --design violett --akzent blau --menue kapsel \
        --zahlen fallblatt --grundstil --umschalter --komponenten --anwenden
```

- baut CSS, Schriften, Design-Umschalter und Komponenten in alle `.html`-Dateien ein, mit Sicherungskopie `*.vor-cockpit.bak`; `--zuruecksetzen --anwenden` macht alles rückgängig.
- `--grundstil` gestaltet auch Seiten ohne Cockpit-Klassen (Überschriften, Navigation, Formulare, Tabellen).
- Vorlagen zum Kopieren: `vorlage.html` (leere Seite mit Seitenleiste), `anmelden.html` (Login V7), `beispiel.html` (alle Bausteine), `komponenten.html` (die sechs Komponenten mit Kommentaren).
- Funktionen mit Server-Daten (Suche, Assistent, E-Mail) brauchen ein eigenes Backend; ohne Backend laufen Karteikasten (nur feste Einträge), Orb (Beispielantwort) und Papierflieger (Vorschau oder Absenden an einen Newsletter-Anbieter per `action`).

## React oder Next.js (Web)

- **CSS 1 : 1 übernehmen:** `app.css` als globales Stylesheet einbinden (oder in Teile zerlegen). Die Attribute (`data-theme`, `data-accent` …) setzt ein kleiner Provider auf `document.documentElement`; bei Next.js serverseitig ins `<html>` rendern (aus Benutzerprofil oder Cookie), damit nichts flackert.
- **Komponenten portieren:** Die Funktionen in `komponenten.js` sind nach Komponenten gegliedert und rein DOM-basiert. In React jeweils als Komponente mit `useRef` und `useEffect`; die Animationen über `element.animate()` (Web Animations API) bleiben gleich. Alternativ Framer Motion mit denselben Zeiten und Kurven aus `03`.
- **Orb:** Die zwölf Zeichenfunktionen (`ORB_DRAW`) sind reine Canvas-2D-Funktionen `(ctx, size, t, level, memo)`; direkt in eine Canvas-Komponente mit `requestAnimationFrame` übernehmen.
- **Strg+K:** globaler `keydown`-Listener im Layout; Dialog als Portal.
- **Server:** Suche und Assistent als API-Route (Next.js Route Handler) mit denselben Regeln; Antworten als JSON, im Client nur als Text rendern (React macht das automatisch, kein `dangerouslySetInnerHTML`).
- **Content-Security-Policy:** mit Nonce statt `unsafe-inline`, falls Next.js Inline-Skripte braucht.

## React Native / Expo (Android und iOS)

CSS gibt es dort nicht. Deshalb:

- **Tokens:** [`design-tokens.json`](design-tokens.json) enthält alle Werte je Design und Modus sowie alle Akzentfarben. Daraus ein Theme-Objekt bauen (Context oder Zustand-Store), das alle Komponenten lesen. `data-tone` entspricht dem effektiven Modus; bei „Schlicht“ ohne Wahl `useColorScheme()`.
- **Hintergründe:** die radialen Licht-Verläufe mit `expo-linear-gradient` oder Skia nachbauen; „Glas“-Flächen mit `expo-blur` (`BlurView`).
- **Schriften:** die WOFF2-Dateien liegen in `referenz-code/projekt-cockpit/cockpit/static/fonts/`; für Expo die TTF-Fassungen derselben Schriften (Sora, Geist, Geist Mono, Plus Jakarta Sans, JetBrains Mono, Manrope, Saira Condensed, alle SIL OFL) über `expo-font` laden.
- **Animationen:** `react-native-reanimated` mit den Zeiten und Kurven aus `03` (`withTiming(…, { duration, easing: Easing.bezier(…) })`, `withSequence`, `withDelay`). 3D-Kippen über `transform: [{ perspective }, { rotateX }]`.
- **Orb und Schlüssel:** `@shopify/react-native-skia` (Canvas und Pfade; die Zeichenfunktionen lassen sich fast wörtlich übertragen) oder `react-native-svg` für Schlüssel und Schloss.
- **Fallblatt:** jede Kachel als zwei Hälften mit `overflow: hidden` und zwei Klappen mit `rotateX`, wie in `03` beschrieben.
- **Karteikasten:** statt Strg+K ein Suchknopf in der Kopfzeile oder eine Wisch-Geste; Blättern mit Wischen (`react-native-gesture-handler`), dieselbe räumliche Anordnung.
- **Seitenleiste:** auf dem Handy die Tab-Leiste unten (entspricht dem Dock), auf Tablets eine einklappbare Seitenleiste.
- **„Bewegung reduzieren“:** `useReducedMotion()` aus Reanimated oder `AccessibilityInfo.isReduceMotionEnabled()`.
- **Speicher:** Darstellung im Benutzerprofil auf dem Server; auf dem Gerät zusätzlich in `AsyncStorage` für den Start vor dem Login (entspricht den Design-Cookies).

## Supabase als Backend

- Tabellen aus `04` als Postgres-Tabellen; Row Level Security auf jeder Tabelle (`auth.uid()`).
- Suche und Assistent als Postgres-Funktion (RPC) oder Edge Function mit denselben Regeln; Eingaben begrenzen, `ILIKE` mit maskierten Platzhaltern.
- Darstellung und Startseiten-Layout als Spalten (`jsonb`) im Profil.
- Erinnerungen: `pg_cron` ruft eine Edge Function auf; Push über Expo Notifications statt ntfy; E-Mail über einen Mail-Anbieter. Jede Erinnerung genau einmal (Tabelle wie `reminder_log`).
- Statusbericht per E-Mail als Edge Function, die `{ok, nachricht}` zurückgibt (für den Papierflieger).
- Dateien oder Sicherungen: Supabase Storage bzw. die eingebauten Backups.

## Was nicht 1 : 1 passt

- Strg+K und „g + Buchstabe“ gibt es nur mit Tastatur (Web, Tablet mit Tastatur).
- `clip-path`-Animationen (Login V7) laufen in React Native nicht; dort mit einer Maske (Skia) oder einer Skalierung aus der Kachel nachbilden.
- Druckansichten sind für Web gedacht; in einer Handy-App stattdessen PDF erzeugen (z. B. `expo-print`).
