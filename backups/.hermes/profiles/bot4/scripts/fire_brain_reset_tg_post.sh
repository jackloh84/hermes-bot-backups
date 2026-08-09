#!/usr/bin/env bash
# fire_brain_reset_tg_post.sh — fires the staged Brain Reset promo to @jacklohai
# Idempotent: skips if a TG @jacklohai post was sent in the last 48h.

set -u
STATE_DIR="/home/ubuntu/.hermes/profiles/bot4/state"
LAST_POST_FILE="$STATE_DIR/telegram_last_post.txt"
PENDING_FILE="$STATE_DIR/telegram_pending_post.txt"
LOG_FILE="$STATE_DIR/telegram_fire_log.txt"
TG_ENV="/home/ubuntu/.hermes/probot4/.env"  # placeholder guard
TG_ENV="/home/ubuntu/.hermes/profiles/bot4/.env"
CHAT_ID="@jacklohai"

mkdir -p "$STATE_DIR"

# 1. Load token
if [ ! -f "$TG_ENV" ]; then
  echo "$(date -Iseconds) | ABORT: $TG_ENV missing" >> "$LOG_FILE"
  exit 1
fi
TG_TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' "$TG_ENV" | cut -d= -f2- | sed 's/^"//;s/"$//')
if [ -z "$TG_TOKEN" ]; then
  echo "$(date -Iseconds) | ABORT: TELEGRAM_BOT_TOKEN empty" >> "$LOG_FILE"
  exit 1
fi

# 2. 48h cap check
if [ -f "$LAST_POST_FILE" ]; then
  LAST_TS=$(grep -oE 'Promo sent: [0-9-]+' "$LAST_POST_FILE" | head -1 | awk '{print $3}')
  if [ -n "$LAST_TS" ]; then
    LAST_EPOCH=$(date -d "$LAST_TS" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    HOURS_SINCE=$(( (NOW_EPOCH - LAST_EPOCH) / 3600 ))
    if [ "$HOURS_SINCE" -lt 48 ]; then
      echo "$(date -Iseconds) | SKIP: $HOURS_SINCE h since last post (<48h cap)" >> "$LOG_FILE"
      exit 0
    fi
  fi
fi

# 3. Load staged draft
if [ ! -f "$PENDING_FILE" ]; then
  echo "$(date -Iseconds) | ABORT: no staged draft at $PENDING_FILE" >> "$LOG_FILE"
  exit 1
fi
DRAFT=$(awk '/^Source:/{exit} {print}' "$PENDING_FILE" | sed '$d')
if [ -z "$DRAFT" ]; then
  echo "$(date -Iseconds) | ABORT: draft empty" >> "$LOG_FILE"
  exit 1
fi

# 4. Send to TG (write body to file first, then post — tirith blocks heredoc+curl)
DRAFT_FILE=/tmp/tg_brain_reset_post.txt
printf '%s' "$DRAFT" > "$DRAFT_FILE"
RESP_FILE=/tmp/tg_brain_reset_resp.json
curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys; m=open('$DRAFT_FILE').read(); print(json.dumps({'chat_id':'$CHAT_ID','text':m,'parse_mode':'HTML','disable_web_page_preview':False}))")" \
  -o "$RESP_FILE"

# 5. Log result
if grep -q '"ok":true' "$RESP_FILE"; then
  MSG_ID=$(python3 -c "import json; d=json.load(open('$RESP_FILE')); print(d.get('result',{}).get('message_id','?'))")
  echo "Promo sent: $(date +%Y-%m-%d), product=The 7-Day Brain Reset (FREE, lead), message_id=${MSG_ID}, channel=@jacklohai, codes=VIRALFIRST+CREATOR30+LAUNCH50+LAUNCH20" > "$LAST_POST_FILE"
  echo "$(date -Iseconds) | SENT: msg_id=$MSG_ID" >> "$LOG_FILE"
  # Archive draft (move out so it doesn't re-fire)
  mv "$PENDING_FILE" "$STATE_DIR/telegram_posted_$(date +%Y-%m-%d_%H%M)_brain_reset.txt"
  exit 0
else
  echo "$(date -Iseconds) | FAIL: $(head -c 300 $RESP_FILE)" >> "$LOG_FILE"
  exit 2
fi