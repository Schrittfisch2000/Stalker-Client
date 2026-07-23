# Stalker Client für UGREEN NAS

**Aktuelle Version: 1.0.30**

Dieses Repository stellt den Stalker Client ausschließlich als Docker-Compose-Projekt für UGREEN-NAS mit UGOS Pro bereit.

Das offizielle Docker-Image ist:

```text
schrittfisch2000/stalker-client:latest
```

Die NAS baut die Anwendung nicht lokal. UGOS lädt das fertige Image direkt von Docker Hub und wählt automatisch die passende Architektur für `linux/amd64` oder `linux/arm64`.

> Nutze den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Funktionen

- Live-TV, Filme und Serien im Browser
- mehrere Portale und Benutzerkonten
- Favoriten und Wiedergabefortschritt
- Downloads, sofern sie vom Anbieter erlaubt sind
- HTTPS-tauglicher Bildproxy für Poster und Logos
- dauerhafte Konfiguration außerhalb des Containers
- automatischer Neustart und Healthcheck
- Updates über Docker Hub ohne erneutes Kopieren des Quellcodes

## Benötigte Dateien

Für die Installation auf der UGREEN NAS wird nur eine Datei benötigt:

```text
docker-compose.yml
```

Der Ordner `konfiguration` wird auf der NAS angelegt und enthält später alle Einstellungen, Benutzer, Portalzugänge, Favoriten, Fortschritte und Logs.

## Installation über die UGOS-Weboberfläche

Diese Variante ist der empfohlene Weg. Sie benötigt kein `git`, `curl`, `wget` und kein Terminal auf der NAS.

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
└── konfiguration/
```

### 2. Compose-Datei einfügen

Im Ordner `stalker-client` eine neue Datei anlegen:

```text
docker-compose.yml
```

Inhalt:

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

UGOS lädt jetzt das Image `schrittfisch2000/stalker-client:latest` von Docker Hub.

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

## Update über die UGOS-Weboberfläche

Die Compose-Datei verwendet:

```yaml
pull_policy: always
```

Dadurch prüft UGOS beim erneuten Bereitstellen, ob auf Docker Hub ein neueres Image verfügbar ist.

Vorgehen:

1. In UGOS Pro **Docker** öffnen.
2. Das Projekt `stalker-client` stoppen.
3. Projekt aktualisieren, erneut bereitstellen oder neu erstellen.
4. Darauf achten, dass keine Option wie **Daten löschen**, **Volumes löschen** oder **Projektordner löschen** aktiviert ist.
5. Projekt wieder starten.
6. Browser vollständig neu laden.

Der Ordner `konfiguration` bleibt erhalten und wird nicht vom Docker-Image überschrieben.

## Port ändern

Standardmäßig läuft der Client auf Port `8080`.

Wenn Port 8080 belegt ist, in UGOS beim Compose-Projekt die Umgebungsvariable setzen:

```text
STALKER_PORT=8180
```

Danach lautet die Adresse:

```text
http://IP-DER-UGREEN-NAS:8180
```

## Konfiguration sichern

Alle Laufzeitdaten liegen im Projektordner unter:

```text
konfiguration
```

Diesen Ordner regelmäßig sichern. Er kann Portaladressen, MAC-Adressen, Benutzerkonten, Tokens, Tickets, Signaturschlüssel und Logs enthalten.

Den Ordner `konfiguration` niemals veröffentlichen oder ungeschwärzt in GitHub, Issues, Pull Requests oder Chats hochladen.

## Diagnose

In UGOS Pro:

1. **Docker** öffnen.
2. Projekt `stalker-client` auswählen.
3. Container `stalker-client` öffnen.
4. Protokolle anzeigen.

Nützliche Prüfungen:

- Containerstatus ist `running` oder `healthy`.
- Die Weboberfläche antwortet unter Port 8080 oder deinem geänderten Port.
- In der Oberfläche wird Version `1.0.30` angezeigt.
- Bilder und Poster werden über `/api/image?...` geladen, wenn die Seite über HTTPS läuft.

Vor dem Teilen von Logs müssen Portaladressen, MAC-Adressen, Tokens, Tickets und Zugangsdaten entfernt werden.

## Häufige Fehler

### Docker sucht ein Dockerfile

Wenn UGOS meldet, dass ein `Dockerfile` fehlt, wurde eine alte lokale Build-Compose-Datei verwendet.

Richtig ist nur diese Zeile:

```yaml
image: schrittfisch2000/stalker-client:latest
```

In der Compose-Datei darf kein `build:`-Block stehen.

### Einstellungen sind nach Update weg

Dann wurde wahrscheinlich der Ordner `konfiguration` gelöscht oder ein neues Projekt in einem anderen Ordner erstellt.

Der Projektordner muss weiterhin denselben Unterordner enthalten:

```text
konfiguration
```

### Port 8080 ist belegt

Setze `STALKER_PORT=8180` oder einen anderen freien Port in den Projektvariablen und stelle das Projekt neu bereit.

## Automatischer Docker-Build

GitHub Actions prüft bei Änderungen:

- Python-Unittests
- JavaScript-Syntax
- die UGREEN-Compose-Datei
- einen vollständigen Docker-Build
- versehentlich eingecheckte Konfigurations- oder Geheimnisdateien

Nach erfolgreichen Prüfungen auf `main` kann das Multi-Arch-Image für `linux/amd64` und `linux/arm64` auf Docker Hub veröffentlicht werden.

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Wiedergabe und Downloads dürfen nur im Rahmen deiner Berechtigungen und der Nutzungsbedingungen des jeweiligen Anbieters erfolgen.
