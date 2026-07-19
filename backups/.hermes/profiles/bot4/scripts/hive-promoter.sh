#!/usr/bin/env bash
# Hive Product Promoter — posts original content promoting Gumroad products
export PATH="$HOME/.local/bin:$PATH"
source /home/ubuntu/projects/hive-bot/.env 2>/dev/null

echo "=== Hive Product Promotion — $(date '+%Y-%m-%d %H:%M SGT') ==="
echo ""

# Use the last template from content_templates.json (newest promo post)
cd /home/ubuntu/projects/hive-bot
template_idx=$(python3 -c "import json; templates=json.load(open('content_templates.json')); idx=$(( $(cat .post_index 2>/dev/null || echo 0) )); print(idx % len(templates))")
echo "Next template index: $template_idx"
echo ""

# For now, just log which post would go out
python3 -c "
import json
templates = json.load(open('content_templates.json'))
idx = int(open('.post_index').read().strip()) if __import__('os').path.exists('.post_index') else 0
idx = idx % len(templates)
post = templates[idx]
print(f'Next post: {post["title"]}')
print(f'Tags: {post["tags"]}')
print(f'Body preview: {post["body"][:100]}...')
"
