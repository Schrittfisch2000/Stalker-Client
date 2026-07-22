# Stalker Client

**Aktuelle Version: 1.0.8 – UGREEN-Unterstützung**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Die Anwendung bündelt Live-TV, Filme und Serien in einer modernen Weboberfläche und unterstützt mehrere Portale, Benutzerkonten, individuelle Freigaben, Favoriten und Wiedergabefortschritt.

Diese Version ist gezielt für den Betrieb auf einer **UGREEN NAS mit UGOS Pro**, darunter die **DXP8800 Plus**, vorbereitet.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Funktionen

### Medien und Wiedergabe

- Live-TV mit EPG
- Filme und Serien mit Episodenauswahl
- Integrierter HTML5-/HLS-Player
- Safari- und iOS-kompatible HLS-Aufbereitung über FFmpeg
- Automatische Erneuerung kurzlebiger Portal-Wiedergabetokens
- Wiedergabefortschritt für Filme und Serienepisoden
- Ansicht **Weiterschauen**
- Persönlicher Wiedergabeverlauf
- Suche nach Sendern und Titeln

### Benutzer und Berechtigungen

- Anmeldung mit Benutzerkonten
- Administrator- und Benutzerrollen
- Benutzerverwaltung über die Weboberfläche
- Individuelle Kategorienfreigaben
- Individuelle Portalzuweisungen
- Serverseitige Zugriffskontrolle für API- und Stream-Endpunkte

### Portale

- Mehrere Stalker-/MAG-Portale verwalten
- Portalname, URL und MAC-Adresse konfigurieren
- Portale aktivieren oder deaktivieren
- Standardportal festlegen
- Portal pro Benutzer auswählen

### Weboberfläche

- Responsive Darstellung für Desktop, Tablet und Smartphone
- Kompakte mobile Navigation
- Mobile Kategorieauswahl als Dropdown
- Kleinere Senderlogos und Coverraster auf Mobilgeräten
- Touch-optimierte Bedienung
- Unterstützung für iPhone-Safe-Areas und Querformat
- Sichtbare Versionsnummer

## UGREEN-Unterstützung

Version 1.0.8 behebt typische Berechtigungsprobleme unter UGOS Pro.

Der Anwendungscode bleibt ausschließlich im Docker-Image unter:

```text
/anwendung
```

Nur die persistenten Daten werden eingebunden:

```text
./konfiguration:/konfiguration
```

Beim Containerstart korrigiert ein Entrypoint die Rechte im Konfigurationsordner und startet die Anwendung anschließend als unprivilegierter Benutzer. Dadurch wird insbesondere dieser Fehler vermieden:

```text
PermissionError: [Errno 13] Permission denied: '/anwendung/app/__init__.py'
```

## Installation auf einer UGREEN DXP8800 Plus

### Voraussetzungen

- UGREEN NAS mit UGOS Pro
- Docker aus dem UGOS App Center
- Netzwerkzugriff auf die NAS
- Zugriff auf ein kompatibles Stalker-/MAG-Portal

### 1. Docker installieren

1. UGOS Pro öffnen.
2. **App Center** öffnen.
3. **Docker** installieren und starten.

### 2. Projekt herunterladen

Über SSH:

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
```

Alternativ kann das Projekt als ZIP heruntergeladen und in einen Ordner wie diesen entpackt werden:

```text
/volume1/docker/Stalker-Client
```

### 3. Konfigurationsordner anlegen

```bash
mkdir -p konfiguration
```

Die Anwendung erzeugt die benötigten Dateien beim ersten Start automatisch.

### 4. Image erstellen und Container starten

```bash
docker compose build --no-cache
docker compose up -d
```

### 5. Weboberfläche öffnen

```text
http://IP-DER-UGREEN-NAS:8080
```

Beispiel:

```text
http://192.168.1.50:8080
```

### Installation über die UGOS-Dockeroberfläche

1. Docker in UGOS öffnen.
2. Den Bereich **Compose** beziehungsweise **Projekte** öffnen.
3. Den Ordner `Stalker-Client` auswählen.
4. Die vorhandene `docker-compose.yml` verwenden.
5. Projekt erstellen und starten.
6. Port `8080` im Browser öffnen.

Wichtig: Binde nicht den gesamten Projektordner nach `/anwendung` ein. Verwende nur den vorhandenen Mount für `/konfiguration`.

## Aktualisieren

```bash
cd /volume1/docker/Stalker-Client
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

Danach die Weboberfläche vollständig neu laden.

## Docker-Bedienung

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

Vollständig neu bauen:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Persistente Dateien

Alle persistenten Dateien liegen unter:

```text
konfiguration/
```

Dort werden unter anderem angelegt:

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

### Bedeutung der Dateien

| Datei | Inhalt |
|---|---|
| `portal-einstellungen.json` | Portale, Standardportal und Portalstatus |
| `portal-zuweisungen.json` | Portalzuweisungen pro Benutzer |
| `benutzer.json` | Benutzerkonten und Rollen |
| `benutzer-freigaben.json` | Kategorienfreigaben pro Benutzer |
| `wiedergabeverlauf.json` | Zuletzt wiedergegebene Inhalte |
| `favoriten.json` | Favoriten pro Benutzer |
| `fortschritt.json` | Wiedergabepositionen und Gesehen-Status |
| `.stalker-geheimnis` | Lokales App-Geheimnis |
| `stalker-client.log` | Anwendungsprotokoll |

## Backup auf UGREEN

Für ein Backup reicht es aus, den Ordner `konfiguration` zu sichern:

```bash
tar -czf stalker-client-backup.tar.gz konfiguration
```

Wiederherstellung:

```bash
docker compose down
tar -xzf stalker-client-backup.tar.gz
docker compose up -d
```

## Fehlerdiagnose auf UGREEN

### Container startet immer wieder neu

Logs anzeigen:

```bash
docker compose logs --tail=200
```

Bei einem Berechtigungsfehler zuerst vollständig neu bauen:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

Prüfen, ob versehentlich `/anwendung` als Volume eingebunden wurde:

```bash
docker inspect stalker-client-deutsch
```

Erlaubt ist nur der persistente Mount:

```text
/konfiguration
```

### Konfigurationsordner nicht beschreibbar

```bash
mkdir -p konfiguration
chmod 755 konfiguration
docker compose restart
```

Der Container korrigiert die Besitzerrechte beim nächsten Start automatisch.

### Port 8080 bereits belegt

In der `docker-compose.yml` kann der linke Port geändert werden:

```yaml
ports:
  - "8180:8080"
```

Danach ist die Anwendung unter folgendem Port erreichbar:

```text
http://IP-DER-UGREEN-NAS:8180
```

## API-Übersicht

### Status und Version

```text
GET /health
GET /api/version
GET /api/status
```

### Portale

```text
GET    /api/portals
POST   /api/portals
PUT    /api/portals/{portal_id}
DELETE /api/portals/{portal_id}
PUT    /api/portals/{portal_id}/default
POST   /api/portals/select
GET    /api/users/{username}/portals
PUT    /api/users/{username}/portals
```

### Medien

```text
GET  /api/categories/{media_type}
GET  /api/content/{media_type}
GET  /api/epg
GET  /api/episodes/{series_id}
POST /api/play
```

### Favoriten und Fortschritt

```text
GET    /api/favorites
PUT    /api/favorites
DELETE /api/favorites/{type}/{id}
GET    /api/progress
PUT    /api/progress
DELETE /api/progress/{type}/{id}
GET    /api/history
```

## Streaming-Technik

Portalstreams werden bei Bedarf durch FFmpeg in Safari-kompatibles HLS umgewandelt. Die Anwendung verwendet kurze Segmente für einen schnelleren Start und erzeugt browserkompatible H.264-/AAC-Ausgaben.

Bei kurzlebigen Portal-Wiedergabelinks kann automatisch ein neuer Link angefordert und die laufende HLS-Sitzung fortgesetzt werden.

## Docker-Bezeichnungen

| Bestandteil | Bezeichnung |
|---|---|
| Compose-Projekt | `stalker-client-deutsch` |
| Dienst | `stalker-client` |
| Image | `stalker-client-deutsch:1.0.8-ugreen` |
| Container | `stalker-client-deutsch` |
| Hostname | `stalker-client-deutsch` |
| Persistente Daten | `/konfiguration` |
| Zeitzone | `Europe/Berlin` |

## Sicherheit

- Portaldateien, Benutzerdateien und App-Geheimnisse nicht veröffentlichen oder committen.
- Die Anwendung nicht ungeschützt direkt ins öffentliche Internet stellen.
- Für externen Zugriff einen Reverse Proxy mit HTTPS und zusätzlicher Zugriffskontrolle verwenden.
- Protokolldateien vor dem Weitergeben auf Portal-URLs, MAC-Adressen und Token prüfen.
- Regelmäßig Sicherungskopien des Ordners `konfiguration` erstellen.

## Versionsverlauf

### 1.0.8

- Gezielte Unterstützung für UGREEN NAS und UGOS Pro
- UGREEN-kompatibler Entrypoint für persistente Dateirechte
- Anwendungscode wird nicht mehr über einen Host-Mount eingebunden
- Persistente Daten liegen gebündelt im Ordner `konfiguration`
- Anwendung läuft nach der Rechtekorrektur als unprivilegierter Benutzer
- Behebung von `PermissionError` beim Laden von `/anwendung/app/__init__.py`

### 1.0.7

- Mobile Kategorien als kompakte Auswahl
- Kleinere Senderlogos
- Kompaktere Film- und Seriencover
- Drei Cover-Spalten auf Smartphones

### 1.0.6

- Schnellerer Wiedergabestart
- Kürzere HLS-Segmente
- Optimierung für Live-TV, Filme und Serien

### 1.0.5

- Stabilere Safari-HLS-Zeitleiste
- Größerer Live-Puffer
- Verbesserte Streamfortsetzung

### 1.0.4

- Automatische Erneuerung abgelaufener Portal-Wiedergabetokens
- Fortsetzung von HLS-Sitzungen nach einem Portalabbruch

### 1.0.3

- Kompaktere mobile Oberfläche

### 1.0.2

- Grundlegende Smartphone- und Tablet-Unterstützung

### 1.0.1

- Sperre aller Medienzugriffe ohne Portalzuweisung
- Einführung der sichtbaren App-Version

## Rechtlicher Hinweis

Dieses Projekt stellt ausschließlich einen Client bereit. Es enthält keine Sender, Filme, Serien, Zugangsdaten oder Portalabonnements.
