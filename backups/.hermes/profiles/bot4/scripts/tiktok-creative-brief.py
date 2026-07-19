#!/usr/bin/env python3
"""TikTok Creative Brief Generator v1.0

Generates video scripts and creative briefs for TikTok Shop affiliate
content that complies with TikTok's policies while driving engagement.

Usage:
  ./tiktok-creative-brief.py --product "blue light glasses" --category electronics
  ./tiktok-creative-brief.py --list-formats
  ./tiktok-creative-brief.py --trending          # Current trending formats
"""
import sys, json, random

PRODUCT_CATEGORIES = {
    "beauty": {"commission": "15-25%", "styles": ["before-after", "tutorial", "review", "ingredient-deep-dive"]},
    "electronics": {"commission": "5-15%", "styles": ["unboxing", "comparison", "life-hack", "problem-solution"]},
    "home-living": {"commission": "10-20%", "styles": ["setup-tour", "aesthetic", "organization", "before-after"]},
    "fashion": {"commission": "10-20%", "styles": ["outfit-check", "styling-tips", "haul", "transformation"]},
    "health": {"commission": "10-20%", "styles": ["demo", "testimonial", "routine", "challenge"]},
    "food": {"commission": "8-15%", "styles": ["recipe", "hack", "taste-test", "cooking"]},
    "pet": {"commission": "10-18%", "styles": ["cute-clip", "product-try", "training-tip", "funny"]},
}

ENGAGEMENT_HOOKS = [
    "Stop scrolling if you [have this problem].",
    "I found THE thing that finally [solves this].",
    "This is your sign to finally [do the thing].",
    "I was skeptical until I tried this.",
    "Don't buy [product] until you watch this.",
    "The hack that changed everything for me.",
    "POV: You finally found something that works.",
    "This underrated find needs to go viral.",
    "I tested 5 products so you don't have to.",
    "The [category] you didn't know you needed.",
]

TIKTOK_POLICY_RULES = [
    "✅ MUST disclose if affiliate: use #ad #affiliate or Branded Content tag",
    "✅ Must be original content — no reposts or reused clips",
    "✅ Claims must be truthful — no 'guaranteed results' or medical claims",
    "✅ Thumbnail must accurately represent video content",
    "✅ Music must be from TikTok library or royalty-free",
    "✅ No misleading before/after edits — must be authentic",
    "✅ Must not target minors with age-restricted products",
    "✅ Price claims must be accurate (original price vs sale price)",
    "✅ No fake urgency ('limited stock' if untrue)",
    "✅ Product must be shown clearly — no hidden defects",
]

def generate_brief(product_name, category, price="", key_feature=""):
    """Generate a complete creative brief for one product."""
    cat_info = PRODUCT_CATEGORIES.get(category, {"commission": "5-20%", "styles": ["review", "demo", "unboxing", "tutorial"]})
    
    briefs = []
    for style in cat_info["styles"][:2]:  # 2 briefs per product
        hook = random.choice(ENGAGEMENT_HOOKS)
        
        # Structure based on style
        if style == "before-after":
            structure = [
                f"(0-2s) Hook: \"{hook}\" — apply 'before' filter/lighting",
                f"(2-5s) Before state: Show problem. Text overlay: \"Before I found this\"",
                f"(5-12s) Product reveal: Show product packaging + key features. Hold in frame.",
                f"(12-18s) After state: Show result/usage. Text overlay: \"After using it\"",
                f"(18-21s) Features: 3 quick cuts showing best features. Fast pace.",
                f"(21-24s) Price reveal: \"And it's only ${price}\" — show price on screen",
                f"(24-27s) CTA: \"Link in bio to grab yours\" + point gesture",
                f"(27-30s) End screen: Product name + #ad #affiliate #[category]",
            ]
        elif style == "review":
            structure = [
                f"(0-2s) Hook: \"{hook}\" — make eye contact with camera",
                f"(2-5s) Intro: \"I've been testing this for [X days] and here's my honest take\"",
                f"(5-12s) Product showcase: Hold product, show from all angles. Point out key feature: {key_feature}",
                f"(12-18s) What I love: 3 specific things. Fast cuts. Text overlay each point.",
                f"(18-21s) What could be better: 1 honest con (makes it more authentic)",
                f"(21-24s) Verdict: \"Do I recommend it? Yes/No — here's who it's for\"",
                f"(24-27s) Price/Value: Show price. Compare to alternatives if relevant.",
                f"(27-30s) CTA: \"Link in bio if you want to try it\" + #ad #honestreview",
            ]
        elif style == "problem-solution":
            structure = [
                f"(0-2s) Hook: \"Are you still [doing old way]? Stop.\"",
                f"(2-5s) Problem: Relatable pain point. \"This used to take me [X hours]\"",
                f"(5-8s) Discovery: \"Then I found this and everything changed\"",
                f"(8-15s) Solution: Show product solving the problem. Step by step.",
                f"(15-20s) Result: The outcome. Make it look effortless.",
                f"(20-24s) Why it works: Key feature explanation. Text overlay.",
                f"(24-27s) Value prop: Price + benefit summary.",
                f"(27-30s) CTA: \"Link in bio — game changer\" + #ad #affiliate",
            ]
        elif style == "tutorial":
            structure = [
                f"(0-2s) Hook: \"Let me show you how to [use this] in 30 seconds\"",
                f"(2-5s) Quick intro: \"This is [product] and it's actually simple\"",
                f"(5-15s) Step 1-2-3: Show the process. Quick cuts. Follow along feel.",
                f"(15-20s) Result: The finished state. Looks clean and satisfying.",
                f"(20-24s) Key tip: \"Pro tip: [undervalued feature] — most people miss this\"",
                f"(24-27s) Where to get: \"Link in bio — comes with [bonus]\"",
                f"(27-30s) CTA: \"Follow for more [category] tips\" + tag product in video",
            ]
        elif style == "comparison":
            structure = [
                f"(0-2s) Hook: \"I compared [product] vs [alternative] — the results surprised me\"",
                f"(2-6s) Setup: Show both products side by side. \"Left is [priceA], right is [priceB]\"",
                f"(6-15s) Compare features: 3 quick comparisons. Winner gets checkmark overlay.",
                f"(15-20s) Winner reveal: \"So which one won?\" Dramatic pause.",
                f"(20-24s) Why: Explain why winner beats the alternative.",
                f"(24-27s) Price check: Show price comparison clearly on screen.",
                f"(27-30s) CTA: \"Link in bio for the winner\" + #comparison #ad",
            ]
        else:
            structure = [
                f"(0-2s) Hook: \"{hook}\"",
                f"(2-7s) Intro: Show product in natural setting",
                f"(7-15s) Features: Highlight 3 key features with demonstrations",
                f"(15-22s) Usage: Show someone using the product naturally",
                f"(22-27s) Value: Price + why it's worth it",
                f"(27-30s) CTA: \"Link in bio\" + #ad #[category]",
            ]
        
        briefs.append({
            "style": style.replace("-", " ").title(),
            "hook": hook,
            "structure": structure,
            "policy_checklist": TIKTOK_POLICY_RULES,
        })
    
    return briefs

def generate_full_brief(product_name, category, price="", key_feature=""):
    """Generate a full printable creative brief."""
    cat_info = PRODUCT_CATEGORIES.get(category, {"commission": "5-20%", "styles": ["review"]})
    briefs = generate_brief(product_name, category, price, key_feature)
    
    print(f"""
╔══════════════════════════════════════════════╗
║  🎬 TIKTOK CREATIVE BRIEF                    ║
╠══════════════════════════════════════════════╣
║  Product: {product_name:<45}║
║  Category: {category:<44}║
║  Est. Commission: {cat_info['commission']:<36}║
╚══════════════════════════════════════════════╝

📋 TIKTOK POLICY CHECKLIST (MUST READ BEFORE FILMING)""")
    for rule in TIKTOK_POLICY_RULES:
        print(f"  {rule}")
    
    for brief in briefs:
        print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 FORMAT: {brief['style']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 Hook: "{brief['hook']}"

⏱  SCRIPT TIMELINE (30s):""")
        for line in brief['structure']:
            print(f"  {line}")
        
        print(f"""
✅ COMPLIANCE CHECK:
  • Affiliate disclosure in video description
  • No false or misleading claims
  • Original content — not repurposed
  • Music from TikTok library
  • Thumbnail matches content

🏷️  RECOMMENDED HASHTAGS:
  #ad #affiliate #{category} #TikTokMadeMeBuyIt #{category.replace(' ','')}
  #productreview #honestreview #[product_name.replace(' ','')]""")
    
    print(f"""
📊 POSTING RECOMMENDATIONS:
  Post time: Mon-Thu 7-9pm SG time
  First 2 hours critical for algorithm
  Respond to ALL comments in first hour
  Do NOT delete and repost if low views
  Use trending sounds from TikTok discover page""")

def list_formats():
    """List all available video formats."""
    print("🎬 AVAILABLE VIDEO FORMATS\n")
    for cat, info in PRODUCT_CATEGORIES.items():
        print(f"  {cat.upper()} ({info['commission']} commission)")
        for style in info['styles']:
            print(f"    • {style.replace('-', ' ').title()}")
    print()
    
    print("🔥 ENGAGEMENT HOOK TEMPLATES:")
    for h in ENGAGEMENT_HOOKS:
        print(f"  • {h}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if sys.argv[1] == "--product" and len(sys.argv) > 2:
        name = sys.argv[2]
        cat = sys.argv[4] if len(sys.argv) > 4 else "electronics"
        if "--category" in sys.argv:
            cat = sys.argv[sys.argv.index("--category") + 1]
        price = ""
        if "--price" in sys.argv:
            price = sys.argv[sys.argv.index("--price") + 1]
        feature = ""
        if "--feature" in sys.argv:
            feature = sys.argv[sys.argv.index("--feature") + 1]
        generate_full_brief(name, cat, price, feature)
    elif sys.argv[1] == "--list-formats":
        list_formats()
    elif sys.argv[1] == "--trending":
        print("🔥 CURRENT TRENDING FORMATS (July 2026):")
        print("  1. 'I found this on TikTok Shop' — Discovery format")
        print("  2. Honest Review — 'I tested this for X days'")
        print("  3. Before/After — Transformation content")
        print("  4. Problem/Solution — 'Stop doing X'")
        print("  5. Quick Tutorial — 'Let me show you in 30s'")
        print("  6. Comparison — 'This vs That'")
        print("  7. 'Underrated find' — Hidden gem angle")
        print("  8. ASMR unboxing — Satisfying product reveal")
    else:
        print(__doc__)
