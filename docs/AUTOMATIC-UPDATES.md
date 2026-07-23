# Automatische Updates über Docker Hub

## Ziel

Alle Plattformen verwenden dasselbe Image:

```
schrittfisch2000/stalker-client
```

Unterstützt:

- UGREEN UGOS Pro
- Linux Docker Engine
- Windows Docker Desktop
- macOS Docker Desktop

## Ablauf einer Veröffentlichung

1. Änderungen werden entwickelt und getestet.
2. Eine neue Version wird erstellt.
3. GitHub Actions baut das Docker Image.
4. Das Image wird für amd64 und arm64 veröffentlicht.
5. Docker Hub erhält:

```
schrittfisch2000/stalker-client:vX.Y.Z
schrittfisch2000/stalker-client:latest
```

6. Installationen ziehen beim Redeploy das neue Image.

## Compose

Produktivinstallationen verwenden:

```yaml
image: schrittfisch2000/stalker-client:latest
pull_policy: always
```

Die Laufzeitkonfiguration bleibt erhalten:

```yaml
volumes:
  - ./konfiguration:/konfiguration
```

## Entwickler

Für lokale Entwicklung kann weiterhin ein lokales Image gebaut werden:

```bash
docker compose up -d --build
```
