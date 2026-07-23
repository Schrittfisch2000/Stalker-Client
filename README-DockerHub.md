# Docker Hub Quick Start

Use the official image:

```yaml
image: schrittfisch2000/stalker-client:latest
pull_policy: always
```

Keep configuration persistent:

```yaml
volumes:
  - ./konfiguration:/konfiguration
```
