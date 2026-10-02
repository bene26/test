# Gesundheits-Cockpit

Die Gesundheitsdaten der ganzen Familie von **Withings** (Waage, Blutdruck, Thermometer, Schlafmatte, ScanWatch), **Garmin**, **Apple Watch / iPhone**, dem **Renpho-Maßband** und der **Körperanalyse in der Praxis** (Ernährungsberatung) an einem Ort, auf deinem eigenen NAS: mit **Befunden**, **Form und Wochen-Coach**, **Zielprognosen**, **Ausblick mit positiven und negativen Szenarien**, **Auswertungen**, **Zusammenhängen**, **Vergleich zwischen Personen** und **Berichten**. Eigener Docker-Container mit eigenem Login und eigener Datenbank. Standard ist das helle Design **Indigo** (weiße Karten, Indigo-Akzent, 3D-Skyline); die fünf Designs des Projekt-Cockpits, Akzentfarben, zehn Menü-Stile, Fallblatt-Zahlen, Fehlerseiten-Grafiken und Strg+K gibt es auch hier.

## Mehrere Personen

Ein Login, beliebig viele Profile (z. B. du, Partner, Kinder). Jede Person hat eine Farbe, eigene Größe und Ziele und verbindet ihre eigenen Geräte: ihr eigenes Withings-Konto, ihre eigene Garmin-Anmeldung, ihren eigenen Apple-Health-Export. Oben in der Seitenleiste wechselst du die gezeigte Person; alle Seiten zeigen dann ihre Werte. Unter *Personen* legst du Profile an, bearbeitest Ziele, änderst die Reihenfolge oder löschst eine Person mit allen Werten. Wer den Login kennt, sieht alle Personen.

Keine Cloud, keine Werbung, keine Weitergabe. Die Daten verlassen das NAS nicht; die App holt sie nur ab.

## Seiten

| Seite | Inhalt |
|---|---|
| **Übersicht** | **3D-Skyline** deines Jahres (eine Säule je Tag, Wochen entlang des Bands, umschaltbar Schritte/Belastung, 3, 6 oder 12 Monate, höchster Tag gelb, Wert beim Darüberfahren, baut sich Woche für Woche auf), **Form heute** (Fitness minus Ermüdung auf der Skala belastet ↔ frisch), Aktivitätsringe, der **wichtigste Befund** groß mit drei Zahlen, Rechenweg und Diagramm, weitere Befunde als Karten, **Wochen-Coach**, **Frag dein Cockpit**, Erholungs-Anzeigen, **Zielprognose** mit Glockenkurve und Regler, Kennzahlen, letzte Nacht, Blutdruck, Woche, Datenquellen. Neue Befunde meldet ein Hinweis unten rechts |
| **Ausblick** | Wie es weitergehen könnte, für Gewicht, Körperfett, VO2max, Ruhepuls, HRV, Schritte, Schlaf und Fitness, über 4 Wochen, 3 oder 6 Monate: **positiv** (wie in deinen besten vier Wochen des letzten Jahres), **wie bisher** und **negativ** (wie in deinen schwächsten). Je Wert ein Diagramm mit Vergangenheit, den drei Wegen und der Spanne dazwischen, wann ein Ziel erreicht wäre, und was in deinen guten Wochen anders war (z. B. „Schlafdauer: 7 h 40 min in den besten, 6 h 30 min in den schwächsten Wochen“) |
| **Befunde** | Alles, was in den Werten auffällt, jeweils gegen den eigenen Normalbereich: Ruhepuls und HRV der letzten Woche, zu harte „lockere“ Trainings (Zonen nach Karvonen), Belastungssprünge, Schlafmangel, schwankende Schlafenszeit, Gewichtstrend, Blutdruck über 135/85, Serien, schwache Wochentage, starke Zusammenhänge. Jeder Befund mit Rechenweg; die Zahl am Menüpunkt zählt die Hinweise |
| **Körper** | Gewicht mit Trendlinie, Zielgewicht und Band „Normalgewicht laut BMI“, BMI, Körperfett, Muskeln, Wasser, Knochen, Viszeralfett, Grundumsatz, Liste der Wiegungen. **Umfänge** vom Maßband (zwölf Stellen mit Veränderung, Taille, Bauch und Hüfte im Verlauf, Taille zu Größe und Taille zu Hüfte). **Analyse in der Praxis**: alle Termine nebeneinander (Phasenwinkel, Körperzellmasse, ECM/BCM, Wasser innen und außen, Fett, Muskeln …) und **zu Hause gegen Praxis** für alle Werte, die beide messen: Abstand am Termin, mittlerer Abstand, ob sich beide in dieselbe Richtung bewegen, Diagramm je Wert |
| **Herz & Kreislauf** | Blutdruck je Tag (Bereich von diastolisch bis systolisch, farbig nach Stufe), Mittel der letzten 7 Tage mit Einstufung nach ESH 2023 und Grenze für Heimmessungen (135/85), einzelne Messungen, Ruhepuls, HRV, Sauerstoffsättigung, Pulswellengeschwindigkeit, Temperatur, Atemfrequenz, EKG-Einstufungen |
| **Schlaf** | Letzte Nacht mit Phasen (Tief, Leicht, REM, Wach), Schlafdauer je Nacht als gestapelte Balken mit Ziel, Schnitt, Bett- und Aufstehzeit, Anteile, Bewertung, Liste der Nächte |
| **Aktivität** | Schritte und aktive Minuten mit Ziel, Kalorien, Strecke, Etagen, Trainings nach Art, Garmin-Werte (Body Battery, Stress, Trainingsbereitschaft, VO2max), Liste der Trainings |
| **Verlauf** | Für jeden Wert: Diagramm, Durchschnitt, Minimum, Maximum, Werte je Tag mit gezählter Quelle und den Werten der anderen Quellen |
| **Auswertungen** | Für jeden Wert: dieser Zeitraum gegen den Zeitraum davor und gegen dasselbe Fenster vor einem Jahr (Zahlen, Prozent, übereinandergelegte Kurven), Bestwerte, schwächster Tag, Ziel-Serien (längste und aktuelle), Durchschnitt je Wochentag, Kalender-Heatmap über 53 Wochen |
| **Zusammenhänge** | Automatische Erkenntnisse wie „Nach längeren Nächten ist dein Ruhepuls niedriger“ (nur wenn mindestens 20 gemeinsame Tage und ein deutlicher Zusammenhang da sind), dazu frei wählbar: Wert A gegen Wert B, am selben Tag oder am Tag danach, als Streudiagramm mit Ausgleichsgerade, Korrelation und Effekt („pro 1 Stunde Schlaf mehr im Schnitt 2 bpm weniger Ruhepuls“) |
| **Vergleich** | Alle oder ausgewählte Personen: Verlauf als farbige Linien, Tabelle mit Schnitt, Spanne, Veränderung und Zielerreichung, Rangliste, Radar „Ziele erreicht“ (jede Person an ihren eigenen Zielen gemessen) und eine Wochen-Challenge für Schritte, Minuten, Strecke und Trainingsminuten |
| **Berichte** | Woche oder Monat je Person, mit Vorwoche bzw. Vormonat verglichen: Kennzahlen, Diagramme, Blutdruck-Protokoll (morgens, mittags, abends mit Mittelwerten und Einstufung) und Trainings. Drucken oder als PDF speichern, z. B. für den Arzttermin |
| **Personen** | Profile mit Farbe, Geburtsjahr, Größe und Zielen (Schritte, Minuten, Kalorien, Schlaf, Trainings pro Woche, Zielgewicht mit Datum für die Prognose) |
| **Quellen** | Withings verbinden, Garmin ein- und ausschalten und anmelden, Apple-Health-Export hochladen, Reihenfolge der Quellen je Bereich |
| **Messungen eintragen** | Maßband (Hals, Schultern, Brust, Taille, Bauch, Hüfte, Oberarme, Oberschenkel, Waden je links und rechts) und Körperanalyse in der Praxis als Formular, ältere Werte als CSV-Tabelle (Vorlagen zum Herunterladen; Spalten wie „Taille“ oder „Phasenwinkel“ werden erkannt, Einheiten und Komma egal), Liste der Einträge mit Löschen |
| **Daten** | Was gespeichert ist je Quelle, CSV-Export, Aufbewahrungsdauer, Löschen je Quelle oder alles |
| **Einstellungen** | Darstellung (Indigo und die fünf Designs des Projekt-Cockpits, hell oder dunkel, mit Live-Vorschau), Passwort |

Jede Seite hat die Zeiträume **7 T, 30 T, 90 T, 1 J**. Diagramme haben weiche Kurven mit Farbverlauf, bauen sich beim Öffnen auf und zeigen beim Darüberfahren oder Antippen den genauen Wert mit Quelle. Alles ist serverseitiges SVG ohne Diagramm-Bibliothek; mit „Bewegung reduzieren“ entfallen die Animationen.

## Wie Befunde, Form, Coach und Prognose rechnen

Alles läuft mit festen, nachvollziehbaren Regeln auf dem NAS, ohne KI und ohne Internet. Jede Zahl lässt sich im Rechenweg auf der Seite nachverfolgen.

- **Belastung** je Tag ist der Trainingsimpuls nach Banister: Minuten × Herzfrequenzreserve × 0,64 × e^(1,92 × Reserve). Trainings ohne Puls zählen als mittel, aktive Minuten außerhalb von Trainings als leicht. Der Höchstpuls kommt aus dem Alter (220 − Alter) oder dem höchsten Trainingspuls, der Ruhepuls aus den letzten 30 Tagen.
- **Form** = Fitness (gleitender 42-Tage-Schnitt der Belastung) minus Ermüdung (7-Tage-Schnitt). Unter −10 „im Aufbau“, unter −30 „überlastet“, über +5 „frisch“. Erst ab drei Wochen mit Werten in den letzten sechs.
- **Taille zu Größe**: Taille geteilt durch Körpergröße; Faustregel (NICE 2022) unter 0,5, für Frauen und Männer gleich, deshalb braucht die App kein Geschlecht. Befunde melden 2 cm Veränderung der Taille in zwölf Wochen und vergleichen den letzten Praxistermin mit dem davor.
- **Befunde** vergleichen immer mit dir selbst, z. B. Ruhepuls der letzten 7 Tage gegen die 28 Tage davor (ab +3 Schlägen und der 1,5-fachen üblichen Schwankung). Die Grenzen stehen in jedem Rechenweg.
- **Wochen-Coach**: Ein Wochentag bekommt eine Einheit, wenn du an ihm in mindestens 4 der letzten 8 Wochen trainiert hast (häufigste Art, übliche Dauer). Sprechen mindestens zwei Zeichen für zu wenig Erholung (Form, Belastungssprung, Ruhepuls, HRV, Schlafmangel), wird die nächste harte Einheit kürzer und locker unter der Zone-2-Grenze; bei starker Überlastung kommt ein Ruhetag dazu. Das Original bleibt durchgestrichen sichtbar.
- **Ausblick**: drei Wege aus deiner eigenen Vergangenheit. Für Trend-Werte (Gewicht, Körperfett, VO2max) läuft die Rate pro Woche weiter, positiv die deiner besten vier Wochen im letzten Jahr, negativ die deiner schwächsten, wie bisher die der letzten acht Wochen. Die Raten flachen über etwa zwölf Wochen ab und sind gedeckelt (Gewicht höchstens 1 % pro Woche). Niveau-Werte (Ruhepuls, HRV, Schritte, Schlaf) bewegen sich in etwa drei Wochen zum Schnitt dieser Wochen. Fitness wird aus der Belastung weitergerechnet: wie bisher, schrittweise bis 30 % mehr mit ruhigen Wochen, oder eine Pause mit einem Drittel. Gewicht ohne Ziel bei normalem BMI hat „niedriger“ und „höher“ statt positiv und negativ. Ab acht Wochen Werten.
- **Zielprognose**: Normalverteilung um den fortgeschriebenen Trend (derselbe wie im Ausblick), dazu die drei Wege bis zum Zieldatum. Gewicht: Gerade durch die Messungen der letzten 60 Tage, Unsicherheit aus Tagesschwankung, Unsicherheit des Trends und 0,25 kg pro Woche Spielraum für geänderte Gewohnheiten. Schritte im Monat: Geschafftes plus ein üblicher Tag für jeden Resttag. Der Regler rechnet die Chance im Browser mit derselben Formel neu.
- **Frag dein Cockpit**: vorbereitete Fragen („Bin ich heute erholt?“, „Trainiere ich zu hart?“ …), deren Antworten aus deinen Zahlen zusammengesetzt werden. Eine Frage erscheint nur, wenn genug Daten für eine ehrliche Antwort da sind.

Zusammenhang heißt nicht Ursache, und kein Befund ersetzt ärztlichen Rat.

## Woher die Werte kommen

| Quelle | Weg | Was |
|---|---|---|
| **Withings** | offizielle Schnittstelle (OAuth 2.0), stündlich | Gewicht und Zusammensetzung, Blutdruck und Puls, Temperatur, SpO2, Pulswellengeschwindigkeit, Schlaf, Aktivität, Trainings, EKG-Einstufung |
| **Apple Health** | Export-Datei aus der Health-App (später eigene iPhone-App) | alles, was Apple Watch, iPhone und andere Apps dort speichern; auch Garmin und Withings, wenn deren Apps nach Apple Health schreiben |
| **Garmin direkt** | inoffizielle Bibliothek `garminconnect`, stündlich, **standardmäßig aus** | Body Battery, Stress, nächtliche HRV, Trainingsbereitschaft, Schlaf mit Bewertung, Aktivität, Trainings, VO2max |
| **Renpho-Maßband** | Taillenumfang über die Renpho-App und Apple Health; alle zwölf Stellen über *Messungen eintragen* oder CSV | Umfänge in cm |
| **Ernährungsberatung** | Ausdruck abtippen oder als CSV übernehmen | Körperanalyse mit Elektroden (bioelektrische Impedanz): Phasenwinkel, Resistanz, Reaktanz, Körperwasser, extra- und intrazelluläres Wasser, Körperzellmasse, extrazelluläre Masse, ECM/BCM-Index, Zellanteil, Fett, Muskeln, Grundumsatz |

### Nichts wird doppelt gezählt

Viele Werte kommen mehrfach: Schritte von Uhr **und** Telefon, ein Gewicht direkt von Withings **und** noch einmal über Apple Health. Die App zählt deshalb **pro Tag die erste Quelle in einer festen Reihenfolge**, die einen Wert hat. Werte verschiedener Quellen werden nie zusammengezählt oder gemittelt. Die Reihenfolge gilt je Bereich und lässt sich unter *Quellen → Reihenfolge* ändern:

| Bereich | Standard |
|---|---|
| Körper, Blutdruck, Temperatur | Withings → Withings über Apple → Renpho über Apple → andere Apps → iPhone → Garmin … → Praxis (zählt nur an Tagen ohne Messung zu Hause, weil das Gerät anders misst) |
| Umfänge | Maßband (eingetragen) → Renpho über Apple → andere Apps |
| Herz und Erholung, Schlaf, Aktivität | Garmin → Garmin über Apple → Apple Watch → Withings … (iPhone weit hinten) |

Beispiel: An Tagen mit Garmin-Uhr zählen deren Schritte, an Tagen mit Apple Watch die der Watch, und nur wenn keine Uhr getragen wurde die des iPhones. Dasselbe Training von zwei Quellen (Beginn innerhalb von 5 Minuten) steht einmal da. Auf jeder Verlaufsseite sieht man, welche Quelle gezählt hat und was die anderen gemessen hätten.

## Installation auf dem UGREEN NAS

### Am einfachsten: vom Mac per Doppelklick

`gesundheit/deploy_to_nas.command` im Finder doppelklicken (beim ersten Mal: Rechtsklick → Öffnen). Das Skript

1. meldet sich einmal per SSH am NAS an (Standard: `Benedikt@192.168.1.43`, Ordner `/volume2/docker/gesundheits-cockpit`, Port 6767; anders mit z. B. `NAS_IP=… ./deploy_to_nas.command` oder oben im Skript),
2. stellt alle Fragen gleich am Anfang (Rebuild ohne Cache? steht in der `.env` noch ein alter Port?),
3. **sichert die Datenbank**, solange die alte Version noch läuft (`data/sicherungen`, die letzten zehn bleiben); klappt das nicht, bricht es ab, ohne etwas zu ändern,
4. kopiert nur, was der Container braucht (`gesundheit/` ohne Daten, Tests und `.env`, dazu das Aussehen aus `cockpit/`), erst in einen Zwischenordner, dann wird der Code ausgetauscht,
5. legt beim ersten Mal die `.env` aus der Vorlage an (Adresse, Port, die Benutzer-IDs des NAS) und überschreibt eine vorhandene nie,
6. baut und startet den Container, wartet, bis `/health` antwortet, und zeigt beim ersten Start den **Einrichtungscode**.

Meldet es nicht „Deploy abgeschlossen“, läuft auf dem NAS noch der alte Stand; die Meldung sagt, was zu tun ist.

### Von Hand

Voraussetzungen und Grundlagen wie beim Projekt-Cockpit: [`docs/installation-ugreen.md`](../docs/installation-ugreen.md). Kurz:

1. **Das ganze Repository** auf das NAS kopieren (z. B. nach `docker/projekt-cockpit`). Die Gesundheits-App liegt im Unterordner `gesundheit/` und benutzt das Design aus `cockpit/static`.
2. In `docker/projekt-cockpit/gesundheit` die Datei `.env.example` nach `.env` kopieren und mindestens eintragen:
   ```
   GESUNDHEIT_BASE_URL=http://<IP-des-NAS>:6767
   ```
3. In der **Docker**-App ein neues **Projekt** anlegen, Name `gesundheits-cockpit`, Speicherpfad `docker/projekt-cockpit/gesundheit`, bereitstellen. Oder per SSH:
   ```
   cd /volume1/docker/projekt-cockpit/gesundheit
   sudo docker compose up -d --build
   ```
4. Den **Einrichtungscode** aus dem Container-Log oder aus `gesundheit/data/EINRICHTUNGSCODE.txt` holen, `http://<IP-des-NAS>:6767` öffnen, Konto anlegen.

Beide Apps laufen nebeneinander: Projekt-Cockpit auf Port 8080, Gesundheits-Cockpit auf 6767. Sie teilen sich nur das Aussehen, keine Daten und kein Login.

**Anderer Port:** in `.env` `GESUNDHEIT_PORT` und den Port in `GESUNDHEIT_BASE_URL` ändern, `docker compose up -d` ausführen und bei Withings die **Callback URL** auf die neue Adresse anpassen (sie muss genau stimmen, sonst schlägt das Verbinden fehl).

### Withings einrichten (einmalig, etwa 5 Minuten)

Withings verlangt für den Zugriff eine eigene, kostenlose „Anwendung“. Die trägst du **einmal** ein; danach verbindet jede Person ihr eigenes Withings-Konto (bei einer gemeinsamen Waage hat in der Withings-App jede Person ihr Profil). Dasselbe Withings-Konto lässt sich nicht zwei Personen zuordnen.

1. Auf **developer.withings.com** mit deinem Withings-Konto anmelden und unter *My apps* eine Anwendung anlegen: *Public API integration*, Zweck „persönliche Nutzung“.
2. Als **Callback URL** genau die Adresse eintragen, die die App unter *Quellen → Withings* anzeigt, also `GESUNDHEIT_BASE_URL` + `/quellen/withings/zurueck`.
   Falls Withings eine Adresse im Heimnetz (`http://192.168…`) nicht annimmt: die App über den Reverse Proxy des NAS mit HTTPS erreichbar machen und diese Adresse verwenden. Erreichbar von außen muss sie dafür nicht sein; die Rückleitung läuft nur über deinen Browser.
3. **Client-ID** und **Secret** unter *Quellen → Withings* eintragen (werden verschlüsselt gespeichert) oder in der `.env` als `WITHINGS_CLIENT_ID` / `WITHINGS_CLIENT_SECRET`.
4. Die Person oben in der Seitenleiste auswählen, **Mit Withings verbinden**, bei Withings mit ihrem Konto anmelden und zustimmen. Der erste Abgleich holt alle Messwerte und die Aktivitäten, Nächte und Trainings des letzten Jahres; danach stündlich nur Neues.

Die App fragt nur lesende Rechte an (`user.info, user.metrics, user.activity, user.sleepevents`).

### Apple Watch und iPhone

1. iPhone: **Health**-App → Profilbild oben rechts → **Alle Gesundheitsdaten exportieren**.
2. Die Datei `Export.zip` in „Dateien“ sichern oder per AirDrop an den Mac schicken.
3. Die Person auswählen, unter *Quellen → Apple Health* hochladen. Das Einlesen läuft im Hintergrund mit Fortschrittsanzeige; die ZIP-Datei wird danach gelöscht.

Jeder Export enthält die ganze Geschichte, ein neuer Import ersetzt die Apple-Werte derselben Tage. Bei sehr großen Exporten (über `GESUNDHEIT_UPLOAD_MAX_MB`, Standard 2 GB) die ZIP-Datei in den Ordner `gesundheit/import` auf dem NAS legen und unter *Quellen* „aus dem Ordner einlesen“.

Eine eigene kleine iPhone-App, die die Werte automatisch schickt, ist für später geplant; dann entfällt der Export.

### Garmin

Garmin-Werte kommen ohne weiteres Zutun über Apple Health mit, wenn die Garmin-Connect-App dort hineinschreibt (Connect-App → Einstellungen → Verbundene Apps → Apple Health). Für Body Battery, Stress, nächtliche HRV und Trainingsbereitschaft gibt es zusätzlich **Garmin direkt**:

- Für die gezeigte Person unter *Quellen → Garmin direkt* einschalten, festlegen, wie viele Tage der erste Abgleich zurückgeht (Standard 30), mit E-Mail und Passwort von Garmin anmelden; bei Zwei-Faktor-Anmeldung kommt danach die Abfrage des Codes.
- **Wichtig:** Garmin bietet Privatpersonen keine offizielle Schnittstelle. Die Verbindung meldet sich an wie die Connect-App, kann jederzeit ausfallen und verträgt sich womöglich nicht mit Garmins Nutzungsbedingungen. Gespeichert werden nur die Anmelde-Token (verschlüsselt), nie das Passwort. Ausschalten löscht die Anmeldung sofort.

## Sicherheit und Datenschutz

Gesundheitsdaten sind besonders schützenswert (Art. 9 DSGVO). Die Einzelheiten stehen in [`SECURITY.md`](SECURITY.md), das Wichtigste:

- Login für jede Seite, Einrichtungscode beim ersten Start, Passwort ab 12 Zeichen, Sperre nach 5 Fehlversuchen, CSRF-Schutz, strenge Content-Security-Policy.
- Withings- und Garmin-Token verschlüsselt (Schlüssel in `GESUNDHEIT_KEY` oder `data/schluessel`, getrennt sichern oder bei Verlust einfach neu verbinden).
- Apple-Upload wird wie feindliche Eingabe behandelt (Größenlimit, ZIP-Bomben-Prüfung, kein Entpacken auf die Platte, XML ohne Entitäten).
- Herzfrequenz, Schritte und Energie aus Apple Health werden schon beim Einlesen zu Tageswerten zusammengefasst; GPS-Routen, EKG-Kurven, Medikamente, Zyklus und Notizen werden gar nicht gelesen.
- Aufbewahrungsdauer einstellbar, Löschen je Quelle, je Person oder alles, CSV-Export aller Personen.
- Container ohne Root, schreibgeschützt, ohne Linux-Rechte, Datenordner nur für den App-Benutzer lesbar.
- Die Cookies heißen anders als die des Projekt-Cockpits. Browser trennen Cookies aber nicht nach Port: auf derselben NAS-Adresse nur eigene Apps betreiben.

Die Einstufungen (Blutdruck nach ESH 2023, BMI nach WHO) sind Orientierung, **keine Diagnose**, und stehen so auch auf den Seiten.

## Einstellungen in `.env`

| Variable | Standard | Bedeutung |
|---|---|---|
| `GESUNDHEIT_PORT` | `6767` | Port auf dem NAS |
| `GESUNDHEIT_BASE_URL` | – | Adresse der App, für den Withings-Rückruf |
| `TZ` | `Europe/Berlin` | Zeitzone für Tage und Nächte |
| `PUID`, `PGID` | `1000` | Benutzer, unter dem die App läuft |
| `GESUNDHEIT_SECURE_COOKIES`, `GESUNDHEIT_TRUST_PROXY` | `false` | auf `true` hinter einem Reverse Proxy mit HTTPS |
| `GESUNDHEIT_SYNC_MINUTES` | `60` | Abstand der Abgleiche (mindestens 15) |
| `GESUNDHEIT_UPLOAD_MAX_MB` | `2048` | größter Upload im Browser |
| `GESUNDHEIT_KEY` | – | eigener Schlüssel für die Token, sonst `data/schluessel` |
| `WITHINGS_CLIENT_ID`, `WITHINGS_CLIENT_SECRET` | – | statt der Eingabe auf der Seite *Quellen* |

## Passwort vergessen

```
sudo docker exec -it -u 1000:1000 gesundheits-cockpit python -m gesundheit.manage passwort <name>
```

## Entwicklung

```
cd gesundheit
pip install -r requirements.txt pytest
python -m pytest                      # 269 Tests
python tools/demo_daten.py /tmp/demo  # ein Jahr Beispieldaten für drei Personen (nie in den echten Datenordner!)
GESUNDHEIT_DATA_DIR=/tmp/demo flask --app gesundheit run --port 6767
```

Aufbau: `gesundheit/katalog.py` (Quellen, Bereiche, alle Werte), `persons.py` (Profile, gezeigte Person), `store.py` (Speichern und Quellen-Reihenfolge, immer je Person), `auswertung.py` (Zeiträume, Bestwerte, Zusammenhänge, Vergleich, Berichte), `belastung.py` (Belastung, Fitness, Ermüdung, Form), `befunde.py` (Regeln für die Befunde), `coach.py` (Wochenplan), `prognose.py` (Zielprognosen), `ausblick.py` (Szenarien positiv, wie bisher, negativ), `messungen.py` (Maßband und Praxis: Eingabe, CSV, Vergleich zu Hause gegen Praxis), `fragen.py` (vorbereitete Antworten), `uebersicht.py` (Skyline, Datenquellen), `withings.py`, `apple.py`, `garmin.py` (Anbindungen), `jobs.py` (Hintergrund-Abgleich und Importe), `charts.py` (Diagramme als SVG, auch die isometrische Skyline), `views/` (Seiten). Das Design kommt aus `../cockpit/static` (im Container nach `/app/shared` kopiert); `themes.py` übernimmt die Designs des Cockpits (ein Test prüft das) und ergänzt „Indigo“, dessen Farben in `static/gesundheit.css` stehen.
