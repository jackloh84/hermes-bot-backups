#!/bin/bash
# Keep Jack's minia2a agent service + cloudflared tunnel alive.
# Restarts them if either is missing, and refreshes the tunnel URL registry.
# Idempotent - safe to run every 5 min.

set -e
SVC_LOG=/tmp/agent_svc.log
CF_LOG=/tmp/cf.log
URL_FILE=/tmp/jack_tunnel_url
PROJ=/home/ubuntu/projects/agent-marketplace-bot
HEALTH_URL_FILE=/home/ubuntu/projects/agent-marketplace-bot/.stack-health.json

stamp() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { echo "[$(stamp)] $*" | tee -a /tmp/agent_keepalive.log; }

check_uvicorn() {
  pgrep -f "jack_agent_service:app" >/dev/null
}

# The named tunnel (api.kachangsia.com) is the canonical, stable URL.
# All Minia2a service registrations MUST point here — quick-tunnel URLs rotate
# on every cloudflared restart, which previously broke registered endpoints.
NAMED_TUNNEL="https://api.kachangsia.com"

check_named_tunnel() {
  curl -sL -m 6 "$NAMED_TUNNEL/" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q '^2'
}

# Quick-tunnel URL (rotates — used as fallback only).
check_tunnel() {
  local url
  url=$(cat "$URL_FILE" 2>/dev/null || echo "")
  if [ -z "$url" ]; then return 1; fi
  curl -sL -m 5 "$url/" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q '^2'
}

# Helper: extract the most recent (last) tunnel URL from the cloudflared log.
# The log may contain URLs from prior restarts; we always want the live one.
latest_tunnel_url() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | tail -1
}

restart_quick_tunnel() {
  log "Restarting quick-tunnel only (named tunnel intact)"
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  sleep 2
  cd "$PROJ"
  nohup cloudflared tunnel --url http://localhost:8088 --no-autoupdate --logfile "$CF_LOG" 2>&1 &
  disown
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    URL=$(latest_tunnel_url)
    if [ -n "$URL" ]; then
      echo "$URL" > "$URL_FILE"
      log "Quick-tunnel back up: $URL"
      return 0
    fi
  done
  log "WARN: quick-tunnel failed to start within 20s (named tunnel still up)"
  return 1
}

restart_stack() {
  log "Restarting full stack"
  pkill -f "jack_agent_service:app" 2>/dev/null || true
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  sleep 2
  cd "$PROJ"
  nohup python3 -m uvicorn jack_agent_service:app --host 0.0.0.0 --port 8088 --no-access-log > "$SVC_LOG" 2>&1 &
  disown
  nohup cloudflared tunnel --url http://localhost:8088 --no-autoupdate --logfile "$CF_LOG" 2>&1 &
  disown
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    URL=$(latest_tunnel_url)
    if [ -n "$URL" ]; then
      echo "$URL" > "$URL_FILE"
      log "Quick-tunnel back up: $URL"
      return 0
    fi
  done
  log "ERROR: quick-tunnel failed to start within 20s"
  return 1
}

# Main
# Primary health check is the NAMED tunnel — if that works, Minia2a services are reachable.
# Only fall back to quick-tunnel logic if the named tunnel is actually down.
LATEST_URL=$(latest_tunnel_url)
if [ -n "$LATEST_URL" ]; then
  echo "$LATEST_URL" > "$URL_FILE"
fi

URL="$NAMED_TUNNEL"
if check_uvicorn && check_named_tunnel; then
  STATUS="healthy"
elif ! check_uvicorn; then
  # uvicorn dead — full restart (named tunnel config still active so will resume)
  restart_stack
  STATUS="restarted-uvicorn"
else
  # uvicorn up, named tunnel down — restart quick-tunnel only
  restart_quick_tunnel || true
  STATUS="restarted-quicktunnel"
fi

# Write health state
cat > "$HEALTH_URL_FILE" <<JSON
{
  "status": "$STATUS",
  "named_tunnel": "$NAMED_TUNNEL",
  "quick_tunnel": "$(cat "$URL_FILE" 2>/dev/null || echo "unknown")",
  "canonical_endpoint": "$NAMED_TUNNEL/",
  "checked_at": "$(stamp)"
}
JSON
