# Stalker Client

**Aktuelle Version: 1.0.7**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Die Anwendung bündelt Live-TV, Filme und Serien in einer modernen Weboberfläche und unterstützt mehrere Portale, Benutzerkonten, individuelle Freigaben, Favoriten und Wiedergabefortschritt.

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
- Kennzeichnung bereits gesehener Inhalte
- Persönlicher Wiedergabeverlauf
- Suche nach Sendern und Titeln

### Benutzer und Berechtigungen

- Anmeldung mit Benutzerkonten
- Administrator- und Benutzerrollen
- Benutzerverwaltung über die Weboberfläche
- Individuelle Kategorienfreigaben für Live-TV, Filme und Serien
- Individuelle Portalzuweisungen
- Keine Inhalte oder Kategorien ohne zugewiesenes Portal
- Serverseitige Zugriffskontrolle für API- und Stream-Endpunkte

### Portale

- Mehrere Stalker-/MAG-Portale verwalten
- Portalname, URL und MAC-Adresse konfigurieren
- Portale aktivieren oder deaktivieren
- Standardportal festlegen
- Portal pro Benutzer auswählen
- Bestehende Einzelportal-Konfiguration wird automatisch übernommen

### Persönliche Funktionen

- Favoriten pro Benutzer
- Wiedergabefortschritt pro Benutzer
- Weiterschauen pro Benutzer
- Verlauf pro Benutzer
- Daten bleiben voneinander getrennt

### Weboberfläche

- Responsive Darstellung für Desktop, Tablet und Smartphone
- Kompakte mobile Navigation
- Mobile Kategorieauswahl als Dropdown
- Kleinere Senderlogos und Coverraster auf Mobilgeräten
- Touch-optimierte Bedienung
- Unterstützung für iPhone-Safe-Areas und Querformat
- Sichtbare, fortlaufende Versionsnummer

## Installation

### Voraussetzungen

- Docker Desktop oder Docker Engine
- Docker Compose
- Zugriff auf ein kompatibles Stalker-/MAG-Portal

### Mit Git herunterladen

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
```

Alternativ kann das Projekt als ZIP heruntergeladen werden:

[Projekt als ZIP herunterladen](https://github.com/Schrittfisch2000/Stalker-Client/archive/refs/heads/main.zip)

### Erstellen und starten

```bash
docker compose build --no-cache
docker compose up -d
```

Danach die Weboberfläche öffnen:

```text
http://localhost:8080
```

Beim ersten Start werden die erforderlichen lokalen Dateien automatisch erzeugt.

## Aktualisieren

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

Danach die Weboberfläche vollständig neu laden. Auf Mobilgeräten kann es nötig sein, den Browser vollständig zu schließen und erneut zu öffnen.

Die aktive Version wird unten rechts in der Weboberfläche angezeigt und ist zusätzlich über folgenden Endpunkt abrufbar:

```text
GET /api/version
```

## Erste Einrichtung

1. Weboberfläche öffnen.
2. Mit dem Administratorkonto anmelden.
3. Administration öffnen.
4. Unter **Portal** mindestens ein Portal mit URL und MAC-Adresse anlegen.
5. Ein Standardportal festlegen.
6. Benutzern die gewünschten Portale zuweisen.
7. Unter den Benutzerfreigaben die erlaubten Kategorien auswählen.

Wird einem normalen Benutzer kein Portal zugewiesen, werden für diesen Benutzer keine Kategorien, Sender, Filme oder Serien geladen.

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

Die Anwendung legt ihre persistenten Dateien direkt im Projektordner ab. Fehlende Dateien werden beim Start automatisch mit sinnvollen Standardwerten erzeugt.

```text
portal-einstellungen.json
portal-zuweisungen.json
benutzer.json
benutzer-freigaben.json
wiedergabeverlauf.json
favoriten.json
fortschritt.json
sitzungen.json
.stalker-secret
stalker-client.log
```

Je nach älterem Installationsstand können noch frühere Dateinamen vorhanden sein. Bestehende Konfigurationen werden soweit möglich übernommen.

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
| `sitzungen.json` | Sitzungsdaten |
| `.stalker-secret` | Lokales App-Geheimnis |
| `stalker-client.log` | Anwendungsprotokoll |

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

Unterstützte Medientypen:

```text
itv
vod
series
```

### Favoriten und Fortschritt

```text
GET    /api/favorites
PUT    /api/favorites
DELETE /api/favorites/{type}/{id}

GET    /api/progress
PUT    /api/progress
DELETE /api/progress/{type}/{id}

GET /api/history
```

Geschützte Endpunkte setzen eine gültige Anmeldung und die erforderlichen Benutzerfreigaben voraus.

## Streaming-Technik

Portalstreams werden bei Bedarf durch FFmpeg in Safari-kompatibles HLS umgewandelt. Dabei verwendet die Anwendung kurze Segmente für einen schnelleren Start und erzeugt browserkompatible H.264-/AAC-Ausgaben.

Bei kurzlebigen Portal-Wiedergabelinks kann die Anwendung automatisch einen neuen Link anfordern und die laufende HLS-Sitzung fortsetzen. Die genaue Stabilität hängt trotzdem vom Portal, der Netzwerkverbindung, dem Quellformat und der verfügbaren Rechenleistung des Docker-Hosts ab.

## Docker-Bezeichnungen

| Bestandteil | Bezeichnung |
|---|---|
| Compose-Projekt | `stalker-client-deutsch` |
| Dienst | `stalker-client` |
| Image | `stalker-client-deutsch:lokal` |
| Container | `stalker-client-deutsch` |
| Hostname | `stalker-client-deutsch` |
| Zeitzone | `Europe/Berlin` |

Docker-Schlüssel wie `services`, `build`, `ports`, `volumes` und `healthcheck` sind fest vorgegeben und dürfen nicht übersetzt werden.

## Sicherheit

- Portaldateien, Benutzerdateien und App-Geheimnisse nicht veröffentlichen oder committen.
- Die Anwendung nicht ohne zusätzliche Absicherung direkt ins öffentliche Internet stellen.
- Für externen Zugriff einen Reverse Proxy mit HTTPS und geeigneter Zugriffskontrolle verwenden.
- Protokolldateien vor dem Weitergeben auf Portal-URLs, MAC-Adressen, Token und andere sensible Angaben prüfen.
- Regelmäßig Sicherungskopien der persistenten JSON-Dateien erstellen.

## Versionsverlauf

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

## Geplante Weiterentwicklung

- Erweiterter Adminbereich mit Statistiken und Systemstatus
- Benutzerprofile und Profilbilder
- Altersfreigaben und PIN-Schutz
- Benutzergruppen
- Backup und Wiederherstellung
- Mehrsprachigkeit und verschiedene Designs
- Zusammenführung mehrerer Portale in eine gemeinsame Mediathek
- Einheitliche Suche über mehrere Portale

## Fehlerdiagnose

Bei Problemen zuerst die laufenden Logs prüfen:

```bash
docker compose logs -f
```

Hilfreich sind insbesondere Meldungen zu:

- `FFmpeg-HLS gestartet`
- `HLS-Link mit frischem Portal-Token erneuert`
- HTTP-Statuscodes des Portals
- `403 Forbidden` bei fehlenden Benutzerfreigaben
- `502 Bad Gateway` bei nicht erreichbaren oder abgebrochenen Portalstreams

Bitte beim Teilen von Logs sämtliche Zugangsdaten, MAC-Adressen, Portaladressen und Wiedergabetokens unkenntlich machen.
