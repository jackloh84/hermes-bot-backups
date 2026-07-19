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

check_tunnel() {
  local url
  url=$(cat "$URL_FILE" 2>/dev/null || echo "")
  if [ -z "$url" ]; then return 1; fi
  curl -sL -m 5 "$url/" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q '^2'
}

restart_stack() {
  log "Restarting stack"
  pkill -f "jack_agent_service:app" 2>/dev/null || true
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  sleep 2
  cd "$PROJ"
  nohup uvicorn jack_agent_service:app --host 0.0.0.0 --port 8088 --no-access-log > "$SVC_LOG" 2>&1 &
  disown
  nohup cloudflared tunnel --url http://localhost:8088 --no-autoupdate --logfile "$CF_LOG" 2>&1 &
  disown
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | head -1)
    if [ -n "$URL" ]; then
      echo "$URL" > "$URL_FILE"
      log "Tunnel back up: $URL"
      return 0
    fi
  done
  log "ERROR: tunnel failed to start within 20s"
  return 1
}

# Main
if check_uvicorn && check_tunnel; then
  URL=$(cat "$URL_FILE")
  STATUS="healthy"
else
  restart_stack
  STATUS="restarted"
  URL=$(cat "$URL_FILE" 2>/dev/null || echo "unknown")
fi

# Write health state
cat > "$HEALTH_URL_FILE" <<JSON
{
  "status": "$STATUS",
  "tunnel_url": "$URL",
  "checked_at": "$(stamp)"
}
JSON
