#!/bin/bash
# ============================================================
# Gesundheits-Cockpit – Deploy auf NAS
# Doppelklick → sichert die Datenbank, kopiert die App, baut Docker neu
# ============================================================
#
# Einstellungen stehen gleich am Anfang von deploy_hauptlauf. Für einen
# anderen NAS lassen sie sich auch ohne Bearbeiten setzen, z. B.:
#   NAS_IP=192.168.1.50 ./deploy_to_nas.command
#
# ── Warum der ganze Ablauf in einer Funktion steht ───────────────────────────
# Bash liest ein Skript häppchenweise. Wird die Datei bearbeitet, während sie
# läuft, liest Bash an der alten Byteposition weiter und landet mitten in einer
# anderen Zeile. In einer Funktion muss Bash erst alles einlesen; danach ist die
# Datei auf der Platte gleichgültig.
deploy_hauptlauf() {
NAS_IP="${NAS_IP:-192.168.1.43}"
NAS_USER="${NAS_USER:-Benedikt}"
NAS_PATH="${NAS_PATH:-/volume2/docker/gesundheits-cockpit}"
PORT="${PORT:-6767}"
# Das Skript liegt in gesundheit/; gebaut wird aus dem Repository darüber,
# weil das Aussehen aus cockpit/static kommt (wie beim Projekt-Cockpit).
REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$NAS_PATH/gesundheit"

# Sicherung für ältere App-Versionen ohne "python -m gesundheit.manage sicherung"
read -r -d '' FALLBACK_BACKUP_PY <<'PY'
import datetime, os, pathlib, sqlite3
d = pathlib.Path(os.environ.get("GESUNDHEIT_DATA_DIR", "/data"))
p = d / "gesundheit.sqlite3"
if not p.exists():
    print("Keine Datenbank, nichts zu sichern.")
    raise SystemExit(0)
t = d / "sicherungen"
t.mkdir(mode=0o700, exist_ok=True)
f = t / ("gesundheit-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".sqlite3")
src, dst = sqlite3.connect(p), sqlite3.connect(f)
src.backup(dst)
dst.close()
src.close()
os.chmod(f, 0o600)
owner = d.stat()
for item in (t, f):
    os.chown(item, owner.st_uid, owner.st_gid)
print("Sicherung: " + str(f))
PY

CTRL_SOCK="/tmp/gesundheit-deploy-$$"
SSH="ssh -o ControlMaster=no -o ControlPath=$CTRL_SOCK -o BatchMode=yes"
REMOTE="$NAS_USER@$NAS_IP"

cleanup() {
  ssh -O exit -o ControlPath="$CTRL_SOCK" "$REMOTE" 2>/dev/null
  rm -f "$CTRL_SOCK"
}
trap cleanup EXIT

ende() {  # $1 = exit code
  echo ""
  echo "Drücke Enter zum Beenden..."; read DUMMY
  exit "$1"
}

echo ""
echo "❤️  Gesundheits-Cockpit – Deploy auf NAS"
echo "========================================"
echo "Von: $REPO"
echo "Zu:  $REMOTE:$NAS_PATH (Port $PORT)"
echo ""

if [ ! -f "$REPO/gesundheit/Dockerfile" ] || [ ! -d "$REPO/cockpit/static" ]; then
  echo "❌ Hier fehlt etwas: erwartet werden gesundheit/Dockerfile und cockpit/static"
  echo "   im Ordner $REPO. Das Skript muss im Ordner gesundheit/ des Repositorys liegen."
  ende 1
fi

# ─── Schritt 1: SSH-Verbindung (einmal anmelden) ─────────────────────────────
echo "🔌 SSH-Verbindung herstellen (Passwort einmalig eingeben)..."
ssh -fNM \
  -o ControlPath="$CTRL_SOCK" \
  -o ControlPersist=60m \
  -o ServerAliveInterval=30 \
  -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=accept-new \
  "$REMOTE"
if [ $? -ne 0 ]; then
  echo ""
  echo "❌ SSH-Verbindung fehlgeschlagen!"
  echo "   Prüfe: SSH am NAS aktiviert? Im Heimnetz? Benutzer $NAS_USER richtig?"
  ende 1
fi
echo "✅ SSH verbunden (alle weiteren Schritte ohne Passwort)"

DOCKER=$($SSH "$REMOTE" 'command -v docker || echo /usr/bin/docker' 2>/dev/null)

# ─── Alle Rückfragen JETZT, vor den langen Schritten ─────────────────────────
NOCACHE=""
read -p "🔄 Kompletten Rebuild ohne Cache erzwingen? (nur bei Problemen nötig) [j/N]: " FORCE_FULL
if [ "$FORCE_FULL" = "j" ] || [ "$FORCE_FULL" = "J" ]; then NOCACHE="--no-cache"; fi

# Steht in der .env auf dem NAS noch ein anderer Port (z. B. 8090 von früher)?
ENV_PORT=$($SSH "$REMOTE" "sed -n 's/^GESUNDHEIT_PORT=//p' \"$APP_DIR/.env\" 2>/dev/null | tail -1")
FIX_PORT=""
if [ -n "$ENV_PORT" ] && [ "$ENV_PORT" != "$PORT" ]; then
  echo ""
  echo "⚠️  In der .env auf dem NAS steht Port $ENV_PORT, gewünscht ist $PORT."
  read -p "   Port und Adresse in der .env auf $PORT umstellen? [J/n]: " ANSWER
  if [ "$ANSWER" != "n" ] && [ "$ANSWER" != "N" ]; then FIX_PORT="ja"; fi
fi

# ─── Schritt 2: Zielordner (nur beim allerersten Mal mit sudo) ───────────────
FOLDER_OK=$($SSH "$REMOTE" "mkdir -p \"$NAS_PATH\" 2>/dev/null && [ -w \"$NAS_PATH\" ] && echo ja || echo nein")
if [ "$FOLDER_OK" != "ja" ]; then
  echo ""
  echo "🔑 Sudo-Passwort für den NAS (einmalig, um $NAS_PATH anzulegen):"
  read -s -p "   Passwort: " NAS_SUDO_PASS
  echo ""
  # Das Passwort geht über stdin, nicht in die Befehlszeile (sonst stünde es
  # kurz in der Prozessliste des NAS).
  PERM_RESULT=$(printf '%s\n' "$NAS_SUDO_PASS" | $SSH "$REMOTE" \
    "sudo -S -p '' sh -c 'mkdir -p \"$NAS_PATH\" && chown $NAS_USER \"$NAS_PATH\"' 2>&1 && echo ORDNER_OK")
  unset NAS_SUDO_PASS
  if ! echo "$PERM_RESULT" | grep -q ORDNER_OK; then
    echo "$PERM_RESULT"
    echo ""
    echo "❌ Zielordner konnte nicht angelegt werden (sudo-Passwort falsch?)."
    ende 1
  fi
  echo "✅ Zielordner angelegt"
fi

# ─── Schritt 3: Datenbank sichern, bevor sich etwas ändert ───────────────────
# Neue Versionen bringen manchmal eine Änderung der Datenbank mit (Migration
# beim Start). Deshalb vor jedem Update eine Kopie, solange die alte Version
# noch läuft. Klappt die Sicherung nicht, wird NICHT aktualisiert.
echo ""
RUNNING=$($SSH "$REMOTE" "cd \"$APP_DIR\" 2>/dev/null && $DOCKER compose ps --status running -q gesundheit 2>/dev/null")
if [ -n "$RUNNING" ]; then
  echo "💾 Sichere die Datenbank..."
  BACKUP=$($SSH "$REMOTE" "cd \"$APP_DIR\" && $DOCKER compose exec -T gesundheit python -m gesundheit.manage sicherung" 2>&1)
  STATUS=$?
  if [ $STATUS -eq 2 ]; then
    # Ältere Version ohne den Befehl "sicherung": dieselbe Kopie direkt mit Python
    BACKUP=$(printf '%s\n' "$FALLBACK_BACKUP_PY" \
      | $SSH "$REMOTE" "cd \"$APP_DIR\" && $DOCKER compose exec -T gesundheit python -" 2>&1)
    STATUS=$?
  fi
  if [ $STATUS -ne 0 ]; then
    echo "$BACKUP" | tail -5 | sed 's/^/     /'
    echo ""
    echo "❌ Sicherung fehlgeschlagen. Deploy abgebrochen, es wurde nichts geändert."
    ende 1
  fi
  echo "✅ $BACKUP"
else
  echo "ℹ️  Die App läuft (noch) nicht auf dem NAS, es gibt nichts zu sichern."
fi

# ─── Schritt 4: Dateien kopieren (tar via SSH) ───────────────────────────────
# Mitgeschickt wird nur, was der Container braucht: gesundheit/ und das
# gemeinsame Aussehen aus cockpit/. NIE mit: die Daten (data/, import/,
# Datenbank samt -wal/-shm, Schlüssel, Sicherungen) und die .env.
# Erst in einen Zwischenordner entpacken, dann den Code austauschen: bricht
# die Übertragung ab, bleibt der laufende Stand unberührt, und gelöschte
# Dateien bleiben nicht als Leichen liegen.
echo ""
echo "📦 Kopiere Dateien aufs NAS (tar via SSH)..."
TAR_LOG="/tmp/gesundheit-tar-log-$$"
cd "$REPO" && \
COPYFILE_DISABLE=1 tar czf - \
  --exclude='gesundheit/data' \
  --exclude='gesundheit/import' \
  --exclude='gesundheit/.env' \
  --exclude='gesundheit/tests' \
  --exclude='gesundheit/tools' \
  --exclude='*.sqlite3' \
  --exclude='*.sqlite3-wal' \
  --exclude='*.sqlite3-shm' \
  --exclude='*.sqlite3-journal' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  gesundheit cockpit/static cockpit/templates/_grafiken.html \
| $SSH "$REMOTE" "cd \"$NAS_PATH\" \
    && rm -rf .upload && mkdir .upload \
    && tar xzf - -C .upload 2>&1 \
    && rm -rf gesundheit/gesundheit cockpit/static \
    && cp -a .upload/. . \
    && rm -rf .upload" \
> "$TAR_LOG" 2>&1
TAR_EXIT=$?
grep -v 'Ignoring unknown extended header keyword' "$TAR_LOG"
if [ $TAR_EXIT -ne 0 ] || grep -q 'Permission denied\|Cannot open\|No space' "$TAR_LOG" 2>/dev/null; then
  echo ""
  echo "❌ Dateien konnten NICHT übertragen werden. Der bisherige Stand läuft weiter."
  grep -E 'Permission denied|Cannot open|No space' "$TAR_LOG" | sed 's/^/     /' | head -10
  rm -f "$TAR_LOG"
  ende 1
fi
rm -f "$TAR_LOG"
echo "✅ Dateien kopiert"

# ─── Schritt 5: .env anlegen (nur wenn keine da ist), Ordner prüfen ──────────
LOCAL_ENV="$REPO/gesundheit/.env"
HAS_ENV=$($SSH "$REMOTE" "[ -f \"$APP_DIR/.env\" ] && echo ja || echo nein")
if [ "$HAS_ENV" = "ja" ]; then
  if [ -f "$LOCAL_ENV" ] && ! $SSH "$REMOTE" "cat \"$APP_DIR/.env\"" | cmp -s - "$LOCAL_ENV"; then
    echo "⚠️  .env: die Datei auf dem NAS weicht von der lokalen ab, sie wurde NICHT überschrieben."
  else
    echo "🔐 .env: bleibt wie sie ist"
  fi
  if [ "$FIX_PORT" = "ja" ]; then
    $SSH "$REMOTE" "cd \"$APP_DIR\" && cp .env .env.vor-portwechsel \
      && sed -i -e 's|^GESUNDHEIT_PORT=.*|GESUNDHEIT_PORT=$PORT|' \
                -e 's|^\(GESUNDHEIT_BASE_URL=.*\):$ENV_PORT\$|\1:$PORT|' .env"
    echo "🔐 .env: Port auf $PORT umgestellt (alte Fassung: .env.vor-portwechsel)"
  fi
elif [ -f "$LOCAL_ENV" ]; then
  $SSH "$REMOTE" "umask 077 && cat > \"$APP_DIR/.env\"" < "$LOCAL_ENV"
  echo "🔐 .env: lokale Fassung einmalig auf den NAS gelegt"
else
  # Erste Einrichtung: aus der Vorlage, mit Adresse, Port und den IDs des NAS-Benutzers
  $SSH "$REMOTE" "cd \"$APP_DIR\" && umask 077 && sed \
      -e 's|^GESUNDHEIT_PORT=.*|GESUNDHEIT_PORT=$PORT|' \
      -e 's|^GESUNDHEIT_BASE_URL=.*|GESUNDHEIT_BASE_URL=http://$NAS_IP:$PORT|' \
      -e \"s|^PUID=.*|PUID=\$(id -u)|\" \
      -e \"s|^PGID=.*|PGID=\$(id -g)|\" \
      .env.example > .env"
  echo "🔐 .env: aus der Vorlage angelegt (Adresse http://$NAS_IP:$PORT)"
fi
$SSH "$REMOTE" "mkdir -p \"$APP_DIR/data\" \"$APP_DIR/import\""

# ─── Schritt 6: Docker bauen + starten ───────────────────────────────────────
echo ""
if [ -n "$NOCACHE" ]; then
  echo "🐳 Vollständiger Rebuild ohne Cache, kann einige Minuten dauern..."
else
  echo "🐳 Baue mit Docker-Cache, nur Geändertes wird neu gebaut..."
fi
$SSH "$REMOTE" "cd \"$APP_DIR\" && $DOCKER compose build $NOCACHE && $DOCKER compose up -d"
DOCKER_OK=$?

echo ""
if [ $DOCKER_OK -ne 0 ]; then
  echo "❌ DEPLOY UNVOLLSTÄNDIG: die neuen Dateien liegen auf dem NAS,"
  echo "   aber der Container läuft noch mit dem ALTEN Stand (oder gar nicht)!"
  echo ""
  echo "   Steht oben „container name ... is already in use“, läuft die App noch"
  echo "   aus einem anderen Ordner. Dort einmal „docker compose down“ ausführen."
  echo ""
  echo "   Von Hand auf dem NAS:"
  echo "   cd \"$APP_DIR\" && docker compose build && docker compose up -d"
  ende 1
fi

# ─── Schritt 7: Warten, bis die App antwortet ────────────────────────────────
echo "⏳ Warte auf die App..."
HEALTHY=""
for _ in $(seq 1 45); do
  if curl -fsS -m 3 "http://$NAS_IP:$PORT/health" >/dev/null 2>&1; then HEALTHY="ja"; break; fi
  sleep 2
done
if [ -z "$HEALTHY" ]; then
  echo ""
  echo "❌ Der Container läuft, antwortet aber nicht auf http://$NAS_IP:$PORT/health."
  echo "   Die letzten Zeilen aus dem Log:"
  $SSH "$REMOTE" "cd \"$APP_DIR\" && $DOCKER compose logs --no-color --tail 25 gesundheit" | sed 's/^/     /'
  ende 1
fi

echo "✅ Deploy abgeschlossen: Dateien kopiert, Container neu gestartet, App antwortet."
CODE=$($SSH "$REMOTE" "cd \"$APP_DIR\" && $DOCKER compose logs --no-color gesundheit 2>&1 | grep -o 'Einrichtungscode: [A-F0-9-]*' | tail -1")
if [ -n "$CODE" ]; then
  echo ""
  echo "🆕 Erster Start: im Browser öffnen und mit diesem Code das Konto anlegen"
  echo "   $CODE"
fi
if [ "$FIX_PORT" = "ja" ]; then
  echo ""
  echo "⚠️  Neuer Port: bei Withings (developer.withings.com) die Callback URL auf"
  echo "   http://$NAS_IP:$PORT/quellen/withings/zurueck ändern, sonst klappt das Verbinden nicht."
fi
echo ""
echo "   Heimnetz:  http://$NAS_IP:$PORT"
echo "   Daten:     $APP_DIR/data (Sicherungen in data/sicherungen)"
ende 0
}

deploy_hauptlauf "$@"
