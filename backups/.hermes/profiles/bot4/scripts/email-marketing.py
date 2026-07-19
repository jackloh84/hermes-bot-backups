#!/usr/bin/env python3
"""Email Marketing Pipeline for Jack Loh's Gumroad Store

Captures leads, sends automated follow-up sequences, and tracks conversions.

Usage:
  ./email-marketing.py --capture user@example.com       # Capture a new lead
  ./email-marketing.py --send-sequence                  # Send scheduled emails
  ./email-marketing.py --list                           # Show all leads
  ./email-marketing.py --stats                          # Show email stats
"""
import json, os, sys, smtplib, subprocess, datetime, hashlib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Config ──
BASE_DIR = Path.home() / ".hermes" / "profiles" / "bot4" / "state" / "email-marketing"
LEADS_FILE = BASE_DIR / "leads.json"
CAMPAIGNS_FILE = BASE_DIR / "campaigns.json"
BASE_DIR.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    {"id": 1, "name": "50 Viral TikTok Hooks + AI Prompts", "price": "$3", "url": "https://jackalope86.gumroad.com/l/diywdak", "offer_code": "FIRST50"},
    {"id": 2, "name": "AI for Content Creators Vol 2", "price": "SGD$19", "url": "https://jackalope86.gumroad.com/l/xcjutg"},
    {"id": 3, "name": "AI Business Automation Prompt Pack", "price": "SGD$19", "url": "https://jackalope86.gumroad.com/l/byrjla"},
    {"id": 4, "name": "The AI Solopreneur Launchpad", "price": "$5", "url": "https://jackalope86.gumroad.com/l/dgdtjf"},
]

# ── Email Sequences ──
SEQUENCES = {
    "welcome": {
        "day": 0,
        "subject": "🎬 Your Free Viral Hooks Are Here!",
        "body": """Hey there,

Thanks for grabbing the free sample! Here's your bonus hook:

🔥 The "Pattern Interrupt" Hook:
"Stop scrolling. I caught you. Now here's why you should read this."

Use with any AI: "Rewrite this hook for a [fitness/tech/business] audience."

👉 Get the FULL pack of 50 hooks + AI remix prompts for {offer}:
{product_url}

Code: {offer_code} (limited to 10!)

Happy creating,
Jack Loh 🇸🇬
📦 jackalope86.gumroad.com"""
    },
    "day3": {
        "day": 3,
        "subject": "💡 3 More Hooks That Got 1M+ Views",
        "body": """Hey again,

Quick tip: The best hooks use curiosity gaps. Here are 3 that work:

1. "I tried [X] for 30 days — here's what happened"
2. "The one setting 99% of creators ignore"
3. "Nobody tells you this about [topic]..."

Want 47 more? They're in the full pack:
{product_url}

Plus the AI prompts to remix them for YOUR niche.

— Jack"""
    },
    "day7": {
        "day": 7,
        "subject": "🎯 Complete Your AI Toolkit (Bundle Deal)",
        "body": """Hey! Last week you grabbed the free hooks.

I noticed you might also like:
🎬 TikTok Hooks Pack ($3) → Already have this
📸 Content Creator AI Prompts (SGD$19) → Scripts, captions, thumbnails
⚙️ Business Automation Pack (SGD$19) → Emails, CRM, lead gen templates
🚀 Solopreneur Launchpad ($5) → Business-in-a-box

Get all 4 at jackalope86.gumroad.com — they all work with ChatGPT, Claude, and Gemini.

— Jack Loh 🇸🇬"""
    },
    "day14": {
        "day": 14,
        "subject": "🎁 Exclusive Offer: Complete Your Set",
        "body": """Quick heads up — you're still on the free sample.

The full 50 Viral TikTok Hooks + AI Prompts pack is just $3 (one-time, no subscriptions).

Includes:
✅ 50 proven hooks (5 categories)
✅ AI prompts to remix each one
✅ PDF + TXT formats
✅ Works with ChatGPT, Claude, Gemini

👉 {product_url}

Code {offer_code} still works if there are redemptions left!

— Jack"""
    },
    "day30": {
        "day": 30,
        "subject": "📬 Still Creating? Here's What's New",
        "body": """It's been a month! Here's what's new at the store:
- More prompt packs
- Better pricing bundles
- All products updated for 2026 trends

Check it out: https://jackalope86.gumroad.com

Reply to this email if you need anything.

— Jack Loh 🇸🇬"""
    }
}

def load_leads():
    if LEADS_FILE.exists():
        return json.loads(LEADS_FILE.read_text())
    return []

def save_leads(leads):
    LEADS_FILE.write_text(json.dumps(leads, indent=2, default=str))

def capture_lead(email, source="email-capture-page"):
    leads = load_leads()
    existing = [l for l in leads if l["email"] == email]
    if existing:
        print(f"⚠️  Lead already exists: {email}")
        return
    lead = {
        "email": email,
        "source": source,
        "captured_at": datetime.datetime.now().isoformat(),
        "emails_sent": [],
        "purchased": False,
        "purchase_value": 0
    }
    leads.append(lead)
    save_leads(leads)
    print(f"✅ Lead captured: {email} (from {source})")
    # Send welcome immediately
    send_email(email, SEQUENCES["welcome"]["subject"],
               SEQUENCES["welcome"]["body"].format(
                   product_url=PRODUCTS[0]["url"],
                   offer=f"FREE with code {PRODUCTS[0]['offer_code']}",
                   offer_code=PRODUCTS[0]["offer_code"]
               ))
    # Log it
    leads = load_leads()
    for l in leads:
        if l["email"] == email:
            l["emails_sent"].append({
                "sequence": "welcome",
                "sent_at": datetime.datetime.now().isoformat()
            })
    save_leads(leads)
    print(f"  → Welcome email sent to {email}")

def send_email(to, subject, body):
    """Send email using system mail command."""
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["To"] = to
    msg["From"] = "Jack Loh <jackloh84@gmail.com>"
    # Use system mail command as fallback
    proc = subprocess.run(
        ["mail", "-s", subject, to],
        input=body.encode("utf-8"),
        timeout=30
    )
    return proc.returncode == 0

def process_sequences():
    """Check all leads and send scheduled emails."""
    leads = load_leads()
    now = datetime.datetime.now()
    sent_count = 0
    for lead in leads:
        captured = datetime.datetime.fromisoformat(lead["captured_at"])
        days_since = (now - captured).days
        sent_names = {s["sequence"] for s in lead["emails_sent"]}
        for seq_name, seq in SEQUENCES.items():
            if seq_name == "welcome":
                continue  # Sent at capture time
            if seq_name not in sent_names and days_since >= seq["day"]:
                body = seq["body"].format(product_url=PRODUCTS[0]["url"])
                if send_email(lead["email"], seq["subject"], body):
                    lead["emails_sent"].append({
                        "sequence": seq_name,
                        "sent_at": now.isoformat()
                    })
                    sent_count += 1
                    print(f"  → Sent '{seq_name}' to {lead['email']}")
    save_leads(leads)
    print(f"📬 Sequence check complete. {sent_count} emails sent today.")

def list_leads():
    leads = load_leads()
    if not leads:
        print("📭 No leads captured yet.")
        return
    print(f"📋 Total Leads: {len(leads)}\n")
    for l in leads:
        emails = len(l["emails_sent"])
        purchased = "💰" if l["purchased"] else "📭"
        print(f"  {purchased} {l['email']}")
        print(f"     Source: {l['source']}")
        print(f"     Since: {l['captured_at'][:10]}")
        print(f"     Emails sent: {emails}")
        print()

def show_stats():
    leads = load_leads()
    total = len(leads)
    total_sent = sum(len(l["emails_sent"]) for l in leads)
    converted = sum(1 for l in leads if l["purchased"])
    print(f"""
┌─────────────────────────────────┐
│  📊 Email Marketing Stats        │
├─────────────────────────────────┤
│  Total Leads:     {total:>4}                    │
│  Emails Sent:     {total_sent:>4}                    │
│  Conversions:     {converted:>4}                    │
│  Conv Rate:       {((converted/total*100) if total else 0):>4.1f}%                   │
│  Active Sequences: {len(SEQUENCES)}                    │
└─────────────────────────────────┘
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "--capture" and len(sys.argv) > 2:
        capture_lead(sys.argv[2], source=sys.argv[3] if len(sys.argv) > 3 else "manual")
    elif cmd == "--send-sequence":
        process_sequences()
    elif cmd == "--list":
        list_leads()
    elif cmd == "--stats":
        show_stats()
    else:
        print("Unknown command. Use --capture, --send-sequence, --list, or --stats")
