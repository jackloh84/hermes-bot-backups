#!/usr/bin/env bash
export PATH="$HOME/.local/bin:$PATH"
report=$(mktemp)
echo "=== Earning Opportunity Scan — $(date '+%Y-%m-%d %H:%M SGT') ===" > "$report"
echo "" >> "$report"
blogwatcher-cli scan 2>&1 >> "$report"
echo "" >> "$report"
echo "=== New Articles ===" >> "$report"
blogwatcher-cli articles --limit 20 2>&1 >> "$report"
cat "$report"
rm "$report"