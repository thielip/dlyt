#!/bin/sh
# Start Cloudflare WARP (userspace SOCKS via wgcf+wireproxy), then the API.
# No NET_ADMIN / TUN required — works on restricted PaaS like Render Free.
set -eu

WARP_DIR="${WARP_DIR:-/tmp/warp}"
SOCKS_ADDR="${WARP_SOCKS_ADDR:-127.0.0.1:1080}"
ENABLE_WARP="${ENABLE_WARP:-true}"
PORT="${PORT:-8000}"

mkdir -p "$WARP_DIR"
cd "$WARP_DIR"

warp_ok=0

start_warp() {
  if [ "$ENABLE_WARP" != "true" ] && [ "$ENABLE_WARP" != "1" ]; then
    echo "[warp] ENABLE_WARP=$ENABLE_WARP — skipping WARP"
    return 1
  fi
  if ! command -v wgcf >/dev/null 2>&1 || ! command -v wireproxy >/dev/null 2>&1; then
    echo "[warp] wgcf/wireproxy missing — skipping WARP"
    return 1
  fi

  if [ ! -f wgcf-account.toml ]; then
    echo "[warp] registering Cloudflare WARP account…"
    # Non-interactive accept of ToS
    wgcf register --accept-tos || {
      echo "[warp] register failed"
      return 1
    }
  fi

  if [ ! -f wgcf-profile.conf ]; then
    echo "[warp] generating WireGuard profile…"
    wgcf generate || {
      echo "[warp] generate failed"
      return 1
    }
  fi

  # wireproxy config: import wgcf profile + local SOCKS5
  cat > wireproxy.conf <<EOF
WGConfig = ${WARP_DIR}/wgcf-profile.conf

[Socks5]
BindAddress = ${SOCKS_ADDR}
EOF

  echo "[warp] starting wireproxy on socks5://${SOCKS_ADDR}"
  wireproxy -c wireproxy.conf >/tmp/wireproxy.log 2>&1 &
  echo $! >/tmp/wireproxy.pid

  # Wait until SOCKS is accepting connections
  i=0
  while [ "$i" -lt 30 ]; do
    if curl -fsS --max-time 3 --socks5-hostname "$SOCKS_ADDR" \
      "https://www.cloudflare.com/cdn-cgi/trace" 2>/dev/null | grep -q "warp="; then
      echo "[warp] ready:"
      curl -fsS --max-time 5 --socks5-hostname "$SOCKS_ADDR" \
        "https://www.cloudflare.com/cdn-cgi/trace" 2>/dev/null | grep -E '^(ip|warp|colo)=' || true
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done

  echo "[warp] SOCKS not ready in time; last log:"
  tail -n 40 /tmp/wireproxy.log 2>/dev/null || true
  return 1
}

if start_warp; then
  warp_ok=1
  export YTDLP_PROXY="socks5://${SOCKS_ADDR}"
  echo "[warp] YTDLP_PROXY=${YTDLP_PROXY}"
else
  unset YTDLP_PROXY || true
  echo "[warp] continuing WITHOUT WARP (YouTube may stay blocked on datacenter IP)"
fi

export WARP_STATUS="$warp_ok"
echo "[api] starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
