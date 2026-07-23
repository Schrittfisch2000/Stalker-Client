# Docker Hub Updates

## Standard deployment

All supported platforms use the same Docker image:

```
schrittfisch2000/stalker-client:latest
```

Supported platforms:

- UGREEN / NAS
- Linux Docker Engine
- Windows Docker Desktop
- macOS Docker Desktop

## Release flow

1. Changes are tested.
2. Version is increased.
3. A Git tag `vX.Y.Z` is created.
4. GitHub Actions builds multi-architecture images.
5. Docker Hub receives:

```
schrittfisch2000/stalker-client:vX.Y.Z
schrittfisch2000/stalker-client:latest
```

6. Devices update by redeploying the Compose project.

The configuration directory remains persistent:

```
./konfiguration:/konfiguration
```
