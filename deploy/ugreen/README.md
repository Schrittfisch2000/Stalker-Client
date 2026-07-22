# UGREEN NAS mit UGOS Pro

Diese Anleitung gilt für UGREEN-NAS-Systeme wie die DXP8800 Plus.

## Empfohlen: Installation über die UGOS-Dockeroberfläche

Viele UGOS-Systeme stellen im Terminal weder `git` noch `curl` oder `wget` bereit. Kopiere deshalb den vollständigen Projektordner zunächst von einem Computer auf die NAS, zum Beispiel per SMB.

Der Zielordner muss so aufgebaut sein:

```text
Stalker-Client/
├── Dockerfile
├── docker-compose-ugreen.yml
├── app/
├── deploy/
└── konfiguration/
```

Danach in UGOS:

1. Docker aus dem App Center installieren und öffnen.
2. **Compose** oder **Projekte** auswählen.
3. Den Hauptordner `Stalker-Client` als Projektordner verwenden.
4. Als Compose-Datei die Datei im Hauptordner auswählen:

   ```text
   docker-compose-ugreen.yml
   ```

5. Das Projekt bauen und starten.

Die Weboberfläche ist anschließend erreichbar unter:

```text
http://IP-DER-NAS:8080
```

### Warum nicht `deploy/ugreen/docker-compose.yml` in der UGOS-Oberfläche?

Die Datei unter `deploy/ugreen/` verwendet relative Pfade für den Kommandozeilenbetrieb. Manche UGOS-Versionen kopieren eine ausgewählte Compose-Datei intern in einen anderen Ordner. Dann wird der Build-Kontext falsch aufgelöst und Docker sucht beispielsweise hier nach dem Dockerfile:

```text
/volume2/Dockerfile
```

Typische Fehlermeldung:

```text
unable to prepare context: unable to evaluate symlinks in Dockerfile path:
lstat /volume2/Dockerfile: no such file or directory
```

Für die UGOS-Oberfläche deshalb immer `docker-compose-ugreen.yml` aus dem Projekt-Hauptordner verwenden. Diese Datei nutzt:

```yaml
build:
  context: .
  dockerfile: Dockerfile

volumes:
  - ./konfiguration:/konfiguration
```

## Alternative: Installation über SSH

Nur verwenden, wenn auf der NAS `git` und Docker Compose verfügbar sind:

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose -f docker-compose-ugreen.yml up -d --build
```

## Einstellungen vom Mac übernehmen

Kopiere den kompletten Ordner `konfiguration` aus der Mac-Installation in den Projektordner auf der NAS. Er enthält Portale, Benutzer, Favoriten, Verlauf und die geheime Signaturdatei.

Danach das Compose-Projekt in UGOS neu starten.

> Den Ordner `konfiguration` niemals veröffentlichen. Er kann Portaladressen, MAC-Adressen, Token und Zugangsdaten enthalten.

## Port ändern

Ist Port 8080 belegt, in den Projektvariablen setzen:

```text
STALKER_PORT=8180
```

Danach ist die Anwendung unter `http://IP-DER-NAS:8180` erreichbar.

## Wichtig bei Volumes

Nur der Konfigurationsordner wird eingebunden:

```text
./konfiguration:/konfiguration
```

Keinen zusätzlichen Mount auf `/anwendung` anlegen. Ein solcher Mount überschreibt den Anwendungscode aus dem Image und kann zu folgendem Fehler führen:

```text
PermissionError: [Errno 13] Permission denied: '/anwendung/app/__init__.py'
```

## Aktualisieren ohne Git auf der NAS

1. Auf dem Computer die aktuelle Version herunterladen oder den lokalen Repository-Ordner aktualisieren.
2. Den Ordner `konfiguration` auf der NAS sichern.
3. Den Projektordner auf der NAS durch die neue Version ersetzen.
4. Den gesicherten Ordner `konfiguration` wieder einsetzen.
5. Das Projekt in UGOS mit `docker-compose-ugreen.yml` neu bauen und starten.
