# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale mit deutscher Oberfläche und deutscher Docker-Konfiguration.

## Funktionen

- Live-TV, EPG, Filme und Serien
- Integrierter HTML5-/HLS-Player
- Portal-URL und MAC-Adresse über die Weboberfläche
- Lokale Konfiguration und automatisch erzeugtes App-Geheimnis
- Rotierende Protokolldatei im Projektordner
- Docker-Betrieb ohne `.env`
- Deutsche Container-, Image- und Projektbezeichnungen

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Herunterladen

[Projekt als ZIP herunterladen](https://github.com/Schrittfisch2000/Stalker-Client/archive/refs/heads/main.zip)

Alternativ mit Git:

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
```

## Erstellen und starten

Docker Desktop beziehungsweise Docker Engine muss installiert und gestartet sein.

```bash
docker compose build --no-cache
docker compose up -d
```

Danach die Weboberfläche öffnen:

```text
http://localhost:8080
```

Beim ersten Aufruf Portal-URL und MAC-Adresse eintragen.

## Deutsche Docker-Bezeichnungen

| Bestandteil | Bezeichnung |
|---|---|
| Compose-Projekt | `stalker-client-deutsch` |
| Dienst | `stalker-client` |
| Image | `stalker-client-deutsch:lokal` |
| Container | `stalker-client-deutsch` |
| Hostname | `stalker-client-deutsch` |
| Zeitzone | `Europe/Berlin` |
| Konfigurationsordner im Container | `/konfiguration` |

Docker-Schlüssel wie `services`, `build`, `ports`, `volumes` und `healthcheck` dürfen nicht übersetzt werden, weil Docker diese festen Schlüssel erwartet.

## Bedienung

Status anzeigen:

```bash
docker compose ps
```

Protokoll live anzeigen:

```bash
docker compose logs -f
```

Container neu starten:

```bash
docker compose restart
```

Container stoppen und entfernen:

```bash
docker compose down
```

Neu erstellen und starten:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Lokale Dateien

Im Projektordner werden automatisch erzeugt:

```text
portal-einstellungen.json
.stalker-geheimnis
stalker-client.log
```

Die Protokolldatei rotiert bei 10 MB. Maximal fünf Sicherungen werden behalten.

## Optionale technische Einstellungen

Die Variablennamen bleiben aus Kompatibilitätsgründen unverändert.

| Variable | Standardwert |
|---|---|
| `VERIFY_TLS` | `true` |
| `REQUEST_TIMEOUT` | `20` |
| `CONFIG_FILE` | `/konfiguration/portal-einstellungen.json` |
| `SECRET_FILE` | `/konfiguration/.stalker-geheimnis` |
| `LOG_FILE` | `/konfiguration/stalker-client.log` |

## Sicherheit

- `portal-einstellungen.json` und `.stalker-geheimnis` nicht weitergeben oder committen.
- Den Client nicht ungeschützt ins öffentliche Internet stellen.
- Protokolldateien vor dem Weitergeben auf sensible Angaben prüfen.
