# Docker Hub Auto Update

## Ziel

Neue Releases sollen ohne manuelles Kopieren auf der UGREEN verfügbar werden.

## Ablauf

Release → GitHub Actions → Docker Hub → UGREEN Redeploy

Die Daten im Volume `konfiguration` bleiben erhalten.
