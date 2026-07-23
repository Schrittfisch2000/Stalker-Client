# Docker Hub Release Plan

## Ziel

Jede freigegebene Version soll automatisch als Docker-Image verfügbar sein.

## Ablauf

1. Entwicklung
2. Tests auf Mac und UGREEN
3. Versionsfreigabe
4. Git-Tag `vX.Y.Z`
5. GitHub Actions baut Multi-Arch Image
6. Push nach Docker Hub
7. UGREEN Redeploy zieht `latest`

## Docker Hub Tags

- Versions-Tag: `schrittfisch2000/stalker-client:vX.Y.Z`
- Aktueller Stand: `schrittfisch2000/stalker-client:latest`
