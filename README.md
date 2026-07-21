# Stalker Client

Dockerisierter Web-Client für kompatible Stalker-/MAG-Portale.

## Funktionen

- Live-TV mit Sendergruppen
- EPG-Ansicht
- Filme und Serien mit Portal-Metadaten
- Integrierter HTML5/HLS-Player
- Zugang über Portal-URL und MAC-Adresse
- Zugangsdaten ausschließlich über Umgebungsvariablen
- Docker- und Docker-Compose-Betrieb

> Verwende den Client nur mit einem Portal und Inhalten, für die du eine gültige Berechtigung besitzt.

## Start

```bash
cp .env.example .env
# PORTAL_URL und PORTAL_MAC in .env eintragen
docker compose up --build -d
```

Danach: http://localhost:8080

## Konfiguration

| Variable | Bedeutung | Standard |
|---|---|---|
| `PORTAL_URL` | Basis-URL des Portals, z. B. `http://example.com/stalker_portal/c/` | erforderlich |
| `PORTAL_MAC` | MAC-Adresse im Format `00:1A:79:XX:XX:XX` | erforderlich |
| `APP_SECRET` | Signiert interne Stream-Tickets | erforderlich |
| `PORT` | Interner HTTP-Port | `8080` |
| `VERIFY_TLS` | TLS-Zertifikate prüfen | `true` |
| `REQUEST_TIMEOUT` | Portal-Timeout in Sekunden | `20` |

## Hinweise zur Portal-Kompatibilität

Stalker-Portale unterscheiden sich je nach Anbieter und Middleware-Version. Der Client unterstützt die üblichen `portal.php`-Aufrufe für Handshake, Sender, EPG, VOD, Serien und `create_link`. Bei einem abweichenden Portal können kleine Anpassungen in `app/stalker.py` nötig sein.

## Entwicklung

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export PORTAL_URL='http://portal.example/c/'
export PORTAL_MAC='00:1A:79:00:00:00'
export APP_SECRET='change-me'
uvicorn app.main:app --reload --port 8080
```

## Sicherheit

- Keine Portal-Zugangsdaten committen.
- Den Dienst nicht ungeschützt ins öffentliche Internet stellen.
- Stream-Tickets sind zeitlich begrenzt und HMAC-signiert.
- Der Backend-Proxy akzeptiert nur URLs, die zuvor vom konfigurierten Portal geliefert wurden.
