# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale.

## Funktionen

- Live-TV mit Sendergruppen
- EPG-Ansicht
- Filme und Serien mit Portal-Metadaten
- Integrierter HTML5/HLS-Player
- Portal-URL und MAC-Adresse direkt in der Weboberfläche eintragen
- Persistente Speicherung in `portal-settings.json` im Projekt-Hauptordner
- Docker- und Docker-Compose-Betrieb

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Start

```bash
cp .env.example .env
# APP_SECRET in .env durch einen langen zufälligen Wert ersetzen
docker compose up --build -d
```

Danach `http://localhost:8080` öffnen. Beim ersten Aufruf erscheint automatisch der Dialog für Portal-URL und MAC-Adresse.

Die Weboberfläche speichert die Zugangsdaten auf dem Docker-Host unter:

```text
./portal-settings.json
```

Die Datei wird durch `.gitignore` vom Repository ausgeschlossen. Unter Linux wird sie mit Dateirechten `0600` erstellt.

## Konfiguration

| Variable | Bedeutung | Standard |
|---|---|---|
| `APP_SECRET` | Signiert interne Stream-Tickets | erforderlich, mindestens 16 Zeichen |
| `HOST_PORT` | Port auf dem Docker-Host | `8080` |
| `PORT` | Interner HTTP-Port | `8080` |
| `VERIFY_TLS` | TLS-Zertifikate prüfen | `true` |
| `REQUEST_TIMEOUT` | Portal-Timeout in Sekunden | `20` |
| `CONFIG_FILE` | Pfad der gespeicherten Portal-Konfiguration im Container | `/config/portal-settings.json` |

`PORTAL_URL` und `PORTAL_MAC` müssen nicht mehr in `.env` stehen. Sie werden über **Zugangsdaten** in der Weboberfläche verwaltet.

## Hinweise zur Portal-Kompatibilität

Stalker-Portale unterscheiden sich je nach Anbieter und Middleware-Version. Der Client unterstützt die üblichen `portal.php`-Aufrufe für Handshake, Sender, EPG, VOD, Serien und `create_link`. Bei einem abweichenden Portal können kleine Anpassungen in `app/stalker.py` nötig sein.

## Entwicklung ohne Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export APP_SECRET='change-this-to-a-long-random-value'
export CONFIG_FILE='./portal-settings.json'
uvicorn app.main:app --reload --port 8080
```

Anschließend die Zugangsdaten in der Weboberfläche eintragen.

## Sicherheit

- `portal-settings.json` und `.env` niemals committen oder weitergeben.
- Den Dienst nicht ungeschützt ins öffentliche Internet stellen.
- Wer Zugriff auf die Weboberfläche hat, kann die gespeicherte Portal-Konfiguration ändern.
- Stream-Tickets sind zeitlich begrenzt und HMAC-signiert.
- Der Backend-Proxy akzeptiert nur HTTP- und HTTPS-URLs, die zuvor vom Portal geliefert wurden.
