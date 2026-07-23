# Stalker Client für UGREEN NAS

**Aktuelle Version: 1.0.30**

Dieses Repository stellt den Stalker Client ausschließlich als Docker-Compose-Projekt für UGREEN-NAS mit UGOS Pro bereit.

> Nutze den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Funktionen

- Live-TV, Filme und Serien im Browser
- mehrere Portale und Benutzerkonten
- Favoriten und Wiedergabefortschritt
- Downloads, sofern sie vom Anbieter erlaubt sind
- dauerhafte Konfiguration außerhalb des Containers
- automatischer Neustart und Healthcheck
- Docker-Image für UGREEN-Systeme mit `amd64` oder `arm64`

Docker wählt auf der UGREEN NAS automatisch die passende Architektur aus.

## Benötigte Dateien

Für die Installation auf der NAS wird nur diese Datei benötigt:

```text
docker-compose.yml
```

Der Container wird direkt von Docker Hub geladen:

```text
schrittfisch2000/stalker-client:latest
```

Die Anwendung wird auf der NAS nicht lokal aus dem Quellcode gebaut.

## Installation über UGOS Pro

1. Auf der UGREEN NAS einen Projektordner anlegen, zum Beispiel:

   ```text
   /volume1/docker/stalker-client
   ```

2. Darin den Ordner für die dauerhafte Konfiguration anlegen:

   ```text
   konfiguration
   ```

3. Die Datei `docker-compose.yml` aus diesem Repository in den Projektordner kopieren.
4. In UGOS Pro **Docker → Projekte/Compose** öffnen.
5. Den Projektordner auswählen und das Compose-Projekt erstellen.
6. Das Projekt starten.
7. Im Browser öffnen:

   ```text
   http://IP-DER-UGREEN-NAS:8080
   ```

## Updates

Die Compose-Datei verwendet `pull_policy: always`. Beim erneuten Bereitstellen des Projekts lädt UGOS deshalb das aktuelle Image von Docker Hub.

Vorgehen in UGOS Pro:

1. Projekt stoppen.
2. Projekt aktualisieren oder neu bereitstellen.
3. Darauf achten, dass der Ordner `konfiguration` erhalten bleibt.
4. Projekt wieder starten.

Optional über das Terminal:

```bash
docker compose pull
docker compose up -d
```

## Port ändern

Standardmäßig ist die Anwendung über Port `8080` erreichbar.

In den Umgebungsvariablen des UGOS-Projekts kann ein anderer Port gesetzt werden:

```text
STALKER_PORT=8180
```

Danach lautet die Adresse beispielsweise:

```text
http://IP-DER-UGREEN-NAS:8180
```

## Konfiguration und Sicherung

Alle Laufzeitdaten liegen im Ordner:

```text
./konfiguration
```

Diesen Ordner vor Updates oder Änderungen sichern. Er kann unter anderem Portaladressen, MAC-Adressen, Benutzerkonten, Tokens, Signaturschlüssel und Logs enthalten.

Der Ordner darf niemals in Git eingecheckt, veröffentlicht oder ungeschwärzt weitergegeben werden.

## Diagnose

Die Container-Protokolle können direkt in UGOS Pro unter dem Docker-Projekt geöffnet werden.

Optional über das Terminal:

```bash
docker compose ps
docker compose logs -f --tail=300
```

Vor dem Teilen von Logs müssen Portaladressen, MAC-Adressen, Tokens, Tickets und Zugangsdaten entfernt werden.

## Automatischer Docker-Build

GitHub Actions prüft bei Änderungen:

- Python-Unittests
- JavaScript-Syntax
- die UGREEN-Compose-Datei
- einen vollständigen Docker-Build
- versehentlich eingecheckte Konfigurations- oder Geheimnisdateien

Nach erfolgreichen Prüfungen auf `main` wird das UGREEN-kompatible Multi-Arch-Image für `linux/amd64` und `linux/arm64` auf Docker Hub veröffentlicht.

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Wiedergabe und Downloads dürfen nur im Rahmen deiner Berechtigungen und der Nutzungsbedingungen des jeweiligen Anbieters erfolgen.
