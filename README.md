# Stalker Client

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale.

> Nutze den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Was kann der Docker-Container?

- Live-TV, Filme und Serien im Browser
- mehrere Portale und Benutzerkonten
- Favoriten und Wiedergabefortschritt
- Downloads, sofern sie vom Anbieter erlaubt sind
- persistente Konfiguration außerhalb des Containers
- Healthcheck und automatischer Neustart
- Multi-Arch-Image für `linux/amd64` und `linux/arm64`

Damit läuft das Image auf:

- Windows mit Docker Desktop
- Linux mit Docker Engine
- macOS mit Docker Desktop, Intel und Apple Silicon
- UGREEN NAS mit Docker/Compose
- Synology NAS mit Container Manager

Docker wählt automatisch die passende Architektur aus.

## Schnellinstallation

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose up -d
```

Danach im Browser öffnen:

```text
http://localhost:8080
```

Das Standard-Compose verwendet das Docker-Hub-Image:

```text
schrittfisch2000/stalker-client:latest
```

## Direkt mit `docker run`

```bash
docker run -d \
  --name stalker-client-deutsch \
  --restart unless-stopped \
  -p 8080:8080 \
  -e TZ=Europe/Berlin \
  -v "$(pwd)/konfiguration:/konfiguration" \
  schrittfisch2000/stalker-client:latest
```

Unter Windows PowerShell kann statt `$(pwd)` `${PWD}` verwendet werden.

## UGREEN NAS

1. Repository als ZIP herunterladen und auf die NAS kopieren.
2. Im Projektordner den Ordner `konfiguration` anlegen.
3. In UGOS **Docker → Projekte/Compose** öffnen.
4. `docker-compose-ugreen.yml` auswählen.
5. Projekt erstellen und starten.
6. `http://IP-DER-NAS:8080` öffnen.

## Synology NAS

Voraussetzung: **Container Manager** ist installiert.

1. Repository als ZIP herunterladen und in einen gemeinsamen Ordner kopieren.
2. Im Projektordner den Ordner `konfiguration` anlegen.
3. In Container Manager **Projekt → Erstellen** öffnen.
4. Den Projektordner auswählen und `docker-compose-synology.yml` verwenden.
5. Projekt bauen und starten.
6. `http://IP-DER-NAS:8080` öffnen.

Alternativ kann das Image in Container Manager direkt aus der Registry geladen werden:

```text
schrittfisch2000/stalker-client:latest
```

Dabei Port `8080` freigeben und einen NAS-Ordner nach `/konfiguration` einbinden.

## Updates

```bash
docker compose pull
docker compose up -d
```

Auf UGREEN oder Synology das Projekt neu bereitstellen, ohne den Ordner `konfiguration` zu löschen.

## Port ändern

```bash
STALKER_PORT=8180 docker compose up -d
```

Danach ist der Client unter `http://localhost:8180` erreichbar.

## Daten und Sicherheit

Die Konfiguration liegt dauerhaft im Ordner:

```text
./konfiguration
```

Dieser Ordner kann Portaladressen, MAC-Adressen, Benutzerkonten, Tokens, Geheimnisse und Logs enthalten. Er darf nicht veröffentlicht oder weitergegeben werden.

## Diagnose

```bash
docker compose ps
docker compose logs -f --tail=300
```

## Docker Hub veröffentlichen

Das Repository enthält einen GitHub-Actions-Workflow für Multi-Arch-Builds auf `linux/amd64` und `linux/arm64`.

Im GitHub-Repository müssen unter **Settings → Secrets and variables → Actions** diese Secrets angelegt werden:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

`DOCKERHUB_TOKEN` sollte ein Docker-Hub-Access-Token sein, nicht das Kontopasswort.

Danach kann der Workflow **Publish Docker image** manuell gestartet werden. Er veröffentlicht:

```text
schrittfisch2000/stalker-client:v<VERSION>
schrittfisch2000/stalker-client:latest
```

Die Versionsnummer wird aus der Datei `VERSION` gelesen.

## Lokaler Entwickler-Build

```bash
docker compose -f deploy/standard/docker-compose.yml up -d --build
```

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Wiedergabe und Downloads dürfen nur im Rahmen deiner Berechtigungen und der Nutzungsbedingungen des jeweiligen Anbieters erfolgen.
