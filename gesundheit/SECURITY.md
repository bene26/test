# Sicherheit: Gesundheits-Cockpit

Kurzes Bedrohungsmodell. Bei jeder neuen Datenart, Quelle oder Rolle wieder lesen und anpassen.

## Wer nutzt die App

Ein Haushalt auf dem eigenen NAS. Es gibt genau **ein Login** und darunter mehrere **Profile** (Personen, z. B. Familie und Kinder). Wer den Login hat, sieht und vergleicht alle Personen; das ist so gewollt („alle sehen alle“). Es gibt keine Rollen und keine Freigaben nach außen. Die App läuft als eigener Docker-Container neben dem Projekt-Cockpit, mit eigener Datenbank und eigenem Login.

Folgen daraus: Das Passwort schützt die Daten aller Personen und muss entsprechend stark sein. Jede Person sollte wissen, dass ihre Werte hier gesammelt und mit den anderen verglichen werden; bei Kindern entscheiden die Eltern. Jede Person lässt sich mit allen Werten einzeln löschen.

## Welche Daten

Alles hier sind **Gesundheitsdaten, also besondere Kategorien personenbezogener Daten nach Art. 9 DSGVO**:

- Messwerte: Gewicht, Körperzusammensetzung, Blutdruck, Puls, Ruhepuls, Herzfrequenzvariabilität, Sauerstoffsättigung, Temperatur, Pulswellengeschwindigkeit, VO2max
- EKG-Einstufungen (Vorhofflimmern ja, nein oder unklar) aus Withings-Geräten, ohne die Kurven selbst
- Schlaf (Dauer, Phasen, Bewertung), Aktivität (Schritte, Kalorien, Minuten), Trainings, Garmin-Werte (Body Battery, Stress, Trainingsbereitschaft)
- Profile: Vorname oder Spitzname, Farbe, Geburtsjahr (optional, kein Datum), Größe, Ziele. Keine Standorte (GPS-Routen aus Apple Health werden nicht eingelesen)
- Zugangsdaten zu fremden Diensten: Withings-Token je Person und das Client-Secret der Withings-Anwendung (einmal für alle), Garmin-Token je Person. **Das Garmin-Passwort wird nie gespeichert**, nur einmal zum Anmelden weitergegeben.

## Vertrauensgrenzen

1. **Browser ↔ App** (Heimnetz, optional HTTPS über den Reverse Proxy des NAS). Der Browser ist nicht vertrauenswürdig: jede Eingabe wird auf dem Server geprüft.
2. **App ↔ Withings** (offizielle API, OAuth 2.0, HTTPS, nur lesende Rechte `user.info,user.metrics,user.activity,user.sleepevents`).
3. **App ↔ Garmin Connect** (inoffizielle Bibliothek `garminconnect`, HTTPS). Standardmäßig aus.
4. **Hochgeladene Dateien** (Apple-Health-Export als ZIP). Wird wie fremde, feindliche Eingabe behandelt.
5. **Andere Apps auf derselben NAS-Adresse.** Cookies trennen nicht nach Port: das Projekt-Cockpit auf `:8080` bekommt die Cookies dieser App mitgeschickt und umgekehrt. Deshalb eigene Cookie-Namen, und auf derselben Adresse nur eigene, vertrauenswürdige Apps betreiben (oder je App eine eigene Subdomain über den Reverse Proxy).

## Was ein Angreifer will und was dagegen steht

| Ziel | Schutz |
|---|---|
| Gesundheitsdaten lesen | Login für jede Seite außer Anmelden, Einrichten und `/health`; Sitzungen auf dem Server (nur der SHA-256 des Tokens liegt in der Datenbank); Cookies `HttpOnly`, `SameSite=Lax`, mit HTTPS `Secure`; `Cache-Control: no-store`; `robots: noindex`. |
| Konto übernehmen | Einrichtungscode beim ersten Start (nur im Container-Log und im Datenordner); Passwort mindestens 12 Zeichen, gehasht mit Werkzeug (scrypt); 5 Fehlversuche pro 15 Minuten und Adresse; Passwortwechsel meldet alle anderen Geräte ab. |
| Fremde Aktionen auslösen (CSRF) | Jedes POST braucht das Token der Sitzung, auch das Wechseln der Person; `form-action 'self'`; kein Zustandswechsel per GET. Der Withings-Rückruf prüft den zufälligen `state` und ordnet das Konto der Person zu, die den Vorgang gestartet hat. |
| Werte bei der falschen Person | Jede Zeile in der Datenbank trägt die Person; alle Abfragen filtern danach. Dasselbe Withings-Konto kann nicht zwei Personen zugeordnet werden. Die gezeigte Person steht nur als Nummer im Cookie und wird bei jeder Anfrage gegen die Datenbank geprüft. |
| Token von Withings oder Garmin stehlen | In der Datenbank nur verschlüsselt (Fernet, AES-128-CBC mit HMAC). Der Schlüssel liegt getrennt in `GESUNDHEIT_KEY` oder in der Datei `schluessel` im Datenordner (Rechte 600). Token erscheinen nie in Seiten, Logs oder Fehlermeldungen. Trennen löscht sie sofort. |
| Schadcode über den Upload | Nur ZIP mit `export.xml`; Größenlimit für den Upload und für jede entpackte Datei; Prüfung des Packverhältnisses (ZIP-Bombe); Dateinamen aus dem ZIP werden nie als Pfad benutzt, nichts wird auf die Platte entpackt; XML über `defusedxml` (keine Entitäten, keine externen Verweise); nur bekannte Datentypen werden übernommen, Zahlen mit Bereichsprüfung. |
| Schadcode in Seiten (XSS) | Jinja escapt alles; Content-Security-Policy ohne `unsafe-inline` und ohne fremde Quellen; Diagramme sind serverseitiges SVG ohne Skripte. |
| Fremde Seiten einbetten (Clickjacking) | `frame-ancestors 'none'`, `X-Frame-Options: DENY`. |
| Daten über die Garmin-Anmeldung abgreifen | Passwort nur im Arbeitsspeicher für die Dauer der Anmeldung; ein offener MFA-Schritt verfällt nach 5 Minuten. |

## Schlimmster realistischer Fall

Jemand im Heimnetz oder mit Zugriff auf das NAS liest die Datenbank und sieht die gesamte Gesundheitshistorie. Gegenmaßnahmen: Datenordner nur für den App-Benutzer lesbar (`umask 077`, `chmod 700`), Container ohne Root-Rechte, schreibgeschützt, ohne Linux-Capabilities. Wer die App von außen erreichbar macht, muss HTTPS über den Reverse Proxy nutzen und `GESUNDHEIT_SECURE_COOKIES=true` setzen.

## Datenschutz (DSGVO)

- **Zweck:** eigene Gesundheitsdaten an einem Ort sehen. Keine Weitergabe, keine Auswertung durch Dritte, keine KI, keine Werbung, keine Telemetrie.
- **Datenminimierung:** Herzfrequenz, Schritte, Energie und Strecke aus Apple Health werden schon beim Einlesen zu Tageswerten zusammengefasst; die Einzelwerte werden nicht gespeichert. GPS-Routen, EKG-Kurven, Medikamente, Zyklusdaten und Notizen werden ignoriert. Die hochgeladene ZIP-Datei wird nach dem Einlesen gelöscht.
- **Aufbewahrung:** einstellbar (Standard: unbegrenzt). Ältere Werte löscht die App nachts von selbst.
- **Löschen:** unter *Daten* je Quelle oder je Person, unter *Personen* das ganze Profil, oder alles auf einmal; sofort und endgültig (danach `VACUUM`, damit nichts in freien Seiten der Datei bleibt).
- **Auswertungen** rechnen nur mit den eigenen Daten auf dem NAS; nichts wird an Dienste geschickt. Zusammenhänge werden als Korrelation mit dem Hinweis „Zusammenhang heißt nicht Ursache“ gezeigt.
- **Export:** alle Werte als CSV.
- **Keine medizinische Beratung:** Einstufungen (z. B. Blutdruck nach ESH 2023) sind Orientierung und werden so beschriftet.

## Abhängigkeiten

Alle Versionen in `requirements.txt` fest. Neue Pakete nur, wenn der Aufwand für eigenen Code deutlich größer wäre. `garminconnect` ist inoffiziell und kann jederzeit brechen; die App läuft ohne die Garmin-Verbindung genauso.

## Fehler melden

Sicherheitsprobleme bitte nicht öffentlich als Issue, sondern direkt an die Person, die das Repository betreibt.
