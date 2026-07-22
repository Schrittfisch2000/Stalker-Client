# Stalker Client

**Aktuelle Version: 1.0.26 – konsistente Versionsangaben und Deployment-Tags**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Die Anwendung unterstützt Live-TV, Filme, Serien, mehrere Portale, Benutzerkonten, Favoriten und Wiedergabefortschritt.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Unterstützte Plattformen

### Standard-Docker

- Windows mit Docker Desktop
- Linux mit Docker Engine und Docker Compose
- macOS mit Docker Desktop, Intel und Apple Silicon

### UGREEN NAS

- UGOS Pro
- DXP8800 Plus und vergleichbare UGREEN-NAS-Systeme

Beide Varianten verwenden dasselbe Dockerfile und dieselbe Anwendung. Nur die Compose-Dateien und Installationshinweise unterscheiden sich.

## Dauerhafter TS-Proxy für Live-TV

Seit Version 1.0.24 läuft bei Live-TV eine dauerhafte Pipeline. Version 1.0.25 normalisiert zusätzlich die MPEG-TS-Zeitachse beim Wechsel auf einen frischen Portal-Token:

```text
Stalker-Portal
      ↓
Dauerhafter MPEG-TS-Proxy
      ↓
Zeitachsen-Normalisierung und Keyframe-Wechsel
      ↓
Eine laufende FFmpeg-Instanz
      ↓
Eine fortlaufende HLS-Playlist
      ↓
Ein unveränderter Browserplayer
```

Der Proxy öffnet frühzeitig eine zweite Portalverbindung mit einem frischen Token. Die Ersatzverbindung wird bis zu einem zufälligen Zugriffspunkt beziehungsweise Keyframe vorgewärmt. Beim Wechsel werden PTS, DTS und PCR auf die laufende Ausgabezeitachse verschoben, Continuity Counter je PID fortgeführt und die zuletzt bekannten PAT-/PMT-Pakete erneut ausgegeben.

Wichtige Eigenschaften:

- Der Browserplayer wird beim Tokenwechsel nicht ersetzt.
- FFmpeg wird beim normalen Tokenwechsel nicht neu gestartet.
- Die Ersatzverbindung wird vorbereitet, während die alte Verbindung noch Daten liefert.
- MPEG-TS-Daten werden an 188-Byte-Paketgrenzen ausgerichtet.
- Der Wechsel erfolgt bevorzugt an einem Keyframe bzw. Random-Access-Punkt.
- PTS, DTS und PCR werden auf eine fortlaufende Zeitachse verschoben.
- Continuity Counter werden pro PID durchgehend neu vergeben.
- PAT und PMT werden am Umschaltpunkt erneut eingespeist.
- Der bisherige Dual-Player-Handover bleibt deaktiviert.

Kurzzeitig bestehen zwei Portalverbindungen, aber nur eine FFmpeg-Instanz und eine HLS-Sitzung.

## Projektstruktur

```text
Dockerfile
docker-compose.yml
deploy/
├── standard/
│   ├── docker-compose.yml
│   └── README.md
└── ugreen/
    ├── docker-compose.yml
    └── README.md
```

## Installation unter Windows, Linux und macOS

Im Hauptverzeichnis des Projekts:

```bash
docker compose up -d --build
```

Alternativ ausdrücklich mit der Standard-Compose-Datei:

```bash
docker compose -f deploy/standard/docker-compose.yml up -d --build
```

Danach ist die Anwendung erreichbar unter:

```text
http://localhost:8080
```

Weitere Hinweise stehen in `deploy/standard/README.md`.

## Installation auf einer UGREEN DXP8800 Plus

Docker über das UGOS App Center installieren. Danach über SSH:

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```

Danach ist die Anwendung erreichbar unter:

```text
http://IP-DER-NAS:8080
```

Über die UGOS-Dockeroberfläche kann dieselbe Datei verwendet werden:

```text
deploy/ugreen/docker-compose.yml
```

Weitere Hinweise stehen in `deploy/ugreen/README.md`.

## Wichtig bei Volumes

Nur die persistenten Daten werden eingebunden:

```text
konfiguration:/konfiguration
```

Der Projektordner darf nicht nach `/anwendung` gemountet werden. Dadurch würde der Anwendungscode aus dem Image überschrieben. Unter UGOS Pro kann dies zu folgendem Fehler führen:

```text
PermissionError: [Errno 13] Permission denied: '/anwendung/app/__init__.py'
```

## Konfiguration

Die Anwendung erzeugt die benötigten Dateien beim ersten Start im Ordner `konfiguration/`. Dazu gehören unter anderem:

```text
portal-einstellungen.json
portal-zuweisungen.json
benutzer.json
benutzer-freigaben.json
wiedergabeverlauf.json
favoriten.json
fortschritt.json
.stalker-geheimnis
stalker-client.log
```

## Port ändern

Standardmäßig wird Port 8080 verwendet. Über die Umgebungsvariable `STALKER_PORT` kann ein anderer Host-Port gesetzt werden.

Linux und macOS:

```bash
STALKER_PORT=8180 docker compose up -d --build
```

Windows PowerShell:

```powershell
$env:STALKER_PORT="8180"
docker compose up -d --build
```

UGREEN:

```bash
STALKER_PORT=8180 docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```

## Docker-Bedienung

Status:

```bash
docker compose ps
```

Logs:

```bash
docker compose logs -f
```

Neustart:

```bash
docker compose restart
```

Stoppen:

```bash
docker compose down
```

## Aktualisieren

Standard-Docker:

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

UGREEN:

```bash
git pull
docker compose -f deploy/ugreen/docker-compose.yml down
docker compose -f deploy/ugreen/docker-compose.yml build --no-cache
docker compose -f deploy/ugreen/docker-compose.yml up -d
```

Nach einem Frontend-Update den Browser mit `Strg + F5` beziehungsweise `Cmd + Shift + R` vollständig neu laden.

## Diagnose des TS-Proxys

Bei einem erfolgreichen Live-Start erscheinen unter anderem folgende Meldungen:

```text
FFmpeg-HLS mit dauerhaftem TS-Proxy gestartet
Dauerhafter TS-Proxy mit Zeitachsen-Normalisierung verbunden
TS-Proxy auf normalisierter Zeitachse gewechselt
```

Die Wechselmeldung enthält zusätzlich, ob ein Keyframe gefunden wurde und wie viele vorgewärmte TS-Pakete übernommen wurden. Beim Tokenwechsel sollte kein neuer FFmpeg-Prozess gestartet und der Browserplayer nicht ersetzt werden.

## Sicherheit

- Konfigurationsdateien, MAC-Adressen, Portalzugänge und Token nicht veröffentlichen.
- Die Anwendung nicht ungeschützt ins öffentliche Internet stellen.
- Für externen Zugriff einen Reverse Proxy mit HTTPS und zusätzlicher Zugriffskontrolle verwenden.
- Den Ordner `konfiguration` regelmäßig sichern.

## Versionsverlauf

### 1.0.26

- Veraltete 1.0.24-Versions- und Cache-Busting-Einträge im Frontend auf 1.0.26 aktualisiert
- Standard- und UGREEN-Compose-Image-Tags auf 1.0.26 angehoben
- README und sichtbare Versionsanzeige auf den neuen Release-Stand gebracht

### 1.0.25

- PTS-/DTS-Normalisierung beim Wechsel der Portalverbindung
- PCR-Verschiebung auf die fortlaufende Ausgabezeitachse
- Durchgehende MPEG-TS-Continuity-Counter pro PID
- Vorgewärmte Ersatzverbindung mit bevorzugtem Wechsel am Keyframe
- Erneute Ausgabe der zuletzt bekannten PAT- und PMT-Pakete
- Zusätzliche Diagnosewerte für Keyframe-Erkennung und Vorpuffer

### 1.0.24

- Dauerhafter MPEG-TS-Proxy zwischen Stalker-Portal und FFmpeg
- Frühzeitiges Öffnen einer Ersatzverbindung mit frischem Portal-Token
- FFmpeg bleibt während des Tokenwechsels aktiv
- Eine fortlaufende HLS-Sitzung und ein unveränderter Browserplayer
- Ausrichtung eingehender Daten an MPEG-TS-Paketgrenzen
- Neue Zeitstempelbildung über die laufende Systemzeit in FFmpeg
- Dual-Player-Handover im Browser deaktiviert

### 1.0.23

- Ersatzplayer wird vor der Übergabe gezielt am Live-Rand ausgerichtet
- Einstieg ungefähr 0,75 Sekunden hinter dem Ende des verfügbaren Puffers
- Hls.js-Live-Synchronisation für den Ersatzplayer auf einen Segmentabstand reduziert
- Übergabe wird abgebrochen, wenn die Live-Rand-Ausrichtung nicht sicher abgeschlossen werden kann
- Zusätzliche Konsolenprotokolle für Zielposition, übersprungene Zeit und verbleibenden Puffer

### 1.0.22

- Paralleler, ausgeblendeter Ersatzplayer für Live-TV-Handover
- Übergabe erst nach laufender Wiedergabe und mindestens drei Sekunden Browserpuffer
- Aktiver Player bleibt während der kompletten Vorbereitung unangetastet
- Alte Hls.js- und FFmpeg-Sitzung wird erst nach erfolgreicher Übergabe beendet
- Playerdiagnose bindet sich nach einem Playerwechsel automatisch neu

### 1.0.21

- Einstieg neuer Hls.js-Sitzungen näher am Live-Rand
- Weniger sichtbare Wiederholung beim Wechsel zwischen Live-Sitzungen

### 1.0.20

- Vorgewärmte Ersatzsessions mit acht HLS-Segmenten
- Browserverwalteter Live-Handover mit aktiver Freigabe alter Sitzungen
- Verhinderung interner Neustarts beendeter Handover-Sitzungen

### 1.0.19

- System- und Browserdiagnose für Live-TV-Probleme
- Protokollierung von Playerzustand, Puffer und laufenden FFmpeg-Sitzungen

### 1.0.11

- Docker-Build läuft ohne interaktive `debconf`-Frontend-Warnungen
- `pip`-Root-Warnung und Versionshinweis werden im Container-Build unterdrückt
- Gemeinsames Dockerfile bleibt für Standard- und UGREEN-Installation erhalten

### 1.0.10

- Proaktive Erneuerung des Live-TV-Portal-Tokens
- Fortlaufende HLS-Segmentnummern bei FFmpeg-Neustarts
- Verbesserte Safari-Stabilität bei länger laufenden Live-Streams

### 1.0.9

- Gemeinsames Docker-Image für alle Plattformen
- Standard-Compose für Windows, Linux und macOS
- Separate UGREEN-Compose-Datei für UGOS Pro
- Plattformbezogene Installationsanleitungen
- Konfigurierbarer Host-Port über `STALKER_PORT`
- Vermeidung von Host-Mounts auf `/anwendung`

### 1.0.8

- Unterstützung für UGREEN NAS und UGOS Pro
- UGREEN-kompatibler Entrypoint für persistente Dateirechte
- Behebung des Berechtigungsfehlers beim Laden von `/anwendung/app/__init__.py`
