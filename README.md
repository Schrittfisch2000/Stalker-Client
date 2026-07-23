# Stalker Client Docker

**Aktuelle Version: 1.0.34**

Stalker Client läuft als Docker-WebApp für kompatible Stalker-/MAG-Portale. Das Repository ist auf den Docker-Betrieb ausgerichtet; normale Installationen verwenden das fertige Docker-Hub-Image und bauen nicht lokal.

Offizielles Image:

```text
schrittfisch2000/stalker-client:latest
```

Das Image wird für `linux/amd64` und `linux/arm64` veröffentlicht. Damit funktioniert es auf UGREEN NAS, Linux-Servern, Docker Desktop unter macOS und Windows sowie auf Raspberry Pi 4/5 mit 64-Bit-System.

> Nutze den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Funktionen

- Live-TV, Filme und Serien im Browser
- vollständige Laufzeitanzeige und seekbarer Scrubber für Filme und Serien
- vorgewärmte Live-TV-Wechsel mit Audio-/Video-Synchronisierung
- mehrere Portale und Benutzerkonten
- Favoriten und Wiedergabefortschritt
- Downloads, sofern sie vom Anbieter erlaubt sind
- HTTPS-tauglicher Bildproxy für Poster und Logos
- dauerhafte Konfiguration außerhalb des Containers
- automatischer Neustart und Healthcheck
- Updates über Docker Hub ohne erneutes Kopieren des Quellcodes

## Benötigte Dateien

Für den Betrieb wird nur diese Datei benötigt:

```text
docker-compose.yml
```

Zusätzlich wird neben der Compose-Datei ein Ordner angelegt:

```text
konfiguration
```

Darin speichert die App später Einstellungen, Benutzer, Portalzugänge, Favoriten, Fortschritte und Logs. Diesen Ordner niemals löschen, wenn Einstellungen erhalten bleiben sollen.

## docker-compose.yml

Diese Compose-Datei ist für UGREEN, Linux, macOS, Windows Docker Desktop und Raspberry Pi geeignet:

```yaml
name: stalker-client-ugreen

services:
  stalker-client:
    image: schrittfisch2000/stalker-client:latest
    pull_policy: always
    container_name: stalker-client
    hostname: stalker-client
    restart: unless-stopped

    environment:
      TZ: ${TZ:-Europe/Berlin}
      LANG: C.UTF-8
      LC_ALL: C.UTF-8
      MAIN_DIRECTORY: /konfiguration
      CONFIG_FILE: /konfiguration/portal-einstellungen.json
      SECRET_FILE: /konfiguration/.stalker-geheimnis
      LOG_FILE: /konfiguration/stalker-client.log

    volumes:
      - ./konfiguration:/konfiguration

    ports:
      - "${STALKER_PORT:-8080}:8080"

    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

## Installation auf UGREEN NAS über die Weboberfläche

Diese Variante ist der empfohlene Weg für UGOS Pro. Sie benötigt kein `git`, `curl`, `wget` und kein Terminal auf der NAS.

### 1. Projektordner anlegen

1. In UGOS Pro den **Dateimanager** öffnen.
2. In den Docker-Bereich wechseln, zum Beispiel:

   ```text
   /volume1/docker
   ```

3. Einen neuen Ordner erstellen:

   ```text
   stalker-client
   ```

4. In diesem Ordner einen weiteren Ordner erstellen:

   ```text
   konfiguration
   ```

Die Struktur soll danach so aussehen:

```text
stalker-client/
├── docker-compose.yml
└── konfiguration/
```

### 2. Compose-Datei einfügen

Im Ordner `stalker-client` die Datei `docker-compose.yml` mit dem Inhalt aus dem Abschnitt **docker-compose.yml** anlegen.

Wichtig: Die Compose-Datei darf keinen `build:`-Block enthalten. UGOS soll das fertige Image von Docker Hub laden.

### 3. Docker-Projekt in UGOS erstellen

1. In UGOS Pro die App **Docker** öffnen.
2. Zu **Projekte**, **Compose** oder **Compose-Projekte** wechseln.
3. Ein neues Projekt erstellen.
4. Als Projektordner auswählen:

   ```text
   /volume1/docker/stalker-client
   ```

5. Als Compose-Datei auswählen:

   ```text
   docker-compose.yml
   ```

6. Projekt erstellen und starten.

UGOS lädt jetzt `schrittfisch2000/stalker-client:latest` von Docker Hub.

### 4. Weboberfläche öffnen

Im Browser öffnen:

```text
http://IP-DER-UGREEN-NAS:8080
```

Beispiel:

```text
http://192.168.178.4:8080
```

Beim ersten Start richtest du Portal, MAC-Adresse und Benutzer direkt in der Weboberfläche ein.

## UGREEN-Installation direkt aus dem Docker-Hub-Repository

Wenn du in der UGREEN-Docker-App nicht über **Compose/Projekt**, sondern über **Image** oder **Repository** installierst, verwende diese Werte.

Image:

```text
schrittfisch2000/stalker-client:latest
```

Containername:

```text
stalker-client
```

Port:

```text
Host-Port: 8080
Container-Port: 8080
Protokoll: TCP
```

Volume:

```text
NAS-Ordner: /volume1/docker/stalker-client/konfiguration
Container-Pfad: /konfiguration
```

Umgebungsvariablen:

```text
TZ=Europe/Berlin
MAIN_DIRECTORY=/konfiguration
CONFIG_FILE=/konfiguration/portal-einstellungen.json
SECRET_FILE=/konfiguration/.stalker-geheimnis
LOG_FILE=/konfiguration/stalker-client.log
```

Der Ordner `/volume1/docker/stalker-client/konfiguration` muss vorher im UGOS-Dateimanager angelegt werden. Er enthält später deine Einstellungen und darf bei Updates nicht gelöscht werden.

Ab Version `1.0.31` funktioniert das Image auch dann sauber, wenn UGOS nicht alle Umgebungsvariablen setzt. Für dauerhafte Daten solltest du trotzdem immer das Volume nach `/konfiguration` eintragen.

## Installation auf Linux

Voraussetzung ist ein installiertes Docker mit Docker Compose Plugin.

```bash
mkdir -p ~/stalker-client/konfiguration
cd ~/stalker-client
```

Dann `docker-compose.yml` aus dem Abschnitt **docker-compose.yml** in diesen Ordner legen und starten:

```bash
docker compose pull
docker compose up -d
```

Öffnen:

```text
http://IP-DES-LINUX-SERVERS:8080
```

Lokal auf demselben Rechner:

```text
http://localhost:8080
```

## Installation auf macOS mit Docker Desktop

1. Docker Desktop installieren und starten.
2. Einen Projektordner anlegen:

```bash
mkdir -p ~/stalker-client/konfiguration
cd ~/stalker-client
```

3. `docker-compose.yml` aus dem Abschnitt **docker-compose.yml** in diesen Ordner legen.
4. Container starten:

```bash
docker compose pull
docker compose up -d
```

Öffnen:

```text
http://localhost:8080
```

Docker Desktop auf Apple Silicon zieht automatisch das `arm64`-Image. Intel-Macs ziehen automatisch `amd64`.

## Installation auf Raspberry Pi

Unterstützt wird Raspberry Pi 4 oder 5 mit einem 64-Bit-Betriebssystem und Docker. Ein 32-Bit-System ist nicht empfohlen, weil das offizielle Image für `linux/arm64` veröffentlicht wird.

```bash
mkdir -p ~/stalker-client/konfiguration
cd ~/stalker-client
```

Dann `docker-compose.yml` aus dem Abschnitt **docker-compose.yml** in diesen Ordner legen und starten:

```bash
docker compose pull
docker compose up -d
```

Öffnen:

```text
http://IP-DES-RASPBERRY-PI:8080
```

Hinweis: Transcoding und Downloads können auf einem Raspberry Pi deutlich langsamer sein als auf einer NAS oder einem Desktop-Rechner.

## Installation auf Windows mit Docker Desktop

1. Docker Desktop installieren und starten.
2. Einen Ordner `stalker-client` anlegen.
3. Darin den Ordner `konfiguration` erstellen.
4. `docker-compose.yml` aus dem Abschnitt **docker-compose.yml** in den Ordner legen.
5. In PowerShell im Projektordner starten:

```powershell
docker compose pull
docker compose up -d
```

Öffnen:

```text
http://localhost:8080
```

## Updates

Die Compose-Datei verwendet:

```yaml
pull_policy: always
```

Dadurch wird beim erneuten Bereitstellen geprüft, ob Docker Hub ein neueres Image bereitstellt.

UGREEN Weboberfläche:

1. Docker-App öffnen.
2. Projekt `stalker-client` stoppen.
3. Projekt aktualisieren, erneut bereitstellen oder neu erstellen.
4. Keine Option wie **Daten löschen**, **Volumes löschen** oder **Projektordner löschen** aktivieren.
5. Projekt wieder starten.
6. Browser vollständig neu laden.

Terminal auf Linux, macOS, Windows oder Raspberry Pi:

```bash
docker compose pull
docker compose up -d
```

Der Ordner `konfiguration` bleibt erhalten und wird nicht vom Docker-Image überschrieben.

## Port ändern

Standardmäßig läuft der Client auf Port `8080`.

Wenn Port 8080 belegt ist, eine Umgebungsvariable setzen:

```text
STALKER_PORT=8180
```

Oder vor dem Start im Terminal:

```bash
STALKER_PORT=8180 docker compose up -d
```

Danach lautet die Adresse:

```text
http://IP-ODER-HOSTNAME:8180
```

## Konfiguration sichern

Alle Laufzeitdaten liegen im Projektordner unter:

```text
konfiguration
```

Diesen Ordner regelmäßig sichern. Er kann Portaladressen, MAC-Adressen, Benutzerkonten, Tokens, Tickets, Signaturschlüssel und Logs enthalten.

Den Ordner `konfiguration` niemals veröffentlichen oder ungeschwärzt in GitHub, Issues, Pull Requests oder Chats hochladen.

## Diagnose

UGREEN:

1. **Docker** öffnen.
2. Projekt `stalker-client` auswählen.
3. Container `stalker-client` öffnen.
4. Protokolle anzeigen.

Terminal:

```bash
docker compose ps
docker compose logs -f --tail=200
```

Nützliche Prüfungen:

- Containerstatus ist `running` oder `healthy`.
- Die Weboberfläche antwortet unter Port 8080 oder deinem geänderten Port.
- In der Oberfläche wird Version `1.0.34` angezeigt.
- Bilder und Poster werden über `/api/image?...` geladen, wenn die Seite über HTTPS läuft.

Vor dem Teilen von Logs müssen Portaladressen, MAC-Adressen, Tokens, Tickets und Zugangsdaten entfernt werden.

## Häufige Fehler

### Docker sucht ein Dockerfile

Dann wurde eine alte lokale Build-Compose-Datei verwendet.

Richtig ist nur diese Zeile:

```yaml
image: schrittfisch2000/stalker-client:latest
```

In der Compose-Datei darf kein `build:`-Block stehen.

### Permission denied: `/config`

Dann wurde ein altes Image oder eine alte Konfiguration gestartet, die noch auf `/config` statt `/konfiguration` zeigt.

Lösung:

1. In UGOS das Image `schrittfisch2000/stalker-client:latest` neu laden.
2. Den Container neu erstellen, nicht nur neu starten.
3. Als Volume eintragen:

   ```text
   /volume1/docker/stalker-client/konfiguration -> /konfiguration
   ```

4. Falls Umgebungsvariablen sichtbar sind, `LOG_FILE` auf diesen Wert setzen:

   ```text
   /konfiguration/stalker-client.log
   ```

Ab Version `1.0.31` sind die internen Standardwerte korrigiert.

### Einstellungen sind nach Update weg

Dann wurde wahrscheinlich der Ordner `konfiguration` gelöscht oder ein neues Projekt in einem anderen Ordner erstellt.

Der Projektordner muss weiterhin denselben Unterordner enthalten:

```text
konfiguration
```

### Port 8080 ist belegt

Setze `STALKER_PORT=8180` oder einen anderen freien Port und stelle das Projekt neu bereit.

### Raspberry Pi lädt kein Image

Prüfe, ob ein 64-Bit-System läuft:

```bash
uname -m
```

Erwartet ist `aarch64` oder `arm64`. Bei `armv7l` läuft ein 32-Bit-System.

## Automatischer Docker-Build

GitHub Actions prüft bei Änderungen:

- Python-Unittests
- JavaScript-Syntax
- die Compose-Datei
- einen vollständigen Docker-Build
- versehentlich eingecheckte Konfigurations- oder Geheimnisdateien

Nach erfolgreichen Prüfungen auf `main` veröffentlicht GitHub Actions automatisch das Multi-Arch-Image für `linux/amd64` und `linux/arm64` auf Docker Hub:

```text
schrittfisch2000/stalker-client:latest
schrittfisch2000/stalker-client:1.0.34
schrittfisch2000/stalker-client:v1.0.34
```

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Wiedergabe und Downloads dürfen nur im Rahmen deiner Berechtigungen und der Nutzungsbedingungen des jeweiligen Anbieters erfolgen.
