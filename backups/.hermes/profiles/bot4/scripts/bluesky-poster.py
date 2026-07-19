#!/usr/bin/env python3
"""
Bluesky auto-poster for Jack Loh Gumroad products.
Policy-compliant: self-labeling, grapheme limit, AI disclosure, random posting.
"""
from pathlib import Path
import random, datetime, re
from atproto import Client

# ── Config ──
HANDLE = "jackloh84.bsky.social"
APP_PASSWORD = "2hnm-3dhm-lvsy-muz2"

PROFILE_DIR = Path.home() / ".hermes" / "profiles" / "bot4"
STATE_FILE = PROFILE_DIR / "state" / "bluesky_last_product.txt"
SKIP_LOG = PROFILE_DIR / "state" / "bluesky_skip_log.txt"
POLICY_LOG = PROFILE_DIR / "state" / "bluesky_policy_check.txt"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

OFFER_CODE = "VIRALFIRST"

PRODUCTS = [
    ("1", "50 Viral TikTok Hooks + AI Prompts", "$3",
     "https://jackalope86.gumroad.com/l/diywdak",
     f"FREE with code {OFFER_CODE} (limited to 10!)"),
    ("2", "AI for Content Creators Prompt Pack Vol 2", "SGD$19",
     "https://jackalope86.gumroad.com/l/xcjutg", None),
    ("3", "AI Business Automation Prompt Pack", "SGD$19",
     "https://jackalope86.gumroad.com/l/byrjla", None),
    ("4", "The AI Solopreneur Launchpad", "$5",
     "https://jackalope86.gumroad.com/l/dgdtjf", None),
]

POST_TEMPLATES = [
    [
        "50 viral TikTok hooks. Pattern interrupts, curiosity gaps, "
        "story starters. Each comes with an AI prompt to remix.\n\n"
        f"Normally $3. Use code {OFFER_CODE} for 100% off.\n\n"
        "{link}",
        "The first 3 seconds make or break your video. "
        "50 proven hooks that work. Copy, paste, post.\n\n"
        "{link}",
    ],
    [
        "Spending hours on content? "
        "Scripts, captions, thumbnails, audience growth \u2014 "
        "all in one AI prompt pack. Works with ChatGPT, Claude, Gemini.\n\n"
        "{link}",
        "Your content workflow shouldn't take all day. "
        "60+ structured prompts for scripts, captions, hooks, "
        "and growth. Copy-paste into any AI.\n\n{link}",
    ],
    [
        "Still typing the same prompts every day? "
        "100+ business automation prompts \u2014 marketing, "
        "productivity, finance, content. Save 10+ hours/week.\n\n"
        "{link}",
        "Stop reinventing prompts. "
        "Copy-paste business automation templates that actually "
        "work. Emails, CRM, lead gen, SOPs.\n\n{link}",
    ],
    [
        "From idea to first dollar. "
        "The AI Solopreneur Launchpad \u2014 prompts for validation, "
        "branding, marketing, and sales. Everything you need to start.\n\n"
        "{link}",
        "Ready to start your solo business? "
        "50+ structured prompts to validate, launch, and grow. "
        "No fluff, just execution.\n\n$5\n{link}",
    ],
]

# ── POLICY RULES (Bluesky Community Guidelines + Automation Policy) ──
BLUESKY_POLICY = {
    "max_graphemes": 300,  # Hard limit - post rejected if exceeded
    "max_hashtags": 5,     # Recommended max
    "ai_disclosure_required": True,
    "self_label_automated": True,
    "banned_patterns": [
        "buy now", "click here", "limited offer", "act fast",
        "don't miss", "last chance", "hurry", "exclusive deal",
    ],
    "required_disclosure": "🤖 AI-assisted post",
}

def count_graphemes(text):
    """Count graphemes (not bytes or chars). Bluesky uses graphemes."""
    count = 0
    i = 0
    while i < len(text):
        cp = ord(text[i])
        if 0xD800 <= cp <= 0xDBFF and i + 1 < len(text):
            count += 1
            i += 2  # Skip surrogate pair
        else:
            # Emoji, combining marks etc count as 1 grapheme each roughly
            count += 1
            i += 1
    return count

def check_policy(post_text, product_name):
    """Run policy compliance checks. Returns (passed: bool, issues: list, warnings: list)."""
    issues = []
    warnings = []
    
    # 1. Grapheme limit check
    graphemes = count_graphemes(post_text)
    if graphemes > BLUESKY_POLICY["max_graphemes"]:
        issues.append(f"Grapheme count {graphemes} exceeds {BLUESKY_POLICY['max_graphemes']} limit")
    
    # 2. URL check - use bare URLs
    if post_text.count("https://") > 2:
        warnings.append("Multiple https:// URLs - consider bare links to save graphemes")
    
    # 3. Banned patterns check
    for pattern in BLUESKY_POLICY["banned_patterns"]:
        if pattern.lower() in post_text.lower():
            issues.append(f"Contains banned pattern: '{pattern}' - sounds like spam")

    # 4. Hashtag count check
    hashtag_count = post_text.count("#")
    if hashtag_count == 0:
        warnings.append("No hashtags - post may have lower discoverability")
    elif hashtag_count > BLUESKY_POLICY["max_hashtags"]:
        warnings.append(f"Hashtags ({hashtag_count}) exceed recommended {BLUESKY_POLICY['max_hashtags']}")
    
    # 5. Content length sanity
    if len(post_text) < 30:
        warnings.append("Post very short - consider adding more value")
    if len(post_text) > 800:
        warnings.append("Post very long for Bluesky - consider trimming")
    
    passed = len(issues) == 0
    return passed, issues, warnings

def apply_self_label(client):
    """Apply automated account self-label per Bluesky policy."""
    try:
        client.com.atproto.repo.put_record({
            "repo": client.me.did,
            "collection": "app.bsky.actor.profile",
            "rkey": "self",
            "record": {
                "displayName": "Jack Loh \U0001F1F8\U0001F1EC",
                "description": "Digital creator \u2022 Solopreneur \u2022 Singapore\n\n"
                               "Sharing AI prompts & automation tips for creators.\n"
                               "\U0001F4E6 Gumroad: jackalope86.gumroad.com\n"
                               "\U0001F4E2 Telegram: t.me/jacklohai\n\n"
                               "\U0001F916 AI-assisted \u2014 some posts automated",
                "labels": {"$type": "com.atproto.label.self", 
                           "values": [{"val": "automated"}]}
            }
        })
        return True
    except Exception as e:
        POLICY_LOG.write_text(f"[ERR] self-label failed: {e}\n")
        return False

def humanize_text(text):
    """Basic humanization pass - strip AI-isms, add natural variation."""
    # Remove redundant punctuation
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\.{3,}', '...', text)
    # Vary link placement
    if random.random() > 0.5:
        text = text.replace("\n\n{link}", "\n\n{link}\n\nThoughts?")
    return text

def should_post_today():
    """70% skip chance ~2 posts/week. More on weekends."""
    roll = random.randint(1, 100)
    today = datetime.date.today().isoformat()
    weekday = datetime.datetime.today().weekday()
    skip_chance = 85 if weekday >= 5 else 70
    
    if roll <= skip_chance:
        SKIP_LOG.write_text(f"{today} | SKIP (rolled {roll}, threshold {skip_chance}%)\n")
        return False
    return True

def get_current_product():
    """Advance to next product, return current."""
    if STATE_FILE.exists():
        idx = int(STATE_FILE.read_text().strip() or "1")
    else:
        idx = 1
    next_idx = (idx % len(PRODUCTS)) + 1
    STATE_FILE.write_text(str(next_idx))
    return PRODUCTS[idx - 1]

def main():
    # Policy pre-flight
    today = datetime.date.today().isoformat()
    POLICY_LOG.write_text(f"\n=== {today} ===\n")
    
    if not should_post_today():
        print("Skipped today (random roll). No post.")
        return

    prod_id, name, price, link, offer_info = get_current_product()
    idx = int(prod_id) - 1
    
    # Pick template and format
    template_idx = random.randint(0, len(POST_TEMPLATES[idx]) - 1)
    post_text = POST_TEMPLATES[idx][template_idx].format(link=link)
    post_text = humanize_text(post_text)
    
    # ── POLICY CHECK ──
    passed, issues, warnings = check_policy(post_text, name)
    
    policy_report = f"[{today}] Product {prod_id}: {name}\n"
    policy_report += f"  Graphemes: {count_graphemes(post_text)}\n"
    policy_report += f"  Passed: {'YES' if passed else 'NO'}\n"
    
    if issues:
        policy_report += f"  ❌ ISSUES: {', '.join(issues)}\n"
        print(f"❌ POLICY FAILED:\n{policy_report}")
        POLICY_LOG.write_text(policy_report)
        return  # DO NOT POST
    
    if warnings:
        policy_report += f"  ⚠️ WARNINGS: {', '.join(warnings)}\n"
    
    policy_report += f"  ✅ Ready to post\n"
    POLICY_LOG.write_text(policy_report)
    print(f"✅ Policy check passed for {name}")
    for w in warnings:
        print(f"  ⚠️  {w}")
    
    # ── POST ──
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    
    # Apply self-labeling (once is enough - runs each time but idempotent)
    apply_self_label(client)
    
    # Send the post
    result = client.send_post(post_text)
    
    print(f"✅ Posted on Bluesky: {name} ({price})")
    print(f"   URI: {result.uri}")
    print(f"   Graphemes: {count_graphemes(post_text)}")
    
    # Log success
    POLICY_LOG.write_text(policy_report + f"  🚀 POSTED: {result.uri}\n")

if __name__ == "__main__":
    main()
