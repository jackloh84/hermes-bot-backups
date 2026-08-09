#!/usr/bin/env bash
export PATH="$HOME/.local/bin:$PATH"
# Load GUMROAD_ACCESS_TOKEN from bot4 .env (never hardcode secrets)
if [ -z "${GUMROAD_ACCESS_TOKEN:-}" ] && [ -f /home/ubuntu/.hermes/profiles/bot4/.env ]; then
    export GUMROAD_ACCESS_TOKEN="$(grep -E '^GUMROAD_ACCESS_TOKEN=' /home/ubuntu/.hermes/profiles/bot4/.env | head -1 | cut -d= -f2- | tr -d '"')"
fi
bash ~/.hermes/profiles/bot4/scripts/gumroad-sales-tracker.sh
