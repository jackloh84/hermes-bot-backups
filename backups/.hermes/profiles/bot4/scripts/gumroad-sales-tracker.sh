#!/usr/bin/env bash
# Track Gumroad sales - runs daily
export PATH="$HOME/.local/bin:$PATH"
echo "=== Gumroad Sales Report — $(date '+%Y-%m-%d %H:%M SGT') ==="
echo ""

# Get sales report
gumroad sales list --json --non-interactive 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
sales = data.get('sales', [])
if not sales:
    print('No sales yet. Products are live and waiting!')
    print()
    print('Your products:')
    print('  📦 https://jackalope86.gumroad.com/l/byrjla  (Vol 1 - \$19)')
    print('  📦 https://jackalope86.gumroad.com/l/xcjutg  (Vol 2 - \$19)')
    sys.exit(0)

total = 0
for s in sales:
    price = float(s.get('formatted_display_price', '0').replace('\$',''))
    total += price
    print(f\"💰 Sale! {s.get('product_name','?')} — {s.get('formatted_display_price','?')}\")
    print(f\"   Customer: {s.get('email','?')}\")
    print(f\"   Date: {s.get('created_at','?')}\")
    print()

print(f'Total sales: \${total:.2f}')
print(f'Total orders: {len(sales)}')
" 2>/dev/null

echo ""
echo "Products: https://jackalope86.gumroad.com"
