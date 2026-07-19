#!/usr/bin/env python3
"""
cross-platform-seo.py — SEO helpers for non-Gumroad properties Jack owns.

Generates SEO-optimized content for:
  - YouTube video titles, descriptions, tags (YouTube Shorts)
  - Telegram channel posts (with SEO keyword density)
  - GitHub repo README frontmatter + topics for discoverability
  - DEV.to / Medium / Hashnode article frontmatter

Each subcommand outputs the formatted content ready to paste.

Usage:
    python3 cross-platform-seo.py --youtube --topic "psychology of motivation" --keywords "psychology, motivation, dopamine"
    python3 cross-platform-seo.py --telegram --product 1
    python3 cross-platform-seo.py --github-readme --slug tiktok-viral-hooks --title "50 Viral TikTok Hooks" --url https://...
    python3 cross-platform-seo.py --article-frontmatter --title "..." --keyword "..." --platform devto
    python3 cross-platform-seo.py --all
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Canonical Jack product catalog (keep in sync with ai-seo-generator.py)
JACK_PRODUCTS = [
    {
        "name": "50 Viral TikTok Hooks + AI Prompts",
        "slug": "tiktok-viral-hooks",
        "url": "https://jackalope86.gumroad.com/l/diywdak",
        "price_usd": 3,
        "category": "social-media-prompts",
        "description": "50 proven viral TikTok hook templates + AI prompt packs for content creators who want to stop the scroll.",
        "audience": "TikTok creators, solopreneurs, content marketers",
        "tags": ["tiktok", "hooks", "viral", "ai-prompts", "content-creation"],
    },
    {
        "name": "AI for Content Creators Vol 2",
        "slug": "content-creator-prompts",
        "url": "https://jackalope86.gumroad.com/l/xcjutg",
        "price_usd": 19,
        "category": "content-creation",
        "description": "AI prompts for YouTube, TikTok, Instagram, and LinkedIn — script templates, hook libraries, and content calendars.",
        "audience": "content creators, YouTubers, social media managers",
        "tags": ["ai-prompts", "content-creation", "youtube", "tiktok", "instagram"],
    },
    {
        "name": "AI Business Automation Prompt Pack",
        "slug": "solopreneur-ai-toolkit",
        "url": "https://jackalope86.gumroad.com/l/byrjla",
        "price_usd": 19,
        "category": "business-automation",
        "description": "Automate your small business with AI — 100+ premium prompts for sales, marketing, ops, and customer service.",
        "audience": "solopreneurs, small business owners, freelancers",
        "tags": ["ai", "automation", "solopreneur", "business", "productivity"],
    },
    {
        "name": "The AI Solopreneur Launchpad",
        "slug": "youtube-shorts-generator",
        "url": "https://jackalope86.gumroad.com/l/dgdtjf",
        "price_usd": 5,
        "category": "solopreneur",
        "description": "50+ AI prompts and Notion templates to launch your solopreneur business in 30 days.",
        "audience": "aspiring solopreneurs, side-hustlers",
        "tags": ["solopreneur", "ai", "launchpad", "business", "notion"],
    },
]


# ===========================================================================
# YouTube Shorts SEO
# ===========================================================================

def build_youtube_short(topic, keywords, hook="", cta=""):
    """
    YouTube Shorts best practices (2026):
    - Title: 60-70 chars max, hook in first 40 chars
    - Description: 200-500 chars, keyword in first 100 chars
    - Tags: 8-15 specific tags, mix of broad + long-tail
    - Hashtags: 3-5 max in description
    """
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    primary = keywords[0] if keywords else topic
    secondary = keywords[1:5] if len(keywords) > 1 else []

    # Title — front-load the hook/keyword
    title_options = [
        f"{primary.title()} — {topic.title()} #shorts",
        f"{topic.title()} (in 30 seconds) #shorts",
        f"Why {primary.title()} Changes Everything #shorts",
    ]

    description = f"""{hook or f"Quick {topic} insight you can use today."}

What you'll learn in 30 seconds:
- The psychology behind {topic}
- Why most people get it wrong
- One actionable takeaway

🔗 Resources mentioned:
- Free {primary} starter: https://jackalope86.gumroad.com
- My {topic} prompt pack: https://jackalope86.gumroad.com

{cta or "Follow for more AI + psychology content."}

#{' #'.join(keywords[:5])} #shorts #psychology"""

    tags = keywords[:5] + [topic, "shorts", "psychology", "ai", "tips", "viral"]
    tags = list(dict.fromkeys(tags))[:15]  # dedupe + cap

    return {
        "title_options": title_options,
        "description": description,
        "tags": tags,
        "hashtags_for_description": ["#" + k.replace(" ", "") for k in keywords[:5]] + ["#shorts", "#psychology"],
    }


# ===========================================================================
# Telegram channel post (with SEO keyword density)
# ===========================================================================

def build_telegram_post(product_index, discount=None, offer_code=None, custom_hook=""):
    """Generate a Telegram-channel-optimized post for a product."""
    if product_index < 1 or product_index > len(JACK_PRODUCTS):
        print(f"❌ Product index must be 1-{len(JACK_PRODUCTS)}")
        sys.exit(1)
    p = JACK_PRODUCTS[product_index - 1]

    hook = custom_hook or f"Stop the scroll — here's a faster way."
    discount_line = ""
    if discount and offer_code:
        discount_line = f"\n\n🎁 **{offer_code}** = {discount}% off (limited time)"

    comma = ", "
    body = f"""{hook}

🎯 **{p['name']}**
${p['price_usd']} USD · instant download

{p['description']}

👥 Perfect for: {p['audience']}
📦 Includes: {comma.join(p['tags'][:3])}
{discount_line}
🛒 {p['url']}

— Jack 🇸🇬 | Solopreneur, AI tools for creators"""
    return body


# ===========================================================================
# GitHub repo README
# ===========================================================================

def build_github_readme(slug, title, url, summary="", topics=None, features=None):
    """Generate a SEO-optimized GitHub README with backlinks."""
    if not topics:
        topics = []
    if not features:
        features = []
    topics_line = "topics: [" + ", ".join(f'"{t}"' for t in topics) + "]" if topics else ""
    return f"""# {title}

> {summary or "AI-powered digital product for solopreneurs and content creators."}

🚀 **Get it here:** [{url}]({url})

## What This Is

{summary or "A ready-to-use digital product, built for fast execution."}

## Features

{chr(10).join(f"- {f}" for f in features) if features else "- 50+ tested templates\\n- AI prompt packs\\n- Works with ChatGPT, Claude, Gemini, DeepSeek"}

## Who It's For

- Solopreneurs who want to move fast
- Content creators building a system, not a one-off
- Small business owners who want leverage without headcount

## How To Use

1. Purchase the pack on Gumroad
2. Download the PDF / Notion template
3. Apply the prompts to your own workflow
4. Iterate based on what you see working

## About the Creator

Built by **Jack Loh** 🇸🇬 — AI tools for entrepreneurs and creators.

- 🛒 Store: [jackalope86.gumroad.com](https://jackalope86.gumroad.com)
- 📺 YouTube: [@jackloh84](https://www.youtube.com/@jackloh84)
- ✈️ Telegram: [@jacklohai](https://t.me/jacklohai)
- 🐙 GitHub: [@jackloh84](https://github.com/jackloh84)

## License

The repo (this README + example scripts) is MIT. The product itself is sold under a personal-use license on Gumroad. See product page for commercial-use options.

---

⭐ If this helps you, star the repo. It helps others find it.
"""


# ===========================================================================
# Article frontmatter (DEV.to / Medium / Hashnode)
# ===========================================================================

def build_article_frontmatter(title, keyword, platform="devto", description=None, tags=None):
    """Generate SEO-optimized article frontmatter per platform."""
    if not tags:
        tags = []
    if not description:
        description = f"Practical {keyword} guide for {datetime.now().year}: examples, templates, and prompts you can use today."

    if platform == "devto":
        # DEV.to rules: no date, no hyphenated tags, max 4 tags
        clean_tags = []
        for t in tags[:4]:
            clean = re.sub(r"[^a-z0-9]", "", t.lower())
            if clean:
                clean_tags.append(clean)
        return f"""---
title: {title}
published: true
description: {description[:160]}
tags: {json.dumps(clean_tags)}
canonical_url:
cover_image:
---

# {title}

{keyword.title()} is a big topic in {datetime.now().year} — let's break it down.

"""
    elif platform == "medium":
        return f"""---
title: {title}
subtitle: {description[:140]}
date: {datetime.now().strftime("%Y-%m-%d")}
---

"""
    elif platform == "hashnode":
        return f"""---
title: "{title}"
subtitle: "{description[:140]}"
slug: "{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}"
tags: {json.dumps([t.lower() for t in tags[:5]])}
published: true
canonical: ""
---

"""
    return ""


# ===========================================================================
# CLI
# ===========================================================================

def main():
    p = argparse.ArgumentParser(description="Cross-platform SEO helpers for Jack's footprint")
    p.add_argument("--youtube", action="store_true", help="Generate YouTube Short SEO package")
    p.add_argument("--topic", help="Topic (for --youtube)")
    p.add_argument("--keywords", help="Comma-separated keywords")
    p.add_argument("--hook", default="", help="Custom hook (for YouTube description)")
    p.add_argument("--cta", default="", help="Custom CTA (for YouTube description)")

    p.add_argument("--telegram", action="store_true", help="Generate Telegram post")
    p.add_argument("--product", type=int, help="Product index 1-N (for --telegram)")
    p.add_argument("--discount", help="Discount percent (optional)")
    p.add_argument("--offer-code", help="Gumroad offer code (optional)")
    p.add_argument("--telegram-hook", default="", help="Custom hook for Telegram")

    p.add_argument("--github-readme", action="store_true", help="Generate GitHub README")
    p.add_argument("--slug", help="Repo slug (for --github-readme)")
    p.add_argument("--title", help="Title")
    p.add_argument("--url", help="Product URL")
    p.add_argument("--summary", default="", help="Summary line")
    p.add_argument("--topics", help="Comma-separated GitHub topics")
    p.add_argument("--features", help="Comma-separated feature list")

    p.add_argument("--article-frontmatter", action="store_true", help="Generate article frontmatter")
    p.add_argument("--platform", default="devto", choices=["devto", "medium", "hashnode"], help="Platform for article")
    p.add_argument("--description", help="Article description/meta")

    p.add_argument("--all", action="store_true", help="Generate everything (Telegram post for product 1 + article frontmatter demo)")

    args = p.parse_args()

    if args.youtube:
        if not args.topic or not args.keywords:
            print("❌ --topic and --keywords required for --youtube")
            sys.exit(1)
        result = build_youtube_short(args.topic, args.keywords, args.hook, args.cta)
        print("📺 YouTube Shorts SEO Package")
        print(f"\n🎬 Title options (pick one):")
        for i, t in enumerate(result["title_options"], 1):
            print(f"  {i}. {t}")
        print(f"\n📝 Description:\n{result['description']}")
        print(f"\n🏷️  Tags ({len(result['tags'])}):")
        print(f"  {', '.join(result['tags'])}")
        print(f"\n#️⃣ Hashtags:")
        print(f"  {' '.join(result['hashtags_for_description'])}")

    if args.telegram:
        if not args.product:
            print("❌ --product N required for --telegram")
            sys.exit(1)
        print("\n✈️  Telegram post:\n")
        print(build_telegram_post(args.product, args.discount, args.offer_code, args.telegram_hook))

    if args.github_readme:
        if not args.slug or not args.title or not args.url:
            print("❌ --slug, --title, --url required for --github-readme")
            sys.exit(1)
        topics = [t.strip() for t in (args.topics or "").split(",") if t.strip()]
        features = [f.strip() for f in (args.features or "").split(",") if f.strip()]
        print("\n🐙 GitHub README:\n")
        print(build_github_readme(args.slug, args.title, args.url, args.summary, topics, features))

    if args.article_frontmatter:
        if not args.title or not args.keyword:
            print("❌ --title and --keyword required for --article-frontmatter")
            sys.exit(1)
        tags = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
        if not tags:
            tags = [args.keyword]
        print("\n📰 Article frontmatter (" + args.platform + "):\n")
        print(build_article_frontmatter(args.title, args.keyword, args.platform, args.description, tags))

    if args.all:
        print("📺 Demo: YouTube Short for 'psychology of motivation'")
        result = build_youtube_short("psychology of motivation", "psychology, motivation, dopamine, habits, productivity")
        print(f"  Title: {result['title_options'][0]}")
        print(f"  Tags: {', '.join(result['tags'][:5])}...")
        print("\n✈️  Demo: Telegram post for product 1")
        print(build_telegram_post(1))


if __name__ == "__main__":
    main()