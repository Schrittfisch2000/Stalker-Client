FROM python:3.12-slim

LABEL org.opencontainers.image.title="Stalker Client Deutsch" \
      org.opencontainers.image.description="Deutscher Web-Client für kompatible Stalker- und MAG-Portale" \
      org.opencontainers.image.vendor="Schrittfisch2000" \
      org.opencontainers.image.source="https://github.com/Schrittfisch2000/Stalker-Client"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /anwendung

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tzdata \
    && ln -snf /usr/share/zoneinfo/Europe/Berlin /etc/localtime \
    && echo "Europe/Berlin" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system anwendung \
    && adduser --system --ingroup anwendung anwendung

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

USER anwendung
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
