# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale.

## Funktionen

- Live-TV, EPG, Filme und Serien
- Integrierter HTML5-/HLS-Player
- Portal-URL und MAC-Adresse über die Weboberfläche
- Lokale Konfiguration und automatisch erzeugtes App-Secret
- Rotierende Logdatei im Projektordner
- Docker-Betrieb ohne `.env`

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Installation

### Download

Projekt als ZIP herunterladen:

https://github.com/Schrittfisch2000/Stalker-Client/archive/refs/heads/main.zip

Alternativ mit Git:

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
```

### Windows

1. Docker Desktop installieren und starten.
2. ZIP entpacken und PowerShell im Projektordner öffnen.
3. Docker-Image erstellen und Container starten:

```powershell
docker compose build
docker compose up -d
```

### Linux

Docker Engine und Docker Compose installieren. Danach im Projektordner:

```bash
docker compose build
docker compose up -d
```

### macOS

Docker Desktop installieren und starten. Danach im Projektordner:

```bash
docker compose build
docker compose up -d
```

Weboberfläche öffnen:

```text
http://localhost:8080
```

Beim ersten Aufruf Portal-URL und MAC-Adresse eintragen. Eine `.env`-Datei ist nicht erforderlich.

## Lokale Dateien

Im Projektordner werden automatisch erzeugt:

```text
portal-settings.json
.stalker-secret
stalker-client.log
```

Die Logdatei rotiert bei 10 MB; maximal fünf Sicherungen werden behalten.

## Docker-Befehle

```bash
docker compose logs -f
docker compose restart
docker compose down
```

## Optionale Konfiguration

| Variable | Standard |
|---|---|
| `VERIFY_TLS` | `true` |
| `REQUEST_TIMEOUT` | `20` |
| `CONFIG_FILE` | `/config/portal-settings.json` |
| `SECRET_FILE` | `/config/.stalker-secret` |
| `LOG_FILE` | `/config/stalker-client.log` |

## Sicherheit

- `portal-settings.json` und `.stalker-secret` nicht weitergeben oder committen.
- Den Client nicht ungeschützt ins öffentliche Internet stellen.
- Logdateien vor dem Weitergeben auf sensible Angaben prüfen.
