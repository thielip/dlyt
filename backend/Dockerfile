# syntax=docker/dockerfile:1

FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMP_DIR=/tmp/dlyt \
    WARP_DIR=/tmp/warp \
    ENABLE_WARP=true \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

ARG WGCF_VERSION=2.2.29
ARG WIREPROXY_VERSION=1.0.9

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && set -eux; \
      arch="$(dpkg --print-architecture)"; \
      case "$arch" in \
        amd64) wgcf_arch="amd64"; wireproxy_arch="amd64" ;; \
        arm64) wgcf_arch="arm64"; wireproxy_arch="arm64" ;; \
        *) echo "Unsupported arch: $arch" >&2; exit 1 ;; \
      esac; \
      curl -fL "https://github.com/ViRb3/wgcf/releases/download/v${WGCF_VERSION}/wgcf_${WGCF_VERSION}_linux_${wgcf_arch}" \
        -o /usr/local/bin/wgcf; \
      chmod +x /usr/local/bin/wgcf; \
      curl -fL "https://github.com/pufferffish/wireproxy/releases/download/v${WIREPROXY_VERSION}/wireproxy_linux_${wireproxy_arch}.tar.gz" \
        -o /tmp/wireproxy.tar.gz; \
      tar -xzf /tmp/wireproxy.tar.gz -C /tmp; \
      find /tmp -type f -name wireproxy -exec mv {} /usr/local/bin/wireproxy \; ; \
      chmod +x /usr/local/bin/wireproxy; \
      rm -rf /tmp/wireproxy.tar.gz /tmp/wireproxy* \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/dlyt /tmp/warp

COPY --from=deps /install /install

WORKDIR /app
COPY app ./app
COPY scripts/start.sh /app/scripts/start.sh
RUN chmod +x /app/scripts/start.sh

EXPOSE 8000

# Render injects $PORT. start.sh brings up WARP SOCKS then uvicorn.
CMD ["/app/scripts/start.sh"]
