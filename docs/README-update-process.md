# Update-Prozess

## Entwickler

- Code ändern
- testen
- Version freigeben

## Veröffentlichung

Ein Release-Tag startet den Docker-Hub-Build.

## UGREEN

Die NAS verwendet das Docker-Hub-Image und lädt beim Redeploy die aktuelle Version.

Die Konfiguration liegt getrennt im Volume `konfiguration` und bleibt erhalten.
