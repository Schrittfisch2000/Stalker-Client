# Automatische Docker-Hub-Updates

## Veröffentlichungsablauf

Neue Versionen werden nach dem Testen über einen Git-Tag veröffentlicht.

Ablauf:

1. Änderungen entwickeln und testen.
2. Versionsnummer erhöhen.
3. Release-Tag erstellen, zum Beispiel `v1.0.30`.
4. GitHub Actions baut automatisch das Docker-Image.
5. Das Image wird nach Docker Hub veröffentlicht:

```text
schrittfisch2000/stalker-client:v1.0.30
schrittfisch2000/stalker-client:latest
```

Unterstützte Architekturen:

```text
linux/amd64
linux/arm64
```

## UGREEN Update

Die UGREEN-Installation verwendet:

```yaml
image: schrittfisch2000/stalker-client:latest
pull_policy: always
```

Bei einem Redeploy prüft UGOS Docker Hub und lädt das aktuelle Image.

Der Ordner `konfiguration` bleibt erhalten:

```yaml
volumes:
  - ./konfiguration:/konfiguration
```

Damit bleiben Portale, Benutzer, Favoriten und Einstellungen bestehen.

## Kein manuelles ZIP-Update mehr

Der normale Ablauf ist:

```text
Neue Version freigeben
        ↓
GitHub Tag
        ↓
Docker Hub Image
        ↓
UGREEN Redeploy
        ↓
Neue Version aktiv
```

## Kontrolle der installierten Version

Nach dem Update sollte die Weboberfläche die neue Versionsnummer anzeigen.
