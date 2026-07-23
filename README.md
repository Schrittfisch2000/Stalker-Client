# Stalker Client

**Aktuelle Version: 1.0.30 – offizielles Multi-Arch-Docker-Image und vereinheitlichte Updates**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Unterstützt Live-TV, Filme, Serien, mehrere Portale, Benutzerkonten, Favoriten, Wiedergabefortschritt und Downloads.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Neu in Version 1.0.30

- offizielles Docker-Hub-Image: `schrittfisch2000/stalker-client`
- dasselbe Image für UGREEN/NAS, Linux, Windows Docker Desktop und macOS Docker Desktop
- Multi-Arch-Veröffentlichung für `linux/amd64` und `linux/arm64`
- automatische Veröffentlichung durch GitHub Actions bei Versions-Tags wie `v1.0.30`
- Tags `v1.0.30` und `latest` werden gemeinsam veröffentlicht
- Standard-Compose-Dateien laden das Registry-Image statt lokal zu bauen
- `pull_policy: always` prüft bei jedem erneuten Bereitstellen auf ein aktuelles Image
- lokale Entwickler-Compose-Dateien bleiben unter `deploy/` erhalten
- Versionsnummern in Anwendung, Frontend, Cache-Schlüsseln, README und Entwickler-Compose-Dateien werden automatisch geprüft

Version 1.0.30 enthält außerdem alle Sicherheits-, HTTPS-Bildproxy- und Katalogverbesserungen aus Version 1.0.29.

## Enthaltene Sicherheits- und Katalogverbesserungen

- sicherer Same-Origin-Bildproxy für HTTPS- und Reverse-Proxy-Zugriff
- Senderlogos und Poster funktionieren über eine HTTPS-Domain, wenn das Portal Bilder nur per HTTP anbietet
- signierte Bild-Tickets, Portalbindung und Schutz vor offenen SSRF-Proxys
- fremde private, lokale und reservierte Ziele werden blockiert
- maximal 5 MiB pro Bild, begrenzte Weiterleitungen und erlaubte Rasterbildformate
- sicherer DOM-Renderer ohne ungeprüfte Portalwerte in `innerHTML`
- große Kataloge werden blockweise dargestellt
- zunächst höchstens 72 Karten; weitere Inhalte über **Mehr anzeigen**
- Bilder laden erst in der Nähe des sichtbaren Bereichs
- Schutz vor tausenden gleichzeitigen Bildanfragen
- vollständige `.gitignore`- und `.dockerignore`-Regeln für Konfiguration, Geheimnisse und Logs

## Getesteter Funktionsstand

Die Portal-, Katalog- und Bildproxy-Funktionen wurden auf einer UGREEN-NAS über die lokale Adresse und über eine externe HTTPS-Zapto-Domain geprüft. Kategorien, Kataloge und Portalbilder wurden erfolgreich geladen.

Die Wiedergabefunktionen aus Version 1.0.28 bleiben enthalten:

- dauerhafter Live-TV-TS-Proxy
- stabilere Portalverbindungswechsel
- frische VOD- und Serienlinks bei erforderlichen Neustarts
- korrekte Staffel- und Episodenzuordnung
- Downloads mit passenden Dateinamen
- sauberes Freigeben vorheriger Wiedergabesitzungen

## Unterstützte Plattformen

Das veröffentlichte Image unterstützt:

- Windows mit Docker Desktop (`linux/amd64`)
- Linux mit Docker Engine und Docker Compose (`linux/amd64` oder `linux/arm64`)
- macOS mit Docker Desktop auf Intel (`linux/amd64`)
- macOS mit Docker Desktop auf Apple Silicon (`linux/arm64`)
- UGREEN UGOS Pro auf unterstützten AMD64- oder ARM64-Modellen

Docker wählt aus dem Multi-Arch-Image automatisch die passende Architektur aus.

## Schnellstart mit Docker Hub

Repository klonen oder als ZIP herunterladen, damit die Compose-Datei vorhanden ist:

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose pull
docker compose up -d
```

Danach:

```text
http://localhost:8080
```

Die Standard-Compose-Datei verwendet:

```yaml
image: schrittfisch2000/stalker-client:latest
pull_policy: always
```

Für eine fest angeheftete Version kann der Image-Eintrag beispielsweise auf diesen Tag gesetzt werden:

```yaml
image: schrittfisch2000/stalker-client:v1.0.30
```

## Updates auf Windows, Linux und macOS

Im Projektordner:

```bash
docker compose pull
docker compose up -d
```

Die Konfiguration bleibt erhalten, weil nur dieser Ordner in den Container eingebunden wird:

```yaml
volumes:
  - ./konfiguration:/konfiguration
```

## Installation auf UGREEN über die Weboberfläche

Viele UGREEN-Systeme stellen im Terminal weder `git` noch `curl` oder `wget` bereit. Für die einmalige Einrichtung:

1. Repository auf einem Computer über **Code → Download ZIP** herunterladen.
2. ZIP entpacken.
3. Den Projektordner per SMB auf die NAS kopieren.
4. Einen Ordner `konfiguration` im Projektordner anlegen oder den vorhandenen Ordner behalten.
5. In UGOS **Docker → Projekte/Compose** öffnen.
6. Den Hauptordner `Stalker-Client` als Projektordner auswählen.
7. Diese Compose-Datei aus dem Hauptordner verwenden:

```text
docker-compose-ugreen.yml
```

8. Projekt erstellen und starten.

Die UGREEN-Compose-Datei verwendet ebenfalls:

```yaml
image: schrittfisch2000/stalker-client:latest
pull_policy: always
```

Danach:

```text
http://IP-DER-NAS:8080
```

### Updates auf UGREEN

Nach einer neuen Veröffentlichung musst du keine Programmdateien mehr ersetzen:

1. In UGOS **Docker → Projekte/Compose** öffnen.
2. Das Stalker-Client-Projekt auswählen.
3. **Neu bereitstellen**, **Redeploy** oder **Erneut erstellen** wählen.
4. Keine Volumes und keine Projektdaten löschen.
5. UGOS lädt wegen `pull_policy: always` das aktuelle `latest`-Image und startet den Container neu.
6. Browser vollständig neu laden: macOS `Cmd + Shift + R`, Windows/Linux `Strg + F5`.

Der Ordner `konfiguration` bleibt dabei erhalten.

### Wichtig für UGOS

Für die UGOS-Weboberfläche ausschließlich die root-nahe Datei verwenden:

```text
docker-compose-ugreen.yml
```

Nicht `deploy/ugreen/docker-compose.yml` auswählen. Diese Datei ist für lokale Entwickler-Builds über die Kommandozeile vorgesehen und verwendet einen relativen Build-Kontext.

## Lokaler Entwickler-Build

Wer Änderungen am Quellcode entwickeln und lokal bauen möchte, verwendet eine Compose-Datei unter `deploy/`:

Standard:

```bash
docker compose -f deploy/standard/docker-compose.yml up -d --build
```

UGREEN-kompatibler Entwickler-Build:

```bash
docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```

Normale Installationen sollen dagegen das veröffentlichte Docker-Hub-Image verwenden.

## Veröffentlichungsablauf

1. Änderungen werden in einem Pull Request geprüft.
2. GitHub Actions führt Tests, Compose-Prüfungen und einen Docker-Build aus.
3. Der Release-PR wird nach `main` gemergt.
4. Ein Versions-Tag wie `v1.0.30` wird erstellt.
5. `.github/workflows/docker-publish.yml` baut für `linux/amd64` und `linux/arm64`.
6. Docker Hub erhält:

```text
schrittfisch2000/stalker-client:v1.0.30
schrittfisch2000/stalker-client:latest
```

7. Installationen übernehmen das Update beim nächsten Pull oder Redeploy.

## HTTPS und Portalbilder

Seit Version 1.0.29 stellt der Client Bildadressen als signierte Same-Origin-Anfragen bereit:

```text
/api/image?ticket=...
```

Der Server lädt das Bild kontrolliert und liefert es über dieselbe HTTPS-Domain an den Browser aus.

## Sicherheit

Der Ordner `konfiguration` kann Portaladressen, MAC-Adressen, Benutzerkonten, Signaturschlüssel, Tokens und Logs enthalten. Er darf niemals veröffentlicht werden.

Geschützt werden unter anderem:

```text
konfiguration/
portal-einstellungen.json
portal-zuweisungen.json
benutzer.json
benutzer-freigaben.json
.stalker-geheimnis
stalker-client.log
```

## Port ändern

Standardport: `8080`.

```bash
STALKER_PORT=8180 docker compose up -d
```

In UGOS die Projektvariable setzen:

```text
STALKER_PORT=8180
```

## Diagnose

```bash
docker compose ps
docker compose logs -f --tail=300
```

Bei UGREEN über die Kommandozeile:

```bash
docker compose -f docker-compose-ugreen.yml logs -f --tail=300
```

Vor dem Teilen von Logs Portaladressen, MAC-Adressen, Tokens, Tickets und Zugangsdaten entfernen.

## Qualitätssicherung

GitHub Actions führt bei Pull Requests und Änderungen auf `main` aus:

```text
Secret-Scan
JavaScript-Syntaxprüfung
Python-Unittests
Validierung aller Compose-Dateien
vollständiger Docker-Build
```

Bei Versions-Tags veröffentlicht ein separater Workflow das Multi-Arch-Image auf Docker Hub.

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Downloads und Wiedergabe dürfen nur im Rahmen der Berechtigungen und Nutzungsbedingungen des jeweiligen Anbieters verwendet werden.
