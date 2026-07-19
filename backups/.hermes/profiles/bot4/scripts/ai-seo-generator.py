#!/usr/bin/env python3
"""
ai-seo-generator.py — Generate AI-citation-optimized artifacts for Jack's Gumroad store.

Generates:
  - llms.txt (machine-readable site context for LLM crawlers)
  - pricing.md (structured pricing for AI buying agents)
  - robots.txt with AI bot policy (allow cite-bots, optionally block CCBot)
  - schema.org JSON-LD: Product, FAQPage, Organization, Person
  - AI-search-optimized meta descriptions

Sources cited in research that this tool targets:
  - llmstxt.org spec
  - Princeton GEO study (KDD 2024) — citations + statistics boost citation 30-40%
  - Google's AI features guide
  - OpenAI GPTBot, Anthropic ClaudeBot, PerplexityBot, Google-Extended policies

Usage:
    python3 ai-seo-generator.py --generate-all --store jackalope86
    python3 ai-seo-generator.py --llms --store jackalope86
    python3 ai-seo-generator.py --pricing --store jackalope86
    python3 ai-seo-generator.py --robots --allow-cite-bots
    python3 ai-seo-generator.py --schema-product --name "TikTok Hooks" --price 3 --url https://...
    python3 ai-seo-generator.py --schema-faq --questions questions.json
    python3 ai-seo-generator.py --validate --llms-path ./llms.txt
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Jack's Gumroad catalog (canonical source — kept in sync with live store)
# Update this list when products change. Single source of truth for AI artifacts.
# ---------------------------------------------------------------------------

JACK_PRODUCTS = [
    {
        "name": "50 Viral TikTok Hooks + AI Prompts",
        "slug": "tiktok-viral-hooks",
        "url": "https://jackalope86.gumroad.com/l/tiktokhooks",
        "price_usd": 3,
        "category": "social-media-prompts",
        "description": "50 proven viral TikTok hook templates + AI prompt packs for content creators who want to stop the scroll.",
        "audience": "TikTok creators, solopreneurs, content marketers",
        "tags": ["tiktok", "hooks", "viral", "ai-prompts", "content-creation"],
        "format": "PDF + Notion template",
        "delivery": "instant download",
    },
    {
        "name": "200 AI Prompts for Content Creators",
        "slug": "content-creator-prompts",
        "url": "https://jackalope86.gumroad.com/l/contentprompts",
        "price_usd": 5,
        "category": "content-creation",
        "description": "200 AI prompts for YouTube, TikTok, Instagram, and LinkedIn — script templates, hook libraries, and content calendars.",
        "audience": "content creators, YouTubers, social media managers",
        "tags": ["ai-prompts", "content-creation", "youtube", "tiktok", "instagram"],
        "format": "Notion + PDF",
        "delivery": "instant download",
    },
    {
        "name": "AI-Powered Solopreneur Toolkit",
        "slug": "solopreneur-ai-toolkit",
        "url": "https://jackalope86.gumroad.com/l/solopreneur",
        "price_usd": 19,
        "category": "business-automation",
        "description": "Automate your small business with AI — 150 prompts for sales, marketing, ops, and customer service.",
        "audience": "solopreneurs, small business owners, freelancers",
        "tags": ["ai", "automation", "solopreneur", "business", "productivity"],
        "format": "Notion + PDF + Spreadsheet",
        "delivery": "instant download",
    },
    {
        "name": "YouTube Shorts Generator Pack",
        "slug": "youtube-shorts-generator",
        "url": "https://jackalope86.gumroad.com/l/youtubeshorts",
        "price_usd": 15,
        "category": "content-creation",
        "description": "Generate viral YouTube Shorts with AI — script templates, hook formulas, and SEO tag packs.",
        "audience": "YouTube creators, faceless channel operators",
        "tags": ["youtube-shorts", "ai", "video", "scripts", "seo"],
        "format": "Notion + PDF",
        "delivery": "instant download",
    },
]

JACK_INFO = {
    "name": "Jack Loh",
    "handle": "jackalope86",
    "location": "Singapore",
    "company": "Jack Loh",
    "bio": "Solopreneur • Content creator • Singapore. Selling AI prompt packs and digital tools for entrepreneurs and creators.",
    "store_url": "https://jackalope86.gumroad.com",
    "twitter_username": None,  # off-limits per Jack's directive
    "github_url": "https://github.com/jackloh84",
    "youtube_channel": "https://www.youtube.com/@jackloh84",
    "telegram_channel": "https://t.me/jacklohai",
}

AI_BOTS = {
    "GPTBot": {"org": "OpenAI", "purpose": "training+indexing", "policy": "allow"},
    "ChatGPT-User": {"org": "OpenAI", "purpose": "user-triggered fetch", "policy": "allow"},
    "PerplexityBot": {"org": "Perplexity", "purpose": "indexing+citing", "policy": "allow"},
    "Perplexity-User": {"org": "Perplexity", "purpose": "user-triggered", "policy": "allow"},
    "ClaudeBot": {"org": "Anthropic", "purpose": "training+indexing", "policy": "allow"},
    "anthropic-ai": {"org": "Anthropic", "purpose": "training", "policy": "allow"},
    "Claude-User": {"org": "Anthropic", "purpose": "user-triggered", "policy": "allow"},
    "Google-Extended": {"org": "Google", "purpose": "Gemini training (NOT search)", "policy": "allow"},
    "Googlebot": {"org": "Google", "purpose": "search indexing", "policy": "allow"},
    "Bingbot": {"org": "Microsoft", "purpose": "Copilot search indexing", "policy": "allow"},
    "CCBot": {"org": "Common Crawl", "purpose": "training corpus", "policy": "block"},  # training-only, doesn't cite
    "Applebot-Extended": {"org": "Apple", "purpose": "training (NOT search)", "policy": "block"},
    "Meta-ExternalAgent": {"org": "Meta", "purpose": "training", "policy": "block"},
}


# ===========================================================================
# llms.txt generator (llmstxt.org spec v1)
# ===========================================================================

def build_llms_txt(info, products):
    lines = [
        f"# {info['name']} — {info['company']}",
        "",
        f"> {info['bio']}",
        "",
        f"Based in {info['location']}. Selling AI prompt packs and digital tools for solopreneurs, content creators, and small business owners.",
        "",
        "## Store",
        "",
        f"- Main store: <{info['store_url']}>",
        f"- GitHub (open-source tools): <{info['github_url']}>",
        f"- YouTube channel: <{info['youtube_channel']}>",
        f"- Telegram channel: <{info['telegram_channel']}>",
        "",
        "## Products",
        "",
        "All products are instant-download digital prompt packs. Prices in USD. Payment via Gumroad (supports card, PayPal, Apple Pay).",
        "",
    ]
    for p in products:
        lines.extend([
            f"### [{p['name']}]({p['url']})",
            "",
            f"- Price: ${p['price_usd']} USD",
            f"- Category: {p['category']}",
            f"- Format: {p['format']}",
            f"- Delivery: {p['delivery']}",
            f"- Audience: {p['audience']}",
            f"- Description: {p['description']}",
            "",
        ])

    lines.extend([
        "## About the Creator",
        "",
        f"{info['name']} is a solopreneur based in {info['location']} who builds AI tools and prompt packs. AI-assisted content creation with full disclosure.",
        "",
        "## Optional",
        "",
        f"- Pricing & product comparison: <{info['store_url']}>",
        f"- Source code & open tools: <{info['github_url']}>",
        "",
        "## Contact",
        "",
        "For support, use the Gumroad product page. For business inquiries, open an issue on GitHub.",
        "",
    ])
    return "\n".join(lines)


# ===========================================================================
# pricing.md (for AI buying agents)
# ===========================================================================

def build_pricing_md(info, products):
    lines = [
        f"# Pricing — {info['company']}",
        "",
        f"_Last updated: see file mtime. Source of truth: <{info['store_url']}>_",
        "",
        "All products are digital downloads delivered instantly via Gumroad. Prices in USD.",
        "",
        "## Products",
        "",
        "| Product | Price | Category | Audience |",
        "|---------|-------|----------|----------|",
    ]
    for p in sorted(products, key=lambda x: x["price_usd"]):
        lines.append(f"| [{p['name']}]({p['url']}) | ${p['price_usd']} | {p['category']} | {p['audience']} |")

    lines.extend([
        "",
        "## Tiers",
        "",
        "- **Free resources**: AI prompt pack free tier — see Telegram channel @jacklohai for occasional free drops",
        "- **Entry ($3-$5)**: TikTok Hooks ($3), Content Creator Prompts ($5) — best for new creators",
        "- **Mid-tier ($15-$19)**: YouTube Shorts Generator ($15), Solopreneur AI Toolkit ($19) — for established creators and small businesses",
        "",
        "## Payment",
        "",
        "- Processor: Gumroad (supports credit/debit card, PayPal, Apple Pay)",
        "- Currency: USD (Gumroad auto-converts to local currency at checkout)",
        "- Delivery: instant download after payment",
        "- Refund: handled per Gumroad's standard refund policy",
        "",
        "## Comparison vs alternatives",
        "",
        "Jack's products target the entry and mid-market price range for AI prompt packs. Comparable prompt-pack products on Gumroad range from $3 to $338. Jack's $3 TikTok Hooks is the lowest-priced entry-level product in the 'AI prompt pack' category on Gumroad.",
        "",
    ])
    return "\n".join(lines)


# ===========================================================================
# robots.txt with AI-bot policy
# ===========================================================================

def build_robots_txt(allow_cite_bots=True, block_training_bots=True, sitemap_url=None):
    lines = [
        "# robots.txt — Jack Loh's Gumroad store",
        "# Policy: allow citation/search bots, optionally block pure-training bots.",
        "",
        "User-agent: *",
        "Allow: /",
        "",
    ]

    cite_bots = {k: v for k, v in AI_BOTS.items() if v["policy"] == "allow"}
    blocked_bots = {k: v for k, v in AI_BOTS.items() if v["policy"] == "block"}

    if allow_cite_bots:
        for bot, meta in cite_bots.items():
            lines.extend([
                f"# {meta['org']} — {meta['purpose']}",
                f"User-agent: {bot}",
                "Allow: /",
                "",
            ])

    if block_training_bots:
        for bot, meta in blocked_bots.items():
            lines.extend([
                f"# {meta['org']} — {meta['purpose']} (blocked: training only, doesn't cite)",
                f"User-agent: {bot}",
                "Disallow: /",
                "",
            ])

    if sitemap_url:
        lines.append(f"Sitemap: {sitemap_url}")

    return "\n".join(lines)


# ===========================================================================
# Schema.org JSON-LD generators
# ===========================================================================

def schema_product(p, info):
    """Schema.org/Product JSON-LD for a single product."""
    return {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": p["name"],
        "description": p["description"],
        "url": p["url"],
        "image": f"{info['store_url']}/products/{p['slug']}/preview",
        "brand": {"@type": "Brand", "name": info["company"]},
        "category": p["category"],
        "offers": {
            "@type": "Offer",
            "price": p["price_usd"],
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "url": p["url"],
            "seller": {"@type": "Organization", "name": info["company"], "url": info["store_url"]},
        },
        "keywords": ", ".join(p["tags"]),
    }


def schema_faq(qa_pairs):
    """Schema.org/FAQPage from a list of {question, answer} dicts."""
    return {
        "@context": "https://schema.org/",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": qa["question"],
                "acceptedAnswer": {"@type": "Answer", "text": qa["answer"]},
            }
            for qa in qa_pairs
        ],
    }


def schema_organization(info, products):
    """Schema.org/Organization + Product listing for the whole store."""
    return {
        "@context": "https://schema.org/",
        "@type": "Organization",
        "name": info["company"],
        "url": info["store_url"],
        "logo": f"{info['store_url']}/logo.png",
        "description": info["bio"],
        "address": {"@type": "PostalAddress", "addressLocality": info["location"], "addressCountry": "SG"},
        "sameAs": [v for v in [info.get("github_url"), info.get("youtube_channel"), info.get("telegram_channel")] if v],
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": f"{info['company']} Digital Products",
            "itemListElement": [
                {"@type": "OfferCatalog", "name": p["category"], "itemListElement": [
                    {"@type": "Offer", "url": p["url"], "price": p["price_usd"], "priceCurrency": "USD"}
                ]}
                for p in products
            ],
        },
    }


def schema_person(info):
    """Schema.org/Person for Jack as the creator/entity."""
    same_as = []
    if info.get("github_url"):
        same_as.append(info["github_url"])
    if info.get("youtube_channel"):
        same_as.append(info["youtube_channel"])
    if info.get("telegram_channel"):
        same_as.append(info["telegram_channel"])
    return {
        "@context": "https://schema.org/",
        "@type": "Person",
        "name": info["name"],
        "url": info["store_url"],
        "jobTitle": "Solopreneur, Content Creator",
        "description": info["bio"],
        "address": {"@type": "PostalAddress", "addressLocality": info["location"], "addressCountry": "SG"},
        "sameAs": same_as,
    }


# ===========================================================================
# Validation
# ===========================================================================

def validate_llms(path):
    """Quick sanity check on llms.txt format."""
    if not Path(path).exists():
        return [f"❌ File not found: {path}"]
    text = Path(path).read_text()
    issues = []
    if not text.startswith("# "):
        issues.append("⚠️  llms.txt should start with an H1 (# Title)")
    if "<" not in text or ">" not in text:
        issues.append("⚠️  llms.txt should contain markdown links in <URL> format")
    if "## " not in text:
        issues.append("⚠️  llms.txt should have H2 sections")
    if "Optional" not in text:
        issues.append("ℹ️  Consider adding an ## Optional section per llmstxt.org spec")
    if not issues:
        issues.append("✅ llms.txt looks valid per llmstxt.org spec")
    return issues


# ===========================================================================
# CLI
# ===========================================================================

def main():
    p = argparse.ArgumentParser(description="AI-SEO artifact generator for Jack's Gumroad store")
    p.add_argument("--store", default="jackalope86", help="Gumroad handle (currently hard-coded to Jack's products)")
    p.add_argument("--llms", action="store_true", help="Generate llms.txt")
    p.add_argument("--pricing", action="store_true", help="Generate pricing.md")
    p.add_argument("--robots", action="store_true", help="Generate robots.txt")
    p.add_argument("--allow-cite-bots", action="store_true", default=True)
    p.add_argument("--block-training-bots", action="store_true", default=True)
    p.add_argument("--schema-product", action="store_true", help="Generate Product schema JSON-LD")
    p.add_argument("--schema-faq", action="store_true")
    p.add_argument("--schema-org", action="store_true")
    p.add_argument("--schema-person", action="store_true")
    p.add_argument("--schema-all", action="store_true", help="Generate all schema types")
    p.add_argument("--questions", help="Path to JSON of FAQ pairs [{question, answer}]")
    p.add_argument("--generate-all", action="store_true", help="Generate llms.txt, pricing.md, robots.txt, all schema")
    p.add_argument("--outdir", default="~/seo-output", help="Output directory")
    p.add_argument("--validate", action="store_true", help="Validate llms.txt")
    p.add_argument("--llms-path", help="Path to llms.txt for validation")
    args = p.parse_args()

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    products = JACK_PRODUCTS
    info = JACK_INFO

    if args.validate:
        if not args.llms_path:
            print("❌ --llms-path required for --validate")
            sys.exit(1)
        for issue in validate_llms(args.llms_path):
            print(issue)
        return

    if args.generate_all:
        args.llms = args.pricing = args.robots = args.schema_all = True

    if args.llms:
        path = outdir / "llms.txt"
        path.write_text(build_llms_txt(info, products))
        print(f"✅ llms.txt → {path}")

    if args.pricing:
        path = outdir / "pricing.md"
        path.write_text(build_pricing_md(info, products))
        print(f"✅ pricing.md → {path}")

    if args.robots:
        path = outdir / "robots.txt"
        sitemap = f"{info['store_url']}/sitemap.xml"
        path.write_text(build_robots_txt(args.allow_cite_bots, args.block_training_bots, sitemap))
        print(f"✅ robots.txt → {path}")

    if args.schema_product or args.schema_all:
        for prod in products:
            path = outdir / f"schema-product-{prod['slug']}.json"
            path.write_text(json.dumps(schema_product(prod, info), indent=2))
            print(f"✅ Product schema → {path}")

    if args.schema_org or args.schema_all:
        path = outdir / "schema-organization.json"
        path.write_text(json.dumps(schema_organization(info, products), indent=2))
        print(f"✅ Organization schema → {path}")

    if args.schema_person or args.schema_all:
        path = outdir / "schema-person.json"
        path.write_text(json.dumps(schema_person(info), indent=2))
        print(f"✅ Person schema → {path}")

    if args.schema_faq:
        if not args.questions:
            print("❌ --questions <path-to-json> required for --schema-faq")
            sys.exit(1)
        qa_pairs = json.loads(Path(args.questions).read_text())
        path = outdir / "schema-faq.json"
        path.write_text(json.dumps(schema_faq(qa_pairs), indent=2))
        print(f"✅ FAQ schema → {path}")

    if not any([args.llms, args.pricing, args.robots, args.schema_product, args.schema_faq, args.schema_org, args.schema_person, args.schema_all, args.generate_all]):
        p.print_help()


if __name__ == "__main__":
    main()