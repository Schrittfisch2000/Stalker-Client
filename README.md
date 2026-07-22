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

Für diesen Stand sind im Repository derzeit keine GitHub-Actions-Workflows eingerichtet. Die Freigabe basiert auf den vorhandenen Regressionstests im Quellcode und dem beschriebenen manuellen Laufzeittest.

## Unterstützte Plattformen

### Standard-Docker

- Windows mit Docker Desktop
- Linux mit Docker Engine und Docker Compose
- macOS mit Docker Desktop, Intel und Apple Silicon

### UGREEN NAS

- UGOS Pro
- DXP8800 Plus und vergleichbare UGREEN-NAS-Systeme

Beide Varianten verwenden dasselbe Dockerfile und dieselbe Anwendung. Für die UGOS-Dockeroberfläche gibt es zusätzlich eine Compose-Datei im Projekt-Hauptordner.

## Schnellstart unter Windows, Linux und macOS

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

Nach einem Frontend-Update den Browser vollständig neu laden:

- Windows/Linux: `Strg + F5`
- macOS: `Cmd + Shift + R`

## Installation auf einer UGREEN-NAS

### Empfohlen: UGOS-Dockeroberfläche ohne Git, curl oder wget

Viele UGREEN-Systeme stellen im Terminal weder `git` noch `curl` oder `wget` bereit. Kopiere deshalb den vollständigen Projektordner von deinem Computer per SMB oder Dateimanager auf die NAS.

Der Ordner auf der NAS muss ungefähr so aussehen:

```text
Stalker-Client/
├── Dockerfile
├── docker-compose.yml
├── docker-compose-ugreen.yml
├── app/
├── deploy/
└── konfiguration/
```

In der UGOS-Dockeroberfläche:

1. Docker aus dem App Center installieren und öffnen.
2. **Compose** oder **Projekte** auswählen.
3. Den Hauptordner `Stalker-Client` als Projektordner verwenden.
4. Als Compose-Datei diese Datei im Hauptordner auswählen:

   ```text
   docker-compose-ugreen.yml
   ```

5. Das Projekt bauen und starten.

Danach ist die Anwendung erreichbar unter:

```text
http://IP-DER-NAS:8080
```

### Wichtig: Nicht die Unterordner-Compose-Datei in UGOS auswählen

Die Datei `deploy/ugreen/docker-compose.yml` verwendet relative Pfade für den Kommandozeilenbetrieb. Manche UGOS-Versionen kopieren die ausgewählte Compose-Datei intern in einen anderen Ordner. Dann wird der Build-Kontext falsch aufgelöst und Docker sucht beispielsweise hier nach dem Dockerfile:

```text
/volume2/Dockerfile
```

Typischer Fehler:

```text
unable to prepare context: unable to evaluate symlinks in Dockerfile path:
lstat /volume2/Dockerfile: no such file or directory
```

Für die UGOS-Oberfläche deshalb immer die Datei `docker-compose-ugreen.yml` aus dem Projekt-Hauptordner verwenden. Sie nutzt bewusst:

```yaml
build:
  context: .
  dockerfile: Dockerfile

volumes:
  - ./konfiguration:/konfiguration
```

### Alternative: Installation über SSH

Nur verwenden, wenn auf der NAS `git` und Docker Compose verfügbar sind:

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose -f docker-compose-ugreen.yml up -d --build
```

### Einstellungen vom Mac übernehmen

Kopiere den kompletten Ordner `konfiguration` aus der Mac-Installation in den Projektordner auf der NAS. Er enthält unter anderem Portale, Benutzer, Favoriten, Wiedergabeverlauf und die geheime Signaturdatei.

Anschließend das Compose-Projekt in UGOS neu bauen oder neu starten.

> Den Ordner `konfiguration` niemals veröffentlichen. Er kann Portaladressen, MAC-Adressen, Token und Zugangsdaten enthalten.

## Aktualisieren

### Standard-Docker mit Git

```bash
cd Stalker-Client
cp -R konfiguration ../stalker-client-konfiguration-backup
docker compose down --remove-orphans
git pull --ff-only
docker compose build --no-cache
docker compose up -d
```

### UGREEN ohne Git auf der NAS

1. Auf dem Computer die aktuelle Version herunterladen oder das lokale Repository aktualisieren.
2. Den NAS-Ordner `konfiguration` sichern.
3. Den Projektordner auf der NAS durch die neue Version ersetzen.
4. Den gesicherten Ordner `konfiguration` wieder einsetzen.
5. In UGOS das Projekt mit `docker-compose-ugreen.yml` neu bauen und starten.

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

- `get_episodes` wird vor breiten Katalogabfragen verwendet.
- Fremde Filme aus ungefilterten Portalantworten werden verworfen.
- Leere Listen wie `series=[]` gelten nicht mehr als Episodennummer.
- Episode, Staffel und übergeordnete Serien-ID werden getrennt übertragen.
- Die portalspezifische Staffel- und Episodenlogik bleibt mit Download-Schaltflächen erhalten.

## Downloads für Filme und Serien

Bei Filmen erscheint auf der Medienkarte eine Schaltfläche **Download**. Bei Serien besitzt jede abspielbare Episode eine eigene Download-Schaltfläche.

- Downloads sind nur für Filme und Serien verfügbar, nicht für Live-TV.
- Video, Audiospuren und vorhandene Untertitel werden ohne Neucodierung übernommen.
- Die Datei wird direkt an den Browser gestreamt und nicht dauerhaft im Container gespeichert.
- Maximal zwei Downloads laufen gleichzeitig.
- Große Dateien können abhängig von Portalgeschwindigkeit und Dateigröße lange dauern.
- Die Funktion umgeht keine Verschlüsselung und keine DRM-Schutzmaßnahmen.

## Projektstruktur

```text
Dockerfile
docker-compose.yml
docker-compose-ugreen.yml
deploy/
├── standard/
│   ├── docker-compose.yml
│   └── README.md
└── ugreen/
    ├── docker-compose.yml
    └── README.md
```

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

Dieser Ordner enthält vertrauliche Daten. Er darf nicht veröffentlicht oder unverändert in öffentliche Fehlerberichte hochgeladen werden.

## Port ändern

Der Standardport ist 8080.

### Standard-Docker

```bash
STALKER_PORT=8180 docker compose up -d --build
```

### UGREEN

In den UGOS-Projektvariablen setzen:

```text
STALKER_PORT=8180
```

Danach ist die Anwendung unter `http://IP-DER-NAS:8180` erreichbar.

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

Bei UGREEN mit der root-nahen Datei jeweils ergänzen:

```bash
docker compose -f docker-compose-ugreen.yml ...
```

## Diagnose

Bei einem Live-Start beziehungsweise Wechsel erscheinen unter anderem folgende Meldungen:

```text
FFmpeg-HLS mit dauerhaftem TS-Proxy gestartet
Dauerhafter TS-Proxy mit Mehrfach-Zeitachsen verbunden
TS-Proxy verwendet den neuesten verfügbaren Keyframe
TS-Proxy mit getrennten Medienuhren gewechselt
```

Bei einem erforderlichen VOD-Neustart erscheint:

```text
Frischen Portal-Link für Medienwiedergabe erstellt
```

Vor dem Teilen eines Logs Portaladressen, MAC-Adressen, Token, Tickets und Zugangsdaten entfernen.

## Fehlerbehebung

### UGREEN sucht `/volume2/Dockerfile`

Falsche Compose-Datei oder falscher Projektordner. In UGOS den Hauptordner `Stalker-Client` auswählen und ausschließlich `docker-compose-ugreen.yml` aus diesem Hauptordner verwenden.

### Port 8080 ist belegt

Einen anderen Port über `STALKER_PORT` verwenden oder den alten Container stoppen.

### Browser zeigt noch eine alte Version

Den Browser mit `Cmd + Shift + R` beziehungsweise `Strg + F5` vollständig neu laden.

### Containerstatus prüfen

```bash
docker compose ps
docker compose logs --tail=100
```

## Wichtig bei Volumes

Nur der Konfigurationsordner darf eingebunden werden:

```text
./konfiguration:/konfiguration
```

Keinen zusätzlichen Mount auf `/anwendung` anlegen. Ein solcher Mount überschreibt den Anwendungscode im Image und kann zu Berechtigungsfehlern führen.

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
- Korrekte Staffel- und Episodenzuordnung bei portalspezifischen Serienantworten
- Download-Erweiterung überschreibt die Seriennavigation nicht mehr
- Root-nahe `docker-compose-ugreen.yml` für die UGOS-Dockeroberfläche
- Dokumentierte Lösung für den Fehler `lstat /volume2/Dockerfile`

### 1.0.27

- Separate Zeitachsenkorrektur für Video, Audio und PCR
- Lese-Watchdog für hängende Portalverbindungen
- Download-Schaltflächen für Filme und einzelne Serienepisoden
- Verlustfreies Remuxen autorisierter Inhalte als MKV

### Frühere Versionen

Frühere Versionen führten unter anderem Browser-Handover, Diagnoseprotokolle, Mehrportal- und Benutzerverwaltung, UGREEN-Unterstützung sowie das gemeinsame Docker-Deployment ein.
