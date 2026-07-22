# UGREEN NAS mit UGOS Pro

Diese Variante ist für UGREEN-NAS-Systeme wie die DXP8800 Plus vorgesehen.

## Installation über SSH

```bash
cd /volume1/docker
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```

Danach ist die Weboberfläche unter `http://IP-DER-NAS:8080` erreichbar.

## Installation über die UGOS-Dockeroberfläche

1. Docker aus dem UGOS App Center installieren.
2. Den Bereich **Compose** oder **Projekte** öffnen.
3. Den Projektordner `Stalker-Client` auswählen.
4. Als Compose-Datei `deploy/ugreen/docker-compose.yml` verwenden.
5. Das Projekt bauen und starten.

## Wichtig bei Volumes

Nur der Konfigurationsordner wird eingebunden:

```text
../../konfiguration:/konfiguration
```

Der Projektordner darf nicht nach `/anwendung` gemountet werden. Ein solcher Mount überschreibt den Anwendungscode aus dem Image und kann unter UGOS Pro zu diesem Fehler führen:

```text
PermissionError: [Errno 13] Permission denied: '/anwendung/app/__init__.py'
```

Der Entrypoint korrigiert beim Start die Rechte des persistenten Konfigurationsordners und startet die Anwendung anschließend als unprivilegierter Benutzer.

## Aktualisieren

```bash
cd /volume1/docker/Stalker-Client
git pull
docker compose -f deploy/ugreen/docker-compose.yml down
docker compose -f deploy/ugreen/docker-compose.yml up -d --build
```
