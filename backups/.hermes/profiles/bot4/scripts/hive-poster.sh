#!/usr/bin/env bash
export PATH="$HOME/.local/bin:$PATH"
source /home/ubuntu/projects/hive-bot/.env
cd /home/ubuntu/projects/hive-bot
python3 poster.py --max-posts 1 >> /home/ubuntu/projects/hive-bot/cron.log 2>&1
echo "--- Hive post attempt at $(date '+%Y-%m-%d %H:%M SGT') ---"
