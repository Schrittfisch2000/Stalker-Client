# Standard-Docker: Windows, Linux und macOS

Diese Variante ist für Docker Desktop unter Windows und macOS sowie für Docker Engine unter Linux vorgesehen.

## Start

Im Hauptverzeichnis des Projekts:

```bash
docker compose up -d --build
```

Alternativ mit der Compose-Datei dieses Ordners:

```bash
docker compose -f deploy/standard/docker-compose.yml up -d --build
```

Die Weboberfläche ist anschließend unter `http://localhost:8080` erreichbar.

## Anderen Port verwenden

Linux/macOS:

```bash
STALKER_PORT=8180 docker compose up -d --build
```

PowerShell:

```powershell
$env:STALKER_PORT="8180"
docker compose up -d --build
```

## Persistente Daten

Die Daten werden im Projektordner unter `konfiguration/` gespeichert. Der Anwendungscode bleibt ausschließlich im Docker-Image; `/anwendung` darf nicht als Host-Volume eingebunden werden.
