# Stalker Client

**Aktuelle Version: 1.0.29 – sicherer HTTPS-Bildproxy und schneller große Kataloge**

Dockerisierter, deutschsprachiger Web-Client für kompatible Stalker-/MAG-Portale. Unterstützt Live-TV, Filme, Serien, mehrere Portale, Benutzerkonten, Favoriten, Wiedergabefortschritt und Downloads.

> Verwende den Client ausschließlich mit Portalen und Inhalten, für die du eine gültige Berechtigung besitzt.

## Neu in Version 1.0.29

- sicherer Same-Origin-Bildproxy für HTTPS- und Reverse-Proxy-Zugriff
- Senderlogos und Poster funktionieren auch über eine HTTPS-Domain, wenn das Portal Bilder nur per HTTP anbietet
- signierte Bild-Tickets, Portalbindung und Schutz vor offenen SSRF-Proxys
- fremde private, lokale und reservierte Ziele werden blockiert
- maximal 5 MiB pro Bild, begrenzte Weiterleitungen und erlaubte Rasterbildformate
- sicherer DOM-Renderer ohne ungeprüfte Portalwerte in `innerHTML`
- große Kataloge werden blockweise dargestellt
- zunächst höchstens 72 Karten; weitere Inhalte über **Mehr anzeigen**
- Bilder laden erst in der Nähe des sichtbaren Bereichs
- Schutz vor tausenden gleichzeitigen Bildanfragen
- vollständige `.gitignore`- und `.dockerignore`-Regeln für Konfiguration, Geheimnisse und Logs
- GitHub Actions prüft Secrets, JavaScript-Syntax, Unittests, alle Compose-Dateien und den Docker-Build

## Getesteter Stand

Version 1.0.29 wurde nach den Änderungen auf einer UGREEN-NAS über die lokale Adresse und über eine externe HTTPS-Zapto-Domain geprüft. Kategorien, Kataloge und Portalbilder wurden erfolgreich geladen.

Die Wiedergabefunktionen aus Version 1.0.28 bleiben enthalten:

- dauerhafter Live-TV-TS-Proxy
- stabilere Portalverbindungswechsel
- frische VOD- und Serienlinks bei erforderlichen Neustarts
- korrekte Staffel- und Episodenzuordnung
- Downloads mit passenden Dateinamen
- sauberes Freigeben vorheriger Wiedergabesitzungen

## Unterstützte Plattformen

- Windows mit Docker Desktop
- Linux mit Docker Engine und Docker Compose
- macOS mit Docker Desktop
- UGREEN UGOS Pro

## Schnellstart mit Docker

```bash
git clone https://github.com/Schrittfisch2000/Stalker-Client.git
cd Stalker-Client
mkdir -p konfiguration
docker compose up -d --build
```

Danach:

```text
http://localhost:8080
```

## Installation auf UGREEN über die Weboberfläche

Viele UGREEN-Systeme stellen im Terminal weder `git` noch `curl` oder `wget` bereit.

1. Repository auf dem Computer über **Code → Download ZIP** herunterladen.
2. ZIP entpacken.
3. Den Projektordner per SMB auf die NAS kopieren.
4. Den bestehenden Ordner `konfiguration` bei Updates behalten.
5. In UGOS **Docker → Projekte/Compose** öffnen.
6. Den Hauptordner `Stalker-Client` als Projektordner auswählen.
7. Diese Compose-Datei aus dem Hauptordner verwenden:

```text
docker-compose-ugreen.yml
```

8. Projekt bauen und starten.

Danach:

```text
http://IP-DER-NAS:8080
```

### Wichtig für UGOS

Nicht `deploy/ugreen/docker-compose.yml` in der Weboberfläche auswählen. Manche UGOS-Versionen verschieben die Compose-Datei intern und lösen `../..` dann falsch auf. Der typische Fehler lautet:

```text
lstat /volume2/Dockerfile: no such file or directory
```

Die root-nahe `docker-compose-ugreen.yml` verwendet korrekt:

```yaml
build:
  context: .
  dockerfile: Dockerfile

volumes:
  - ./konfiguration:/konfiguration
```

## Update auf UGREEN ohne Terminal

1. Aktuelles ZIP auf dem Computer herunterladen und entpacken.
2. UGREEN-Projekt stoppen.
3. Alle Programmdateien im NAS-Projektordner ersetzen.
4. Den Ordner `konfiguration` nicht löschen oder überschreiben.
5. Projekt mit `docker-compose-ugreen.yml` neu bauen und starten.
6. Browser vollständig neu laden: macOS `Cmd + Shift + R`, Windows/Linux `Strg + F5`.

## HTTPS und Portalbilder

Über eine HTTPS-Domain lädt der Browser unsichere HTTP-Portalbilder nicht direkt. Version 1.0.29 stellt deshalb Bildadressen als signierte Same-Origin-Anfragen bereit:

```text
/api/image?ticket=...
```

Der Server lädt das Bild kontrolliert und liefert es über dieselbe HTTPS-Domain an den Browser aus.

## Sicherheit

Der Ordner `konfiguration` kann Portaladressen, MAC-Adressen, Benutzerkonten, Signaturschlüssel, Tokens und Logs enthalten. Er darf niemals veröffentlicht werden.

Geschützt werden unter anderem:

```text
konfiguration/
portal-einstellungen.json
portal-zuweisungen.json
benutzer.json
benutzer-freigaben.json
.stalker-geheimnis
stalker-client.log
```

## Port ändern

Standardport: `8080`.

```bash
STALKER_PORT=8180 docker compose up -d --build
```

In UGOS die Projektvariable setzen:

```text
STALKER_PORT=8180
```

## Diagnose

```bash
docker compose ps
docker compose logs -f --tail=300
```

Bei UGREEN über die Kommandozeile:

```bash
docker compose -f docker-compose-ugreen.yml logs -f --tail=300
```

Vor dem Teilen von Logs Portaladressen, MAC-Adressen, Tokens, Tickets und Zugangsdaten entfernen.

## Qualitätssicherung

GitHub Actions führt bei Pull Requests und Änderungen auf `main` aus:

```text
Secret-Scan
JavaScript-Syntaxprüfung
Python-Unittests
Validierung aller Compose-Dateien
vollständiger Docker-Build
```

## Lizenz und Nutzung

Die Anwendung umgeht keine Verschlüsselung oder DRM-Schutzmaßnahmen. Downloads und Wiedergabe dürfen nur im Rahmen der Berechtigungen und Nutzungsbedingungen des jeweiligen Anbieters verwendet werden.
