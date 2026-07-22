# Stalker Client

**Aktuelle Version: 1.0.28 – stabilere Medienwechsel und korrekte Serienepisoden**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Die Anwendung unterstützt Live-TV, Filme, Serien, mehrere Portale, Benutzerkonten, Favoriten, Wiedergabefortschritt und Downloads von Filmen und Episoden.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt. Lade nur Inhalte herunter, deren Speicherung durch deinen Anbieter und die geltenden Nutzungsbedingungen erlaubt ist.

## Status von Version 1.0.28

Version 1.0.28 wurde manuell auf einem Mac mit Apple Silicon, Docker Desktop und Firefox getestet.

Geprüft wurden:

- Live-TV über mehrere automatische Portalverbindungswechsel
- Wechsel von Live-TV zu Filmwiedergabe
- mehrere Filmstarts nacheinander
- Auswahl verschiedener Staffeln und Episoden
- korrekte Zuordnung der ausgewählten Episode zum Portalstream
- Start eines Episoden-Downloads mit richtigem Dateinamen
- sauberes Beenden von HLS-, FFmpeg- und Portal-Sitzungen

Der vollständige Download einer großen Episode wurde im manuellen Test aus Zeitgründen abgebrochen. Start, HTTP-Antwort und Dateiname waren korrekt; ein vollständiger Langzeit-Download wurde damit nicht abschließend verifiziert.

## Unterstützte Plattformen

### Standard-Docker

- Windows mit Docker Desktop
- Linux mit Docker Engine und Docker Compose
- macOS mit Docker Desktop, Intel und Apple Silicon

### UGREEN NAS

- UGOS Pro
- DXP8800 Plus und vergleichbare UGREEN-NAS-Systeme

Beide Varianten verwenden dasselbe Dockerfile und dieselbe Anwendung. Nur die Compose-Dateien und Installationshinweise unterscheiden sich.

## Schnellstart

### Neue Installation

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose up -d --build
```

Danach ist die Anwendung erreichbar unter:

```text
http://localhost:8080
```

### Vorhandene Installation aktualisieren

Die Konfiguration liegt im Ordner `konfiguration/` und bleibt beim normalen Aktualisieren erhalten. Eine zusätzliche Sicherung vor größeren Updates ist trotzdem sinnvoll.

```bash
cd Stalker-Client
cp -R konfiguration ../stalker-client-konfiguration-backup
docker compose down --remove-orphans
git pull --ff-only
docker compose build --no-cache
docker compose up -d
```

Nach einem Frontend-Update den Browser vollständig neu laden:

- Firefox, Chrome und Edge unter Windows/Linux: `Strg + F5`
- Firefox, Chrome und Safari unter macOS: `Cmd + Shift + R`

Version prüfen:

```bash
curl -s http://localhost:8080/api/version
```

## Live-TV-Pipeline

```text
Stalker-Portal
      ↓
Dauerhafter MPEG-TS-Proxy
      ↓
Getrennte Video-, Audio- und PCR-Zeitachsen
      ↓
Keyframe-Wechsel mit aktuellem Ersatzpuffer
      ↓
Eine laufende FFmpeg-Instanz
      ↓
Eine fortlaufende HLS-Playlist
      ↓
Ein unveränderter Browserplayer
```

Der Proxy öffnet frühzeitig eine zweite Portalverbindung mit einem frischen Token. Beim Wechsel werden Video-PTS/DTS, Audio-PTS und PCR unabhängig auf die laufenden Ausgabeuhren ausgerichtet. Version 1.0.28 verwendet bei einer nicht vollständig möglichen Nachführung den neuesten vollständig verfügbaren Keyframe, statt auf den älteren ursprünglichen Ersatzpuffer zurückzufallen.

Wichtige Eigenschaften:

- Der Browserplayer wird beim Tokenwechsel nicht ersetzt.
- FFmpeg wird beim normalen Tokenwechsel nicht neu gestartet.
- MPEG-TS-Daten werden an 188-Byte-Paketgrenzen ausgerichtet.
- Der Wechsel erfolgt an einem Keyframe beziehungsweise Random-Access-Punkt.
- Video-, Audio- und PCR-Zeitachsen werden getrennt fortgeführt.
- Continuity Counter werden pro PID durchgehend neu vergeben.
- PAT und PMT werden am Umschaltpunkt erneut eingespeist.
- Ein Lese-Watchdog erneuert hängende Portalverbindungen.
- Beim Wechsel wird der aktuellste vollständige Ersatz-Keyframe bevorzugt.

## Wiedergabe von Filmen und Serien

Vor dem Start eines neuen Titels beendet der Browser die vorherige HLS- beziehungsweise Portal-Sitzung. Das ist besonders bei Portalen wichtig, die pro MAC-Adresse nur eine gleichzeitige Streamverbindung zulassen.

Falls ein zeitlich begrenzter VOD-Link neu geöffnet werden muss, erzeugt der Server über das ursprüngliche Portal-Kommando einen frischen Link. Dadurch wird ein bereits verbrauchter oder abgelaufener Link nicht in einer schnellen FFmpeg-Neustartschleife wiederverwendet.

Bei Serien gilt:

- Die spezifische Portalaktion `get_episodes` wird vor breiten Katalogabfragen verwendet.
- Fremde Filme aus ungefilterten Portalantworten werden verworfen.
- Leere Listen wie `series=[]` gelten nicht mehr als Episodennummer.
- Episode, Staffel und übergeordnete Serien-ID werden beim Erzeugen des Streamlinks getrennt übertragen.
- Die portalspezifische Staffel- und Episodenlogik bleibt auch mit Download-Schaltflächen erhalten.

## Downloads für Filme und Serien

Bei Filmen erscheint auf der Medienkarte eine Schaltfläche **Download**. Bei Serien besitzt jede abspielbare Episode eine eigene Download-Schaltfläche.

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
- Video, Audiospuren und vorhandene Untertitel werden ohne Qualitätsverlust übernommen.
- Die Datei wird direkt an den Browser gestreamt und nicht dauerhaft im Container gespeichert.
- Maximal zwei Downloads laufen gleichzeitig.
- Benutzer-, Portal- und Kategorienfreigaben gelten auch für Downloads.
- Die Funktion umgeht keine Verschlüsselung und keine DRM-Schutzmaßnahmen.
- Große Dateien können abhängig von Portalgeschwindigkeit, Dateigröße und Internetverbindung lange dauern.

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

Alternativ mit der Standard-Compose-Datei:

```bash
docker compose -f deploy/standard/docker-compose.yml up -d --build
```

## Installation auf einer UGREEN-NAS

Docker über das UGOS App Center installieren. Danach über SSH:

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```

Danach ist die Weboberfläche erreichbar unter:

```text
http://IP-DER-NAS:8080
```

Über die UGOS-Dockeroberfläche kann dieselbe Compose-Datei verwendet werden:

```text
deploy/ugreen/docker-compose.yml
```

## Wichtig bei Volumes

Nur der persistente Konfigurationsordner wird eingebunden:

```text
konfiguration:/konfiguration
```

Der Projektordner darf nicht nach `/anwendung` gemountet werden. Dadurch würde der Anwendungscode aus dem Image überschrieben und es kann zu Berechtigungsfehlern kommen.

## Konfiguration

Beim ersten Start werden im Ordner `konfiguration/` unter anderem folgende Dateien erzeugt:

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

Dieser Ordner enthält vertrauliche Daten. Er darf nicht veröffentlicht oder in öffentliche Fehlerberichte hochgeladen werden.

## Port ändern

Der Standardport ist 8080. Ein anderer Host-Port kann über `STALKER_PORT` gesetzt werden.

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

```bash
# Status
docker compose ps

# Logs
docker compose logs -f --tail=300

# Neustart
docker compose restart

# Stoppen
docker compose down

# Vollständig neu bauen
docker compose down --remove-orphans
docker compose build --no-cache
docker compose up -d
```

## Diagnose

Bei einem Live-Start beziehungsweise Wechsel erscheinen unter anderem folgende Meldungen:

```text
FFmpeg-HLS mit dauerhaftem TS-Proxy gestartet
Dauerhafter TS-Proxy mit Mehrfach-Zeitachsen verbunden
TS-Proxy verwendet den neuesten verfügbaren Keyframe
TS-Proxy mit getrennten Medienuhren gewechselt
```

Beim Wechsel von Live-TV zu einem Film oder einer Episode sollte außerdem die vorherige HLS-Session sauber beendet werden. Bei einem erforderlichen VOD-Neustart erscheint:

```text
Frischen Portal-Link für Medienwiedergabe erstellt
```

Aktuelle Containerlogs in eine Datei schreiben:

```bash
docker compose logs --no-color --since 30m > stalker-client-current.log
```

Vor dem Teilen eines Logs Portaladressen, MAC-Adressen, Token, Tickets und Zugangsdaten entfernen.

## Fehlerbehebung

### Docker läuft nicht

Docker Desktop starten und prüfen:

```bash
open -a Docker
docker info
```

### Port 8080 ist belegt

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Danach entweder den alten Container stoppen oder einen anderen Port über `STALKER_PORT` verwenden.

### Browser zeigt noch eine alte Version

```bash
curl -s http://localhost:8080/api/version
```

Meldet die API die aktuelle Version, den Browser mit `Cmd + Shift + R` beziehungsweise `Strg + F5` neu laden.

### Containerstatus prüfen

```bash
docker compose ps
docker compose logs --tail=100
```

## Sicherheit

- Konfigurationsdateien, MAC-Adressen, Portalzugänge und Token nicht veröffentlichen.
- Die Anwendung nicht ungeschützt ins öffentliche Internet stellen.
- Für externen Zugriff einen Reverse Proxy mit HTTPS und zusätzlicher Zugriffskontrolle verwenden.
- Den Ordner `konfiguration` regelmäßig sichern.
- Downloads ausschließlich für Inhalte verwenden, deren lokale Speicherung erlaubt ist.

## Versionsverlauf

### 1.0.28

- Vorherige Portal- und HLS-Sitzung wird vor einer neuen Wiedergabe sofort freigegeben
- Zeitlich begrenzte VOD- und Serienlinks werden bei einem Neustart frisch erzeugt
- HTTP-462-Neustartschleifen durch wiederverwendete Portal-Links werden verhindert
- Neuester vollständiger Keyframe wird bei unvollständiger Live-Nachführung verwendet
- Spezifische Episodenabfrage wird vor breiten Katalogabfragen ausgeführt
- Fremde Filme aus fehlerhaften Episodenantworten werden verworfen
- Leere `series`-Listen werden nicht mehr als Episodennummer übernommen
- Episodenparameter werden beim `create_link` in der spezifischsten Form zuerst gesendet
- Download-Erweiterung überschreibt die Seriennavigation nicht mehr
- Durchgängige Versionsanzeige und Docker-Tags für 1.0.28
- Manueller Laufzeittest unter macOS, Docker Desktop und Firefox

### 1.0.27

- Separate Zeitachsenkorrektur für Video, Audio und PCR
- Größerer Wechselkontext für Audio- und PCR-Anker
- Lese-Watchdog für hängende Portalverbindungen
- Sauberes Beenden von TS-Proxy, FFmpeg und HLS-Ordnern
- Download-Schaltflächen für Filme und einzelne Serienepisoden
- Verlustfreies Remuxen autorisierter Inhalte als MKV

### 1.0.26

- Konsistente Versionsangaben, Frontend-Cache-Parameter und Deployment-Tags

### 1.0.25

- PTS-/DTS- und PCR-Normalisierung beim Wechsel der Portalverbindung
- Durchgehende MPEG-TS-Continuity-Counter pro PID
- Vorgewärmte Ersatzverbindung mit Keyframe-Wechsel
- Erneute Ausgabe der zuletzt bekannten PAT- und PMT-Pakete

### 1.0.24

- Dauerhafter MPEG-TS-Proxy zwischen Stalker-Portal und FFmpeg
- Frühzeitiges Öffnen einer Ersatzverbindung mit frischem Portal-Token
- FFmpeg bleibt während des Tokenwechsels aktiv
- Eine fortlaufende HLS-Sitzung und ein unveränderter Browserplayer

### Frühere Versionen

Frühere Versionen führten unter anderem Browser-Handover, Diagnoseprotokolle, Mehrportal- und Benutzerverwaltung, UGREEN-Unterstützung sowie das gemeinsame Docker-Deployment ein.
