FROM python:3.12-slim

LABEL org.opencontainers.image.title="Stalker Client Deutsch" \
      org.opencontainers.image.description="Deutscher Web-Client für kompatible Stalker- und MAG-Portale" \
      org.opencontainers.image.vendor="Schrittfisch2000" \
      org.opencontainers.image.source="https://github.com/Schrittfisch2000/Stalker-Client"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    TZ=Europe/Berlin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MAIN_DIRECTORY=/konfiguration

WORKDIR /anwendung

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg tzdata gosu \
    && ln -snf /usr/share/zoneinfo/Europe/Berlin /etc/localtime \
    && echo "Europe/Berlin" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system anwendung \
    && adduser --system --ingroup anwendung anwendung \
    && mkdir -p /konfiguration \
    && chown anwendung:anwendung /konfiguration

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=anwendung:anwendung app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod -R a+rX /anwendung/app \
    && chmod 0755 /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]