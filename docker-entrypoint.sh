#!/bin/sh
# Prepare the data folder, then drop root and start the app as PUID:PGID.
# NAS systems often create bind-mounted folders as root, so fix ownership first.
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA="${COCKPIT_DATA_DIR:-/data}"

case "$PUID$PGID" in
  *[!0-9]*) echo "PUID und PGID müssen Zahlen sein." >&2; exit 1 ;;
esac
if [ "$PUID" = "0" ]; then
  echo "PUID=0 ist nicht erlaubt; die App läuft nie als root." >&2
  exit 1
fi

# New files (database, backups, keys) are readable only by the app user.
umask 077

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA"
  if [ "$(stat -c %u:%g "$DATA")" != "$PUID:$PGID" ]; then
    chown -R "$PUID:$PGID" "$DATA"
  fi
  chmod 700 "$DATA"
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups -- "$@"
fi
exec "$@"
