# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale mit moderner Streaming-Oberfläche, integrierter Wiedergabe und lokaler Konfiguration.

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Aktuelle Funktionen

- Live-TV mit Sendergruppen und EPG
- Filme und Serien mit Portal-Metadaten
- integrierter HTML5-/HLS-Player
- dunkles, kachelbasiertes Streaming-Layout
- Hero-Bereich, Suche und Navigation für Live-TV, Filme und Serien
- responsive Darstellung für Desktop, Tablet und Smartphone
- Portal-URL und MAC-Adresse direkt in der Weboberfläche verwalten
- persistente Speicherung der Konfiguration im Projekt-Hauptordner
- automatisch erzeugtes internes App-Secret
- rotierende Logdateien im Projekt-Hauptordner
- Docker- und Docker-Compose-Betrieb ohne `.env`-Datei

## Installation

### Windows

1. Docker Desktop installieren und starten.
2. Repository herunterladen oder klonen.
3. PowerShell im Projektordner öffnen:

```powershell
docker compose up --build -d
```

### Linux

Docker Engine und das Docker-Compose-Plugin installieren. Danach im Projektordner:

```bash
docker compose up --build -d
```

Falls Docker nur mit `sudo` funktioniert:

```bash
sudo docker compose up --build -d
```

### macOS

Docker Desktop installieren und starten. Danach im Projektordner:

```bash
docker compose up --build -d
```

Anschließend unter allen Systemen öffnen:

```text
http://localhost:8080
```

Beim ersten Aufruf Portal-URL und MAC-Adresse eingeben. Eine `.env`-Datei ist nicht erforderlich.

## Container verwalten

Status anzeigen:

```bash
docker compose ps
```

Konsolenausgabe anzeigen:

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

Nach Änderungen neu bauen:

```bash
docker compose up --build -d
```

## Automatisch erzeugte Dateien

Der Projekt-Hauptordner wird in Docker unter `/config` eingebunden. Dort werden automatisch folgende Dateien erzeugt:

```text
portal-settings.json
.stalker-secret
stalker-client.log
stalker-client.log.1
stalker-client.log.2
stalker-client.log.3
stalker-client.log.4
stalker-client.log.5
```

### `portal-settings.json`

Enthält die über die Weboberfläche eingetragene Portal-URL und MAC-Adresse.

### `.stalker-secret`

Enthält ein automatisch erzeugtes internes Secret. Es wird zum Signieren zeitlich begrenzter Stream-Tickets verwendet.

Ein manuell gesetztes `APP_SECRET` ist nicht erforderlich.

### `stalker-client.log`

Enthält Anwendungsereignisse mit Zeitstempel und Log-Level. Protokolliert werden unter anderem:

- Start und Stop der Anwendung
- erfolgreiche und fehlgeschlagene Portalverbindungen
- Änderungen der Portal-Konfiguration
- Wiedergabestarts
- Portal-, API- und Streamfehler
- unerwartete Fehler mit Stacktrace

Sensible Informationen werden reduziert protokolliert. Die vollständige MAC-Adresse und vollständige Stream-URLs sollen nicht im Log erscheinen.

## Log-Rotation

Die aktive Logdatei ist:

```text
stalker-client.log
```

Sobald sie 10 MB erreicht, wird sie automatisch rotiert. Es werden maximal fünf Sicherungsdateien aufbewahrt:

```text
stalker-client.log.1
...
stalker-client.log.5
```

Ältere Sicherungsdateien werden automatisch entfernt.

Die Logdateien werden zusätzlich in der Docker-Konsole ausgegeben und können mit folgendem Befehl verfolgt werden:

```bash
docker compose logs -f
```

## Weboberfläche

Die Oberfläche ist als moderner Streaming-Client aufgebaut und verwendet ein dunkles, filmisches Design.

Enthalten sind:

- Navigation für Live-TV, Filme und Serien
- großer Hero-Bereich
- kachelbasierte Sender-, Film- und Serienansicht
- Kategorienavigation
- Titelsuche
- Statusanzeige der Portalverbindung
- Dialog zur Verwaltung der Zugangsdaten
- integrierter Videoplayer
- EPG-Anzeige für Live-TV
- Episodenauswahl für Serien

Das Design orientiert sich an bekannten Streaming-Plattformen, verwendet jedoch eigenes Stalker-Client-Branding und keine Markenbestandteile fremder Anbieter.

## Optionale Konfiguration

Bei Bedarf können Umgebungsvariablen direkt unter `environment` in `docker-compose.yml` ergänzt werden.

| Variable | Bedeutung | Standard |
|---|---|---|
| `HOST_PORT` | Port auf dem Docker-Host | `8080` |
| `PORT` | Interner HTTP-Port | `8080` |
| `VERIFY_TLS` | TLS-Zertifikate des Portals prüfen | `true` |
| `REQUEST_TIMEOUT` | Portal-Timeout in Sekunden | `20` |
| `CONFIG_FILE` | Pfad der Portal-Konfiguration im Container | `/config/portal-settings.json` |
| `SECRET_FILE` | Pfad des automatisch erzeugten Secrets | `/config/.stalker-secret` |
| `LOG_FILE` | Pfad der Logdatei im Container | `/config/stalker-client.log` |
| `APP_SECRET` | Optionales festes Secret statt automatischer Erzeugung | automatisch erzeugt |

Beispiel für einen anderen Host-Port:

```yaml
services:
  stalker-client:
    ports:
      - "9090:8080"
```

Die Weboberfläche ist danach unter `http://localhost:9090` erreichbar.

## Entwicklung ohne Docker

Virtuelle Umgebung erstellen und Abhängigkeiten installieren:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Unter Windows PowerShell wird die Umgebung so aktiviert:

```powershell
.venv\Scripts\Activate.ps1
```

Anwendung im Projektordner starten:

```bash
CONFIG_FILE='./portal-settings.json' \
SECRET_FILE='./.stalker-secret' \
LOG_FILE='./stalker-client.log' \
uvicorn app.main:app --reload --port 8080
```

Anschließend `http://localhost:8080` öffnen und die Portal-Zugangsdaten in der Weboberfläche eintragen.

## Portal-Kompatibilität

Stalker-Portale unterscheiden sich je nach Anbieter und Middleware-Version. Der Client unterstützt die üblichen `portal.php`-Aufrufe für:

- Handshake
- Profil
- Sender und Kategorien
- EPG
- Video-on-Demand
- Serien und Episoden
- `create_link`

Bei abweichenden Middleware-Versionen oder angepassten Portalen können Änderungen in `app/stalker.py` erforderlich sein.

## Fehlerbehebung

### Portal verbindet sich nicht

- Portal-URL auf Tippfehler prüfen
- MAC-Adresse auf das korrekte Format prüfen
- sicherstellen, dass das Portal vom Docker-Host erreichbar ist
- `stalker-client.log` prüfen
- Docker-Ausgabe mit `docker compose logs -f` verfolgen

### Änderungen werden nicht übernommen

```bash
docker compose down
docker compose up --build -d
```

### Gespeicherte Zugangsdaten zurücksetzen

Container stoppen und die lokale Konfigurationsdatei entfernen:

```bash
docker compose down
rm portal-settings.json
docker compose up -d
```

Beim nächsten Aufruf erscheint der Einrichtungsdialog erneut.

### Internes Secret zurücksetzen

```bash
docker compose down
rm .stalker-secret
docker compose up -d
```

Beim nächsten Start wird ein neues Secret erzeugt. Bereits ausgestellte Stream-Tickets werden dadurch ungültig.

## Sicherheit

- `portal-settings.json` und `.stalker-secret` niemals committen oder weitergeben.
- Logdateien vor dem Weitergeben auf sensible Angaben prüfen.
- Den Dienst nicht ungeschützt im öffentlichen Internet bereitstellen.
- Wer Zugriff auf die Weboberfläche hat, kann die Portal-Konfiguration ändern.
- Stream-Tickets sind zeitlich begrenzt und HMAC-signiert.
- Der Backend-Proxy akzeptiert nur HTTP- und HTTPS-URLs.
- Die lokalen Konfigurations- und Secret-Dateien werden unter Linux nach Möglichkeit mit Dateirechten `0600` erstellt.
- Lokale Konfigurations-, Secret- und Logdateien werden durch `.gitignore` ausgeschlossen.

## Rechtlicher Hinweis

Dieses Projekt stellt nur einen technischen Client bereit. Es enthält keine Sender, Filme, Serien, Zugangsdaten oder Abonnements. Für die Nutzung eines Portals und der darüber verfügbaren Inhalte ist ausschließlich der Benutzer verantwortlich.
