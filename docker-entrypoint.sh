#!/bin/sh
set -eu

KONFIGURATION="${MAIN_DIRECTORY:-/konfiguration}"

mkdir -p "$KONFIGURATION"

# UGOS Pro legt bind-gemountete Ordner häufig mit NAS-eigenen Besitzern an.
# Der Entrypoint korrigiert nur den persistenten Konfigurationsordner und
# startet die Anwendung danach wieder als unprivilegierter Benutzer.
chown -R anwendung:anwendung "$KONFIGURATION"
chmod 0750 "$KONFIGURATION" || true
find "$KONFIGURATION" -type f -exec chmod 0600 {} \; 2>/dev/null || true

exec gosu anwendung "$@"
