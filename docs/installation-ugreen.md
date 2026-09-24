# Installation auf dem UGREEN NAS (UGOS Pro, Docker)

Diese Anleitung bringt das Projekt-Cockpit als Docker-Container auf ein UGREEN NAS. Sie funktioniert genauso auf jedem anderen Rechner mit Docker, z. B. einem Raspberry Pi 4/5.

Die Beschriftungen in der Docker-App können je nach UGOS-Version leicht abweichen. Wo es hakt, gibt es in Schritt 4 den Weg über SSH, der immer gleich funktioniert.

## Was du brauchst

- UGREEN NAS mit UGOS Pro und installierter **Docker**-App (App Center)
- Zugriff auf die Dateien des NAS vom PC aus (Freigabe im Explorer/Finder oder die Dateien-App in UGOS)
- Internet auf dem NAS, damit beim ersten Start Python und die Pakete geladen werden können

## 1. Dateien auf das NAS kopieren

1. Auf GitHub im Repository den Branch mit dem Cockpit öffnen und über **Code → Download ZIP** herunterladen.
2. ZIP entpacken.
3. Auf dem NAS einen Ordner anlegen, z. B. `docker/projekt-cockpit`.
4. Den **Inhalt** des entpackten Ordners dort hineinkopieren. Danach muss `docker-compose.yml` direkt in `docker/projekt-cockpit` liegen, nicht in einem Unterordner.

## 2. Einstellungen in `.env` eintragen

1. Die Datei `.env.example` im selben Ordner kopieren und die Kopie `.env` nennen.
   Tipp: Dateien mit Punkt am Anfang sind im Explorer/Finder manchmal ausgeblendet.
2. `.env` mit einem Texteditor öffnen und mindestens diese Zeile anpassen:

   ```
   COCKPIT_BASE_URL=http://<IP-des-NAS>:8080
   ```

   Die IP des NAS steht in UGOS unter den Netzwerkeinstellungen, z. B. `192.168.1.10`.
3. Ist Port 8080 schon belegt, `COCKPIT_PORT` ändern (z. B. `8085`) und die URL entsprechend anpassen.

Push und E-Mail kannst du später einrichten (Schritt 6 und 7). Ohne `.env` startet das Cockpit auch, nur ohne Benachrichtigungen.

## 3. Projekt in der Docker-App anlegen

1. In UGOS die **Docker**-App öffnen und zu **Projekt** wechseln.
2. **Erstellen** wählen.
3. Projektname: `projekt-cockpit`.
4. Als Speicherpfad den Ordner `docker/projekt-cockpit` wählen. UGOS übernimmt die vorhandene `docker-compose.yml`. Falls stattdessen ein leerer Editor erscheint: den Inhalt von `docker-compose.yml` hineinkopieren.
5. **Bereitstellen** bzw. **Erstellen und starten**.

Beim ersten Start wird das Image gebaut. Das dauert ein paar Minuten.

## 4. Falls die Docker-App das Projekt nicht baut: über SSH

1. In UGOS unter **Systemsteuerung → Terminal** SSH aktivieren.
2. Vom PC aus verbinden: `ssh <dein-benutzer>@<IP-des-NAS>`
3. In den Ordner wechseln und starten. Den Pfad zeigt die Dateien-App in den Ordnereigenschaften an, häufig `/volume1/docker/projekt-cockpit`:

   ```
   cd /volume1/docker/projekt-cockpit
   sudo docker compose up -d --build
   ```

4. SSH danach wieder deaktivieren, wenn du es nicht brauchst.

## 5. Konto einrichten

1. Den Einrichtungscode holen, eine der beiden Möglichkeiten:
   - Docker-App → **Container** → `projekt-cockpit` → **Protokoll**. Dort steht `Einrichtungscode: XXXXXX-XXXXXX-XXXXXX`.
   - Datei `data/EINRICHTUNGSCODE.txt` im Projektordner (wird nach der Einrichtung gelöscht).
2. Im Browser `http://<IP-des-NAS>:8080` öffnen.
3. Code, Benutzername und ein Passwort mit mindestens 12 Zeichen eingeben.

Fertig. Als Nächstes unter **Team & Firmen** die Leute und Firmen anlegen, dann unter **Projekte** die Projekte.

## 6. Push-Erinnerungen aufs Handy (ntfy)

Das Cockpit schickt Erinnerungen über den Dienst **ntfy**. Die Nachrichten enthalten nur Zahlen und einen Link, z. B. „3 überfällig · 1 Protokoll fehlt“, keine Aufgabentitel oder Namen.

1. Die App **ntfy** installieren (Android: Google Play oder F-Droid, iPhone: App Store).
2. Einen langen, zufälligen Themennamen ausdenken, z. B. aus dem Passwort-Manager: `cockpit-k7f2q9x4m1v8`. Wer den Namen kennt, kann die Nachrichten mitlesen.
3. In der App **+** tippen, den Themennamen eintragen, Server `ntfy.sh` lassen, abonnieren.
4. In `.env` eintragen:

   ```
   NTFY_URL=https://ntfy.sh
   NTFY_TOPIC=cockpit-k7f2q9x4m1v8
   ```

5. Projekt in der Docker-App neu starten (bzw. per SSH `sudo docker compose up -d`).
6. Im Cockpit unter **Einstellungen → Testnachricht senden** prüfen.

Wer gar nichts über fremde Server schicken will, kann ntfy selbst auf dem NAS betreiben. Dann erreicht das Handy die Nachrichten aber nur im Heimnetz oder per VPN, und auf dem iPhone kommen sie ohne Weiterleitung über ntfy.sh verzögert an.

## 7. E-Mail (Protokolle versenden, optional Erinnerungen)

In `.env` die Daten des Mailservers eintragen. Die bekommst du von eurer IT oder deinem Mail-Anbieter:

```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=cockpit@example.com
SMTP_PASSWORD=...
SMTP_FROM=cockpit@example.com
REMINDER_EMAIL_TO=du@example.com     # leer lassen, wenn nur Push gewünscht
```

Hinweis: Bei Microsoft 365 ist der SMTP-Versand mit Benutzername und Passwort oft abgeschaltet. Dann bei der IT nach einem eigenen Versandkonto oder SMTP-Relay fragen.

Nach dem Speichern das Projekt neu starten. Unter **Einstellungen** steht, welche Kanäle eingerichtet sind.

## 8. Sicherung

- Das Cockpit legt jede Nacht eine Kopie der Datenbank in `data/backups/` ab und behält 14 Tage.
- Das schützt nicht vor einem Ausfall des NAS. Deshalb den Ordner `docker/projekt-cockpit/data` zusätzlich mit der Backup-Funktion von UGOS **verschlüsselt** auf ein anderes Ziel sichern (USB-Platte, zweites NAS oder Cloud).
- Unter **Einstellungen → Aktuelle Datenbank herunterladen** gibt es jederzeit eine Kopie.

**Wiederherstellen:** Projekt stoppen, `data/cockpit.sqlite3` durch die Sicherung ersetzen (Datei umbenennen in `cockpit.sqlite3`), Dateien `cockpit.sqlite3-wal` und `cockpit.sqlite3-shm` löschen, falls vorhanden, Projekt starten.

## 9. Sicherheit

- **Nicht per Portweiterleitung am Router ins Internet stellen.** Für den Zugriff von unterwegs ein VPN nutzen, z. B. WireGuard auf dem Router oder Tailscale.
- `.env` enthält Zugangsdaten. Die Datei bleibt auf dem NAS und gehört nicht ins Git-Repository.
- Der Container läuft ohne Root-Rechte (Benutzer 1000:1000), mit schreibgeschütztem Dateisystem. Nur der Ordner `data` ist beschreibbar.
- Mit HTTPS über einen Reverse Proxy zusätzlich `COCKPIT_SECURE_COOKIES=true` und `COCKPIT_TRUST_PROXY=true` setzen.

## 10. Update auf eine neue Version

1. Neue Dateien herunterladen und in den Projektordner kopieren. **`data/` und `.env` nicht löschen.**
2. Docker-App: Projekt stoppen und mit **Neu erstellen** bzw. **Build** wieder starten. Oder per SSH:

   ```
   cd /volume1/docker/projekt-cockpit
   sudo docker compose up -d --build
   ```

Die Datenbank wird beim Start automatisch auf den neuen Stand gebracht.

## Häufige Probleme

| Problem | Lösung |
|---|---|
| Seite lädt nicht | Läuft der Container? Docker-App → Container. Stimmt der Port? |
| „Permission denied“ im Protokoll | In `.env` `PUID`/`PGID` auf deinen NAS-Benutzer setzen (per SSH `id` ausführen) und neu starten. |
| Passwort vergessen | Per SSH: `sudo docker exec -it -u 1000:1000 projekt-cockpit python -m cockpit.manage passwort <benutzername>` (bei anderem PUID/PGID die Zahlen anpassen) |
| Keine Push-Nachrichten | Themenname in App und `.env` identisch? Testnachricht in den Einstellungen senden, dann das Container-Protokoll ansehen. |
| Links in Nachrichten führen ins Leere | `COCKPIT_BASE_URL` in `.env` prüfen. |
| Erinnerungen kommen zur falschen Uhrzeit | Zeitzone: `TZ=Europe/Berlin` in `.env`. |
