#!/usr/bin/env python3
"""
Multi-Platform Campaign Manager
================================
Generates platform-optimized promotional posts from a single product brief.

Usage:
    python multi-platform-campaign.py \
        --product "50 Viral TikTok Hooks + AI Prompts" \
        --desc "A swipe file of 50 proven viral hooks paired with AI prompts to remix them" \
        --price "$3" \
        --url "https://jackalope86.gumroad.com/l/tiktok-hooks" \
        --tags "tiktok,content-creation,viral-marketing,ai-prompts"

    Shortcut: use --product-id 1 through 4 to auto-fill known products.

Output:
    - Prints all variants to stdout.
    - Saves individual files to /home/ubuntu/gumroad-promo/campaign-{timestamp}/
"""

import argparse
import os
import sys
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Known product catalogue (Jack's Gumroad store: jackalope86.gumroad.com)
# ---------------------------------------------------------------------------
KNOWN_PRODUCTS = {
    1: {
        "name": "50 Viral TikTok Hooks + AI Prompts",
        "desc": "A swipe file of 50 proven viral TikTok hooks paired with ready-to-use AI prompts so you can remix, repurpose, and never run out of scroll-stopping openings.",
        "price": "$3",
        "url": "https://jackalope86.gumroad.com/l/tiktok-hooks",
        "tags": "tiktok,content-creation,viral-marketing,ai-prompts,social-media-growth",
    },
    2: {
        "name": "AI for Content Creators Vol 2",
        "desc": "Unlock the full power of AI in your creative workflow — advanced prompts, real-world pipelines, and automation strategies for serious content creators.",
        "price": "SGD$19",
        "url": "https://jackalope86.gumroad.com/l/ai-content-creators-v2",
        "tags": "ai-content,content-creation,ai-prompts,creator-economy,productivity",
    },
    3: {
        "name": "AI Business Automation",
        "desc": "Automate your busiest workflows with AI — from email triage and CRM enrichment to social scheduling and reporting. No coding required.",
        "price": "SGD$19",
        "url": "https://jackalope86.gumroad.com/l/ai-business-automation",
        "tags": "ai-automation,business-productivity,workflow-automation,no-code,small-business",
    },
    4: {
        "name": "The AI Solopreneur Launchpad",
        "desc": "A step-by-step system for solopreneurs to launch, market, and scale a product using AI tools — from idea validation to first sale.",
        "price": "$5",
        "url": "https://jackalope86.gumroad.com/l/ai-solopreneur-launchpad",
        "tags": "solopreneur,ai-tools,product-launch,side-hustle,entrepreneurship",
    },
}

# ---------------------------------------------------------------------------
# Platform constants
# ---------------------------------------------------------------------------
BLUESKY_MAX = 300
MASTODON_MAX = 280

# ---------------------------------------------------------------------------
# Unicodify: smart quotes, em dashes, typographic polish
# ---------------------------------------------------------------------------
def smart_text(text: str) -> str:
    """Apply typographic polish — smart quotes, em dashes, ellipsis."""
    text = text.replace("'", "'").replace("'", "'")
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace("--", "\u2014").replace("...", "\u2026")
    return text


def truncate_graphemes(text: str, limit: int) -> str:
    """Truncate to fit within `limit` grapheme clusters (approximation
    using Unicode extended grapheme clusters via a simple regex approach).

    Falls back gracefully: cuts at the last sentence boundary or space.
    """
    if len(text) <= limit:
        return text

    # Try cutting at last sentence boundary within limit
    prefix = text[: limit - 1]
    # Last sentence end
    for punct in (".", "!", "?"):
        idx = prefix.rfind(punct)
        if idx >= int(limit * 0.6):  # only if meaningful
            return prefix[: idx + 1]

    # Fallback: last space
    idx = prefix.rfind(" ")
    if idx >= int(limit * 0.4):
        return prefix[:idx] + "\u2026"

    return prefix + "\u2026"


def parse_tags(tags_str: str) -> list[str]:
    """Parse comma/space-separated tags into a clean list."""
    parts = re.split(r"[,\s]+", tags_str.strip())
    return [t.strip().lower().replace("-", "").replace(" ", "") for t in parts if t.strip()]


def format_hashtags(tags: list[str], *, prefix: str = "#", limit: int = 999) -> str:
    """Join tags as hashtags, truncating if over limit."""
    tag_string = " ".join(f"{prefix}{t}" for t in tags)
    if len(tag_string) > limit:
        # Drop tags one by one from the end
        while len(tag_string) > limit and len(tags) > 1:
            tags.pop()
            tag_string = " ".join(f"{prefix}{t}" for t in tags)
        if len(tag_string) > limit:
            tag_string = tag_string[:limit]
    return tag_string


# ---------------------------------------------------------------------------
# Platform generators
# ---------------------------------------------------------------------------

def generate_bluesky(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """Bluesky post — max 300 graphemes, concise, link at end.
    Never truncates the URL — drops hashtags or shortens desc if needed.
    """
    hashtags = format_hashtags(tags, limit=BLUESKY_MAX - 60)
    body = smart_text(f"{name} — {desc.rstrip('.')}. {price}")
    url_line = f"\n\n{url}"
    post = f"{body}{url_line}"

    if len(post) <= BLUESKY_MAX:
        return post

    # Over limit — shorten the body while keeping URL intact
    remaining = BLUESKY_MAX - len(url_line)
    short_desc = truncate_graphemes(desc.rstrip("."), remaining - len(name) - 5)
    body = smart_text(f"{name} — {short_desc}. {price}")
    post = f"{body}{url_line}"
    if len(post) > BLUESKY_MAX:
        post = f"{name}: {url}"
    return post


def generate_telegram(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """Telegram post — Markdown-rich, full story, emoji, section breaks."""
    hashtags = format_hashtags(tags)
    body = smart_text(
        f"**{name}**\n\n"
        f"{desc}\n\n"
        f"💰 **Price:** {price}\n\n"
        f"🔗 **[Grab it here]({url})**\n\n"
        f"---\n"
        f"{hashtags}"
    )
    return body


def generate_linkedin(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """LinkedIn post — professional, story-driven, CTA."""
    hashtags = format_hashtags(tags, limit=180)
    body = smart_text(
        f"🚀 **{name}**\n\n"
        f"{desc}\n\n"
        f"💡 **Why this matters:**\n"
        f"If you're building in public or growing a creator business, "
        f"tools like this save you hours of staring at a blank page. "
        f"I've put together something practical — prompts that work, "
        f"paired with hooks that have already been proven to perform.\n\n"
        f"📦 **Price:** {price}\n\n"
        f"👇 **Get it here:** {url}\n\n"
        f"---\n"
        f"{hashtags}"
    )
    return body


def generate_reddit(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """Reddit post — value-first, humble, community-oriented."""
    hashtags = format_hashtags(tags)
    body = smart_text(
        f"Sharing something I built: **{name}**\n\n"
        f"{desc}\n\n"
        f"💰 **{price}** — I wanted to keep it accessible.\n\n"
        f"👉 {url}\n\n"
        f"Happy to answer questions below. Hope this helps someone! 🙌"
    )
    return body


def generate_pinterest(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """Pinterest pin description — keyword-rich, SEO-friendly, link-first."""
    hashtags = format_hashtags(tags, limit=140)
    body = smart_text(
        f"{name} | {desc} | {price}\n\n"
        f"Perfect for content creators, solopreneurs, and anyone building online. "
        f"Save this pin for later and grab the full guide at the link below.\n\n"
        f"🔗 {url}\n\n"
        f"{hashtags}"
    )
    return body


def generate_mastodon(name: str, desc: str, price: str, url: str, tags: list[str]) -> str:
    """Mastodon post — 280 chars max, friendly, terse, hash-taggy.

    Strategy: build the full post. If it exceeds 280, drop hashtags first.
    If still over, truncate the description portion only (never the URL).
    """
    body = smart_text(f"{name} — {desc.rstrip('.')}. {price}")
    hashtags = format_hashtags(tags, limit=MASTODON_MAX - 60)
    post = f"{body}\n{url}\n{hashtags}"

    if len(post) <= MASTODON_MAX:
        return post

    # Try dropping hashtags
    post_no_tags = f"{body}\n{url}"
    if len(post_no_tags) <= MASTODON_MAX:
        return post_no_tags

    # Still over — shorten the description within body while keeping URL intact.
    # We need body (with truncated desc) + \n + url to fit.
    remaining = MASTODON_MAX - len(f"\n{url}")  # space for body
    body = smart_text(f"{name} — ")
    remaining -= len(body)
    # Truncate description
    short_desc = truncate_graphemes(desc.rstrip("."), remaining - 2)
    body = smart_text(f"{name} — {short_desc}. {price}")
    post = f"{body}\n{url}"
    if len(post) > MASTODON_MAX:
        post = post[:MASTODON_MAX].rsplit(" ", 1)[0] + "\u2026\n" + url
    return post


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
PLATFORMS = [
    {"key": "bluesky", "label": "Bluesky", "fn": generate_bluesky},
    {"key": "telegram", "label": "Telegram", "fn": generate_telegram},
    {"key": "linkedin", "label": "LinkedIn", "fn": generate_linkedin},
    {"key": "reddit", "label": "Reddit", "fn": generate_reddit},
    {"key": "pinterest", "label": "Pinterest", "fn": generate_pinterest},
    {"key": "mastodon", "label": "Mastodon", "fn": generate_mastodon},
]

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
OUTPUT_DIR = "/home/ubuntu/gumroad-promo"


def save_variant(platform_key: str, content: str, campaign_dir: Path) -> Path:
    """Write one platform variant to disk."""
    ext = "md" if platform_key == "telegram" else "txt"
    path = campaign_dir / f"{platform_key}.{ext}"
    path.write_text(content, encoding="utf-8")
    return path


def print_report(variants: list[tuple[str, str, str]], campaign_dir: Path):
    """Print a well-formatted campaign report to stdout."""
    sep = "=" * 60
    for platform_key, label, content in variants:
        char_count = len(content)
        print(f"\n{sep}")
        print(f"  {label}  ({char_count} chars)")
        print(f"{sep}")
        print(content)
    print(f"\n{sep}")
    print(f"  All variants saved to: {campaign_dir}")
    print(f"{sep}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Multi-Platform Campaign Manager — generate platform-optimised posts."
    )

    # Product identification
    product_group = parser.add_mutually_exclusive_group(required=True)
    product_group.add_argument(
        "--product-id",
        type=int,
        choices=list(KNOWN_PRODUCTS.keys()),
        help=f"Known product ID ({', '.join(str(k) for k in KNOWN_PRODUCTS)})",
    )
    product_group.add_argument(
        "--product", type=str, help="Product name"
    )

    # Custom fields (required if --product-id not used)
    parser.add_argument("--desc", type=str, help="Short product description")
    parser.add_argument("--price", type=str, help="Price string (e.g. '$3', 'SGD$19')")
    parser.add_argument("--url", type=str, help="Full Gumroad URL")
    parser.add_argument(
        "--tags",
        type=str,
        help="Comma-separated tags (e.g. 'tiktok,content-creation')",
    )

    args = parser.parse_args()

    # Resolve product data
    if args.product_id is not None:
        product = KNOWN_PRODUCTS[args.product_id]
        name = product["name"]
        desc = product["desc"]
        price = product["price"]
        url = product["url"]
        tags_str = product["tags"]
    else:
        name = args.product
        desc = args.desc
        price = args.price
        url = args.url
        tags_str = args.tags
        missing = []
        if not desc:
            missing.append("--desc")
        if not price:
            missing.append("--price")
        if not url:
            missing.append("--url")
        if not tags_str:
            missing.append("--tags")
        if missing:
            print(f"Error: missing required arguments: {', '.join(missing)}", file=sys.stderr)
            print("Use --product-id to load a known product, or supply all custom fields.", file=sys.stderr)
            sys.exit(1)

    tags = parse_tags(tags_str)

    # Build campaign directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")[:40]
    campaign_dir = Path(OUTPUT_DIR) / f"campaign-{timestamp}_{slug}"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Generate and save all variants
    variants: list[tuple[str, str, str]] = []
    for platform in PLATFORMS:
        content = platform["fn"](name, desc, price, url, tags)
        path = save_variant(platform["key"], content, campaign_dir)
        variants.append((platform["key"], platform["label"], content))
        print(f"  ✓ Saved  {platform['label']:>10}  →  {path}", file=sys.stderr)

    # Print report to stdout
    print_report(variants, campaign_dir)


if __name__ == "__main__":
    main()
