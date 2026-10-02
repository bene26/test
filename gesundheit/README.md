# Gesundheits-Cockpit

Deine Gesundheitsdaten von **Withings** (Waage, Blutdruck, Thermometer, Schlafmatte, ScanWatch), **Garmin** und **Apple Watch / iPhone** an einem Ort, auf deinem eigenen NAS. Eigener Docker-Container mit eigenem Login und eigener Datenbank, im selben Design wie das Projekt-Cockpit (fünf Designs, Akzentfarben, zehn Menü-Stile, Fallblatt-Zahlen, Fehlerseiten-Grafiken, Strg+K).

Keine Cloud, keine Werbung, keine Weitergabe. Die Daten verlassen das NAS nicht; die App holt sie nur ab.

## Seiten

| Seite | Inhalt |
|---|---|
| **Übersicht** | Vier Ringe für heute (Schritte, aktive Minuten, Aktivkalorien, Schlaf letzte Nacht), Kennzahlen mit Trend und Veränderung in 30 Tagen (Gewicht, Ruhepuls, HRV, Sauerstoff, Body Battery, VO2max), letzter Blutdruck mit Einstufung, letzte Nacht mit Schlafphasen, Schritte der Woche, Stand der Quellen |
| **Körper** | Gewicht mit Trendlinie, Zielgewicht und Band „Normalgewicht laut BMI“, BMI, Körperfett, Muskeln, Wasser, Knochen, Viszeralfett, Grundumsatz, Liste der Wiegungen |
| **Herz & Kreislauf** | Blutdruck je Tag (Bereich von diastolisch bis systolisch, farbig nach Stufe), Mittel der letzten 7 Tage mit Einstufung nach ESH 2023 und Grenze für Heimmessungen (135/85), einzelne Messungen, Ruhepuls, HRV, Sauerstoffsättigung, Pulswellengeschwindigkeit, Temperatur, Atemfrequenz, EKG-Einstufungen |
| **Schlaf** | Letzte Nacht mit Phasen (Tief, Leicht, REM, Wach), Schlafdauer je Nacht als gestapelte Balken mit Ziel, Schnitt, Bett- und Aufstehzeit, Anteile, Bewertung, Liste der Nächte |
| **Aktivität** | Schritte und aktive Minuten mit Ziel, Kalorien, Strecke, Etagen, Trainings nach Art, Garmin-Werte (Body Battery, Stress, Trainingsbereitschaft, VO2max), Liste der Trainings |
| **Verlauf** | Für jeden Wert: Diagramm, Durchschnitt, Minimum, Maximum, Werte je Tag mit gezählter Quelle und den Werten der anderen Quellen |
| **Quellen** | Withings verbinden, Garmin ein- und ausschalten und anmelden, Apple-Health-Export hochladen, Reihenfolge der Quellen je Bereich |
| **Daten** | Was gespeichert ist je Quelle, CSV-Export, Aufbewahrungsdauer, Löschen je Quelle oder alles |
| **Einstellungen** | Darstellung (wie im Projekt-Cockpit, mit Live-Vorschau), Größe und Ziele, Passwort |

Jede Seite hat die Zeiträume **7 T, 30 T, 90 T, 1 J**. Diagramme zeigen beim Darüberfahren oder Antippen den genauen Wert mit Quelle.

## Woher die Werte kommen

| Quelle | Weg | Was |
|---|---|---|
| **Withings** | offizielle Schnittstelle (OAuth 2.0), stündlich | Gewicht und Zusammensetzung, Blutdruck und Puls, Temperatur, SpO2, Pulswellengeschwindigkeit, Schlaf, Aktivität, Trainings, EKG-Einstufung |
| **Apple Health** | Export-Datei aus der Health-App (später eigene iPhone-App) | alles, was Apple Watch, iPhone und andere Apps dort speichern; auch Garmin und Withings, wenn deren Apps nach Apple Health schreiben |
| **Garmin direkt** | inoffizielle Bibliothek `garminconnect`, stündlich, **standardmäßig aus** | Body Battery, Stress, nächtliche HRV, Trainingsbereitschaft, Schlaf mit Bewertung, Aktivität, Trainings, VO2max |

### Nichts wird doppelt gezählt

Viele Werte kommen mehrfach: Schritte von Uhr **und** Telefon, ein Gewicht direkt von Withings **und** noch einmal über Apple Health. Die App zählt deshalb **pro Tag die erste Quelle in einer festen Reihenfolge**, die einen Wert hat. Werte verschiedener Quellen werden nie zusammengezählt oder gemittelt. Die Reihenfolge gilt je Bereich und lässt sich unter *Quellen → Reihenfolge* ändern:

| Bereich | Standard |
|---|---|
| Körper, Blutdruck, Temperatur | Withings → Withings über Apple → andere Apps → iPhone → Garmin … |
| Herz und Erholung, Schlaf, Aktivität | Garmin → Garmin über Apple → Apple Watch → Withings … (iPhone weit hinten) |

Beispiel: An Tagen mit Garmin-Uhr zählen deren Schritte, an Tagen mit Apple Watch die der Watch, und nur wenn keine Uhr getragen wurde die des iPhones. Dasselbe Training von zwei Quellen (Beginn innerhalb von 5 Minuten) steht einmal da. Auf jeder Verlaufsseite sieht man, welche Quelle gezählt hat und was die anderen gemessen hätten.

## Installation auf dem UGREEN NAS

Voraussetzungen und Grundlagen wie beim Projekt-Cockpit: [`docs/installation-ugreen.md`](../docs/installation-ugreen.md). Kurz:

1. **Das ganze Repository** auf das NAS kopieren (z. B. nach `docker/projekt-cockpit`). Die Gesundheits-App liegt im Unterordner `gesundheit/` und benutzt das Design aus `cockpit/static`.
2. In `docker/projekt-cockpit/gesundheit` die Datei `.env.example` nach `.env` kopieren und mindestens eintragen:
   ```
   GESUNDHEIT_BASE_URL=http://<IP-des-NAS>:8090
   ```
3. In der **Docker**-App ein neues **Projekt** anlegen, Name `gesundheits-cockpit`, Speicherpfad `docker/projekt-cockpit/gesundheit`, bereitstellen. Oder per SSH:
   ```
   cd /volume1/docker/projekt-cockpit/gesundheit
   sudo docker compose up -d --build
   ```
4. Den **Einrichtungscode** aus dem Container-Log oder aus `gesundheit/data/EINRICHTUNGSCODE.txt` holen, `http://<IP-des-NAS>:8090` öffnen, Konto anlegen.

Beide Apps laufen nebeneinander: Projekt-Cockpit auf Port 8080, Gesundheits-Cockpit auf 8090. Sie teilen sich nur das Aussehen, keine Daten und kein Login.

### Withings einrichten (einmalig, etwa 5 Minuten)

Withings verlangt für den Zugriff eine eigene, kostenlose „Anwendung“:

1. Auf **developer.withings.com** mit deinem Withings-Konto anmelden und unter *My apps* eine Anwendung anlegen: *Public API integration*, Zweck „persönliche Nutzung“.
2. Als **Callback URL** genau die Adresse eintragen, die die App unter *Quellen → Withings* anzeigt, also `GESUNDHEIT_BASE_URL` + `/quellen/withings/zurueck`.
   Falls Withings eine Adresse im Heimnetz (`http://192.168…`) nicht annimmt: die App über den Reverse Proxy des NAS mit HTTPS erreichbar machen und diese Adresse verwenden. Erreichbar von außen muss sie dafür nicht sein; die Rückleitung läuft nur über deinen Browser.
3. **Client-ID** und **Secret** unter *Quellen → Withings* eintragen (werden verschlüsselt gespeichert) oder in der `.env` als `WITHINGS_CLIENT_ID` / `WITHINGS_CLIENT_SECRET`.
4. **Mit Withings verbinden**, bei Withings zustimmen. Der erste Abgleich holt alle Messwerte und die Aktivitäten, Nächte und Trainings des letzten Jahres; danach stündlich nur Neues.

Die App fragt nur lesende Rechte an (`user.info, user.metrics, user.activity, user.sleepevents`).

### Apple Watch und iPhone

1. iPhone: **Health**-App → Profilbild oben rechts → **Alle Gesundheitsdaten exportieren**.
2. Die Datei `Export.zip` in „Dateien“ sichern oder per AirDrop an den Mac schicken.
3. Unter *Quellen → Apple Health* hochladen. Das Einlesen läuft im Hintergrund mit Fortschrittsanzeige; die ZIP-Datei wird danach gelöscht.

Jeder Export enthält die ganze Geschichte, ein neuer Import ersetzt die Apple-Werte derselben Tage. Bei sehr großen Exporten (über `GESUNDHEIT_UPLOAD_MAX_MB`, Standard 2 GB) die ZIP-Datei in den Ordner `gesundheit/import` auf dem NAS legen und unter *Quellen* „aus dem Ordner einlesen“.

Eine eigene kleine iPhone-App, die die Werte automatisch schickt, ist für später geplant; dann entfällt der Export.

### Garmin

Garmin-Werte kommen ohne weiteres Zutun über Apple Health mit, wenn die Garmin-Connect-App dort hineinschreibt (Connect-App → Einstellungen → Verbundene Apps → Apple Health). Für Body Battery, Stress, nächtliche HRV und Trainingsbereitschaft gibt es zusätzlich **Garmin direkt**:

- Unter *Quellen → Garmin direkt* einschalten, festlegen, wie viele Tage der erste Abgleich zurückgeht (Standard 30), mit E-Mail und Passwort von Garmin anmelden; bei Zwei-Faktor-Anmeldung kommt danach die Abfrage des Codes.
- **Wichtig:** Garmin bietet Privatpersonen keine offizielle Schnittstelle. Die Verbindung meldet sich an wie die Connect-App, kann jederzeit ausfallen und verträgt sich womöglich nicht mit Garmins Nutzungsbedingungen. Gespeichert werden nur die Anmelde-Token (verschlüsselt), nie das Passwort. Ausschalten löscht die Anmeldung sofort.

## Sicherheit und Datenschutz

Gesundheitsdaten sind besonders schützenswert (Art. 9 DSGVO). Die Einzelheiten stehen in [`SECURITY.md`](SECURITY.md), das Wichtigste:

- Login für jede Seite, Einrichtungscode beim ersten Start, Passwort ab 12 Zeichen, Sperre nach 5 Fehlversuchen, CSRF-Schutz, strenge Content-Security-Policy.
- Withings- und Garmin-Token verschlüsselt (Schlüssel in `GESUNDHEIT_KEY` oder `data/schluessel`, getrennt sichern oder bei Verlust einfach neu verbinden).
- Apple-Upload wird wie feindliche Eingabe behandelt (Größenlimit, ZIP-Bomben-Prüfung, kein Entpacken auf die Platte, XML ohne Entitäten).
- Herzfrequenz, Schritte und Energie aus Apple Health werden schon beim Einlesen zu Tageswerten zusammengefasst; GPS-Routen, EKG-Kurven, Medikamente, Zyklus und Notizen werden gar nicht gelesen.
- Aufbewahrungsdauer einstellbar, Löschen je Quelle oder alles, CSV-Export.
- Container ohne Root, schreibgeschützt, ohne Linux-Rechte, Datenordner nur für den App-Benutzer lesbar.
- Die Cookies heißen anders als die des Projekt-Cockpits. Browser trennen Cookies aber nicht nach Port: auf derselben NAS-Adresse nur eigene Apps betreiben.

Die Einstufungen (Blutdruck nach ESH 2023, BMI nach WHO) sind Orientierung, **keine Diagnose**, und stehen so auch auf den Seiten.

## Einstellungen in `.env`

| Variable | Standard | Bedeutung |
|---|---|---|
| `GESUNDHEIT_PORT` | `8090` | Port auf dem NAS |
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
python -m pytest                      # 149 Tests
python tools/demo_daten.py /tmp/demo  # ein Jahr Beispieldaten (nie in den echten Datenordner!)
GESUNDHEIT_DATA_DIR=/tmp/demo flask --app gesundheit run --port 8090
```

Aufbau: `gesundheit/katalog.py` (Quellen, Bereiche, alle Werte), `store.py` (Speichern und Quellen-Reihenfolge), `withings.py`, `apple.py`, `garmin.py` (Anbindungen), `jobs.py` (Hintergrund-Abgleich und Importe), `charts.py` (Diagramme als SVG), `views/` (Seiten). Das Design kommt aus `../cockpit/static` (im Container nach `/app/shared` kopiert); `themes.py` ist eine Kopie aus dem Cockpit, ein Test prüft, dass beide gleich bleiben.
