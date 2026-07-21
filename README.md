# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale.

## Funktionen

- Live-TV mit Sendergruppen
- EPG-Ansicht
- Filme und Serien mit Portal-Metadaten
- Integrierter HTML5/HLS-Player
- Portal-URL und MAC-Adresse direkt in der Weboberfläche eintragen
- Persistente Speicherung im Projekt-Hauptordner
- Automatisch erzeugtes internes App-Secret
- Docker- und Docker-Compose-Betrieb

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Start

```bash
docker compose up --build -d
```

Danach `http://localhost:8080` öffnen. Beim ersten Aufruf erscheint automatisch der Dialog für Portal-URL und MAC-Adresse.

Im Projekt-Hauptordner werden automatisch angelegt:

```text
./portal-settings.json
./.stalker-secret
```

`portal-settings.json` enthält Portal-URL und MAC-Adresse. `.stalker-secret` enthält das automatisch erzeugte interne Secret für signierte Stream-Tickets. Beide Dateien werden durch `.gitignore` ausgeschlossen und unter Linux mit Dateirechten `0600` erstellt.

Es ist keine `.env`-Datei erforderlich.

## Optionale Konfiguration

Bei Bedarf können folgende Umgebungsvariablen direkt in `docker-compose.yml` ergänzt werden:

| Variable | Bedeutung | Standard |
|---|---|---|
| `VERIFY_TLS` | TLS-Zertifikate prüfen | `true` |
| `REQUEST_TIMEOUT` | Portal-Timeout in Sekunden | `20` |
| `CONFIG_FILE` | Pfad der Portal-Konfiguration im Container | `/config/portal-settings.json` |
| `SECRET_FILE` | Pfad des generierten App-Secrets im Container | `/config/.stalker-secret` |
| `APP_SECRET` | Optionales festes Secret statt automatischer Erzeugung | automatisch erzeugt |

## Hinweise zur Portal-Kompatibilität

Stalker-Portale unterscheiden sich je nach Anbieter und Middleware-Version. Der Client unterstützt die üblichen `portal.php`-Aufrufe für Handshake, Sender, EPG, VOD, Serien und `create_link`. Bei einem abweichenden Portal können kleine Anpassungen in `app/stalker.py` nötig sein.

## Entwicklung ohne Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
CONFIG_FILE='./portal-settings.json' SECRET_FILE='./.stalker-secret' uvicorn app.main:app --reload --port 8080
```

Anschließend die Zugangsdaten in der Weboberfläche eintragen. Auch hierbei wird das App-Secret automatisch erzeugt.

## Sicherheit

- `portal-settings.json`, `.stalker-secret` und `.env` niemals committen oder weitergeben.
- Den Dienst nicht ungeschützt ins öffentliche Internet stellen.
- Wer Zugriff auf die Weboberfläche hat, kann die gespeicherte Portal-Konfiguration ändern.
- Stream-Tickets sind zeitlich begrenzt und HMAC-signiert.
- Der Backend-Proxy akzeptiert nur HTTP- und HTTPS-URLs, die zuvor vom Portal geliefert wurden.
