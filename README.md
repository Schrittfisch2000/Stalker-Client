# Stalker Client

**Aktuelle Version: 1.0.27 – stabilere Live-TV-Wechsel und Downloads für Filme und Serien**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Die Anwendung unterstützt Live-TV, Filme, Serien, mehrere Portale, Benutzerkonten, Favoriten, Wiedergabefortschritt und Downloads von Filmen und Episoden.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt. Lade nur Inhalte herunter, deren Speicherung durch deinen Anbieter und die geltenden Nutzungsbedingungen erlaubt ist.

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

Seit Version 1.0.24 läuft bei Live-TV eine dauerhafte Pipeline. Version 1.0.25 führte die MPEG-TS-Zeitachsen-Normalisierung ein. Version 1.0.27 richtet beim Wechsel Video-PTS/DTS, Audio-PTS und PCR getrennt auf die laufenden Ausgabeuhren aus und führt den vorgewärmten Ersatzstrom bis zum aktuellen Bild nach:

```text
Stalker-Portal
      ↓
Dauerhafter MPEG-TS-Proxy
      ↓
Getrennte Video-, Audio- und PCR-Zeitachsen
      ↓
Keyframe-Wechsel am aktuellen Live-Bild
      ↓
Eine laufende FFmpeg-Instanz
      ↓
Eine fortlaufende HLS-Playlist
      ↓
Ein unveränderter Browserplayer
```

Der Proxy öffnet frühzeitig eine zweite Portalverbindung mit einem frischen Token. Die Ersatzverbindung wird bis zu einem zufälligen Zugriffspunkt beziehungsweise Keyframe vorgewärmt. Vor der Übergabe wird sie bis zum aktuellen Bild der bisherigen Verbindung nachgeführt. Beim Wechsel werden die Zeitstempel je Medien-PID und die PCR-Uhr getrennt verschoben, Continuity Counter je PID fortgeführt und die zuletzt bekannten PAT-/PMT-Pakete erneut ausgegeben.

Wichtige Eigenschaften:

- Der Browserplayer wird beim Tokenwechsel nicht ersetzt.
- FFmpeg wird beim normalen Tokenwechsel nicht neu gestartet.
- Die Ersatzverbindung wird vorbereitet, während die alte Verbindung noch Daten liefert.
- Der Ersatzstrom wird vor der Übergabe bis zum aktuellen Video-PTS nachgeführt.
- MPEG-TS-Daten werden an 188-Byte-Paketgrenzen ausgerichtet.
- Der Wechsel erfolgt bevorzugt an einem Keyframe beziehungsweise Random-Access-Punkt.
- Video-PTS/DTS, Audio-PTS und PCR werden unabhängig auf fortlaufende Zeitachsen verschoben.
- Ein größerer Paketkontext überträgt Audio- und PCR-Anker zuverlässig mit dem Keyframe.
- Continuity Counter werden pro PID durchgehend neu vergeben.
- PAT und PMT werden am Umschaltpunkt erneut eingespeist.
- Ein Lese-Watchdog erneuert eine hängende Portalverbindung.
- Der bisherige Dual-Player-Handover bleibt deaktiviert.

Kurzzeitig bestehen zwei Portalverbindungen, aber nur eine FFmpeg-Instanz und eine HLS-Sitzung.

## Downloads für Filme und Serien

Bei Filmen erscheint auf der Medienkarte eine Schaltfläche **Download**. Bei Serien besitzt jede abspielbare Episode eine eigene Download-Schaltfläche.

Der Ablauf:

```text
Portalstream
      ↓
FFmpeg-Remux ohne Neucodierung
      ↓
Matroska-Datei (.mkv)
      ↓
Browser-Download
```

- Downloads sind nur für `vod` und `series` verfügbar, nicht für Live-TV.
- Video, Audiospuren und vorhandene Untertitel werden ohne Qualitätsverlust in einen MKV-Container übernommen.
- Die Datei wird direkt an den Browser gestreamt und nicht dauerhaft im Container oder im Konfigurationsordner gespeichert.
- Maximal zwei Downloads laufen gleichzeitig, damit NAS und Portal nicht unkontrolliert belastet werden.
- Die normalen Benutzer- und Portalzuweisungen gelten auch für Downloads.
- Die Funktion umgeht keine Verschlüsselung und keine DRM-Schutzmaßnahmen.

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
Dauerhafter TS-Proxy mit Mehrfach-Zeitachsen verbunden
TS-Proxy-Ersatzstrom bis zum aktuellen Bild nachgeführt
TS-Proxy mit getrennten Medienuhren gewechselt
```

Die Wechselmeldung enthält die Anzahl der übernommenen TS-Pakete sowie Video-, Audio- und PCR-Anker. Beim Tokenwechsel sollte kein neuer FFmpeg-Prozess gestartet und der Browserplayer nicht ersetzt werden.

## Sicherheit

- Konfigurationsdateien, MAC-Adressen, Portalzugänge und Token nicht veröffentlichen.
- Die Anwendung nicht ungeschützt ins öffentliche Internet stellen.
- Für externen Zugriff einen Reverse Proxy mit HTTPS und zusätzlicher Zugriffskontrolle verwenden.
- Den Ordner `konfiguration` regelmäßig sichern.
- Downloads ausschließlich für Inhalte verwenden, deren lokale Speicherung erlaubt ist.

## Versionsverlauf

### 1.0.27

- Ersatzverbindung wird vor dem Wechsel bis zum aktuellen Live-Bild nachgeführt
- Separate Zeitachsenkorrektur für Video, Audio und PCR
- Größerer Wechselkontext für zuverlässige Audio- und PCR-Anker
- Lese-Watchdog für hängende Portalverbindungen
- Sauberes Beenden von TS-Proxy, FFmpeg und HLS-Ordnern
- Download-Schaltflächen für Filme und einzelne Serienepisoden
- Verlustfreies Remuxen autorisierter Inhalte als MKV ohne Neucodierung
- Durchgängige Versionsanzeige und Docker-Tags für 1.0.27

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
