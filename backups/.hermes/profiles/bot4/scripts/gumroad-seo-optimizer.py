#!/usr/bin/env python3
"""
Gumroad SEO Analyzer & Optimizer
=================================
Helps optimize Gumroad product listings for search visibility.
No external API dependencies — pure Python with SEO best practices for digital products.

Modes:
  --analyze   Score an existing product listing (0-100) with recommendations
  --generate  Create SEO-optimized product assets (HTML description, tags, meta)

Args:
  --name      Product name / title
  --desc      Product description (plain text or partial HTML)
  --tags      Comma-separated tags
  --price     Price (e.g., "3", "$5", "SGD$19")
  --category  Product category

Supported products (presets auto-filled when --name matches):
  - "TikTok Hooks"           -> $3   | social-media-prompts
  - "Content Creators Vol 2" -> SGD$19 | content-creation
  - "Biz Automation"         -> SGD$19 | business-automation
  - "Solopreneur Launchpad"  -> $5   | solopreneur
"""

import argparse
import math
import re
import sys
import textwrap

# ──────────────────────────────────────────────────────────────────────
#  CONSTANTS - SEO guidelines, category data, and product presets
# ──────────────────────────────────────────────────────────────────────

CATEGORIES = {
    "social-media-prompts": {
        "label": "Social Media Prompts",
        "keywords": [
            "viral content", "social media templates", "hook ideas",
            "engagement prompts", "content calendar", "captions",
            "social strategy", "trending topics", "short-form video",
            "TikTok growth", "Instagram Reels", "video scripts",
        ],
        "competitor_tags": [
            "social media", "content", "templates", "viral", "hooks",
            "prompts", "captions", "growth", "marketing", "video",
        ],
        "description_angle": ("Stop staring at a blank screen. Get proven social media prompts "
                              "that drive engagement and save hours every week."),
        "ideal_title_length": (40, 70),
        "min_tags": 5,
        "max_tags": 10,
    },
    "content-creation": {
        "label": "Content Creation",
        "keywords": [
            "content creation", "digital assets", "creator tools",
            "editing templates", "content pack", "graphic design",
            "brand assets", "social media kit", "content planner",
            "batch creation", "audio assets", "visual templates",
        ],
        "competitor_tags": [
            "content", "creation", "templates", "assets", "design",
            "creator", "digital", "pack", "tools", "editing",
        ],
        "description_angle": ("Everything you need to create scroll-stopping content - "
                              "templates, assets, and workflows built for creators who value their time."),
        "ideal_title_length": (40, 70),
        "min_tags": 5,
        "max_tags": 10,
    },
    "business-automation": {
        "label": "Business Automation",
        "keywords": [
            "business automation", "workflow automation", "AI tools",
            "productivity system", "process optimization", "SOP templates",
            "automation tools", "efficiency hacks", "business systems",
            "no-code automation", "task management", "lead generation",
        ],
        "competitor_tags": [
            "automation", "business", "productivity", "workflow",
            "efficiency", "tools", "SOP", "systems", "AI", "growth",
        ],
        "description_angle": ("Automate the busywork. Deploy battle-tested workflows "
                              "that save 10+ hours a week and scale your business without burning out."),
        "ideal_title_length": (45, 75),
        "min_tags": 5,
        "max_tags": 10,
    },
    "solopreneur": {
        "label": "Solopreneur",
        "keywords": [
            "solopreneur tools", "one-person business", "side hustle",
            "passive income", "digital products", "online business",
            "entrepreneur toolkit", "business starter pack",
            "micro business", "freelance resources", "startup kit",
            "low-cost business", "profit system",
        ],
        "competitor_tags": [
            "solopreneur", "business", "startup", "tools", "kit",
            "entrepreneur", "digital", "income", "passive", "launch",
        ],
        "description_angle": ("Built for the solo operator. Launch, grow, and scale "
                              "your one-person business with tools and systems that actually work."),
        "ideal_title_length": (40, 70),
        "min_tags": 5,
        "max_tags": 10,
    },
}

PRODUCT_PRESETS = {
    "tiktok hooks": {
        "name": "TikTok Hooks Pack",
        "price": "$3",
        "category": "social-media-prompts",
        "suggested_tags": [
            "TikTok hooks", "viral hooks", "content prompts",
            "video scripts", "social media", "engagement",
        ],
        "meta_description": (
            "100+ proven TikTok hooks to stop the scroll and boost engagement. "
            "Ready-to-use viral hooks for creators, marketers, and businesses."
        ),
    },
    "content creators vol 2": {
        "name": "Content Creators Vol 2",
        "price": "SGD$19",
        "category": "content-creation",
        "suggested_tags": [
            "content pack", "creator tools", "digital assets",
            "social templates", "batch content", "brand kit",
        ],
        "meta_description": (
            "Volume 2 of the ultimate content creation toolkit - templates, audio assets, "
            "and workflows for creators who want to produce faster and better."
        ),
    },
    "biz automation": {
        "name": "Biz Automation Toolkit",
        "price": "SGD$19",
        "category": "business-automation",
        "suggested_tags": [
            "automation tools", "business systems", "workflow",
            "productivity", "AI tools", "efficiency",
        ],
        "meta_description": (
            "10+ ready-to-deploy automation workflows for your business. "
            "Save 10+ hours a week with AI-powered systems optimized for growth."
        ),
    },
    "solopreneur launchpad": {
        "name": "Solopreneur Launchpad",
        "price": "$5",
        "category": "solopreneur",
        "suggested_tags": [
            "solopreneur", "business starter", "launch kit",
            "digital tools", "side hustle", "passive income",
        ],
        "meta_description": (
            "Everything a solo founder needs to launch, grow, and monetize "
            "their first digital product. Low-cost, high-impact starter kit."
        ),
    },
}

HTML_DESC_TEMPLATES = {
    "social-media-prompts": """<p><strong>{angle}</strong></p>

<h3>What's Inside</h3>
<ul>
<li><strong>100+ Scroll-Stopping Hooks</strong> - Proven openers for TikTok, Reels, and Shorts that grab attention in under 2 seconds</li>
<li><strong>Engagement Prompts</strong> - Questions, challenges, and CTAs that drive comments, shares, and saves</li>
<li><strong>Content Calendar Template</strong> - Plan 30 days of posts in under an hour with our done-for-you framework</li>
<li><strong>Niche-Specific Variations</strong> - Tailored hooks for e-commerce, education, entertainment, and B2B</li>
<li><strong>Bonus: Caption Library</strong> - 50+ proven captions optimized for the algorithm</li>
</ul>

<h3>Why This Works</h3>
<p>Every hook and prompt in this pack has been tested against real engagement data. We have analyzed thousands of viral posts to find the patterns that consistently win - then packaged them so you can copy-paste your way to growth.</p>

<h3>Perfect For</h3>
<ul>
<li>Social media managers juggling multiple accounts</li>
<li>Content creators who post daily</li>
<li>Business owners who want organic reach without paid ads</li>
<li>Agency owners scaling content production</li>
</ul>

<h3>What You Get</h3>
<ul>
<li>1 PDF guide with all 100+ hooks organized by category</li>
<li>1 Notion template for your content calendar</li>
<li>1 CSV with ready-to-use caption bank</li>
<li>Lifetime access + free updates</li>
</ul>

<p><em>Instant download after purchase. No watermark, no branding - just done-for-you assets.</em></p>""",
    "content-creation": """<p><strong>{angle}</strong></p>

<h3>What's Inside</h3>
<ul>
<li><strong>Professional Templates</strong> - Ready-to-use designs for social posts, stories, thumbnails, and banners</li>
<li><strong>Audio Asset Pack</strong> - Royalty-free sound effects, transitions, and background tracks</li>
<li><strong>Batch Creation Workflow</strong> - Produce 2 weeks of content in a single session with our system</li>
<li><strong>Brand Identity Guide</strong> - Keep your visuals consistent across every platform</li>
<li><strong>Bonus: Analytics Tracker</strong> - Measure what is working and double down</li>
</ul>

<h3>Why This Works</h3>
<p>Volume 2 builds on everything creators loved about the first pack - more templates, deeper workflows, and assets that actually match today's platform trends. No fluff, no filler, just production-ready tools.</p>

<h3>Perfect For</h3>
<ul>
<li>Full-time creators and influencers</li>
<li>Video editors and motion designers</li>
<li>Social media teams at startups and agencies</li>
<li>Anyone who wants to create faster without sacrificing quality</li>
</ul>

<h3>What You Get</h3>
<ul>
<li>50+ design templates (Figma + Canva)</li>
<li>30 audio assets (WAV + MP3)</li>
<li>1 batch production playbook (PDF)</li>
<li>1 brand identity workbook (Notion)</li>
<li>Lifetime access + free Volume 2 updates</li>
</ul>

<p><em>Instant download after purchase. Compatible with all major editing software.</em></p>""",
    "business-automation": """<p><strong>{angle}</strong></p>

<h3>What's Inside</h3>
<ul>
<li><strong>10+ Pre-Built Automation Workflows</strong> - Lead capture, email sequences, invoicing, CRM sync, and more - ready to deploy</li>
<li><strong>AI Prompt Library</strong> - ChatGPT and Claude prompts for sales copy, customer support, and content generation</li>
<li><strong>SOP Templates</strong> - Standard operating procedures for every recurring business task</li>
<li><strong>Integration Recipes</strong> - Zapier/Make blueprints connecting your tools without code</li>
<li><strong>Bonus: Automation Audit Checklist</strong> - Find 10+ hours of hidden manual work in your current setup</li>
</ul>

<h3>Why This Works</h3>
<p>Each workflow has been built and tested in real businesses. We don't sell theory - we sell systems that have already saved founders 10-20 hours a week. Set them up once, and they run forever.</p>

<h3>Perfect For</h3>
<ul>
<li>Solopreneurs wearing every hat</li>
<li>Small business owners scaling without hiring</li>
<li>Consultants automating client delivery</li>
<li>Anyone tired of repetitive manual tasks</li>
</ul>

<h3>What You Get</h3>
<ul>
<li>10 automation blueprints (PDF + video walkthroughs)</li>
<li>50+ AI prompts organized by business function</li>
<li>20 SOP templates (Google Docs + Notion)</li>
<li>5 Zapier/Make integration recipes</li>
<li>Lifetime access + quarterly workflow updates</li>
</ul>

<p><em>Instant download. Works with tools you already use - Gmail, Notion, Slack, Stripe, and more.</em></p>""",
    "solopreneur": """<p><strong>{angle}</strong></p>

<h3>What's Inside</h3>
<ul>
<li><strong>Launch Checklist</strong> - Go from idea to first sale in 7 days with our step-by-step roadmap</li>
<li><strong>Product Planning Workbook</strong> - Validate your idea, define your audience, and price with confidence</li>
<li><strong>Marketing Starter Kit</strong> - Landing page copy, email sequences, and social posts ready to customize</li>
<li><strong>Operations Hub</strong> - Templates for finance tracking, client management, and content scheduling</li>
<li><strong>Bonus: Growth Experiments Log</strong> - Track what works and scale your winners</li>
</ul>

<h3>Why This Works</h3>
<p>Built by a solopreneur for solopreneurs. Every template, checklist, and system in this kit was created while building a real one-person business to five figures. No corporate jargon, no fluff - just what actually works.</p>

<h3>Perfect For</h3>
<ul>
<li>First-time digital product creators</li>
<li>Side hustlers ready to go full-time</li>
<li>Freelancers building a product business</li>
<li>Anyone who wants to start a business for under $10</li>
</ul>

<h3>What You Get</h3>
<ul>
<li>Launch roadmap (7-day timeline, PDF)</li>
<li>Product validation workbook (Notion)</li>
<li>Marketing templates (copy + graphics)</li>
<li>Operations templates (finance + scheduling)</li>
<li>Growth experiments log (spreadsheet)</li>
<li>Lifetime access + free updates</li>
</ul>

<p><em>Instant download. All templates work in free tools - Notion, Google Docs, and Canva.</em></p>""",
}


# ──────────────────────────────────────────────────────────────────────
#  SEO ANALYSIS ENGINE
# ──────────────────────────────────────────────────────────────────────

def analyze_title(name: str, category: str) -> dict:
    """Score the product title against SEO best practices."""
    score = 0
    max_score = 25
    issues = []
    wins = []

    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])
    ideal_min, ideal_max = cat["ideal_title_length"]

    length = len(name) if name else 0

    # Length check
    if ideal_min <= length <= ideal_max:
        score += 10
        wins.append("Title length (%d chars) is in the ideal range (%d-%d)"
                     % (length, ideal_min, ideal_max))
    elif length < ideal_min:
        score += 3
        issues.append("Title is too short (%d chars). Aim for %d-%d chars (%d more needed)"
                       % (length, ideal_min, ideal_max, ideal_min - length))
    else:
        score += 2
        issues.append("Title is too long (%d chars). Shorten to %d-%d chars (%d to cut)"
                       % (length, ideal_min, ideal_max, length - ideal_max))

    # Keyword presence in title
    title_lower = name.lower() if name else ""
    found_keywords = []
    for kw in cat["keywords"]:
        for word in kw.split():
            if word in title_lower:
                found_keywords.append(kw)
                break
    if found_keywords:
        bonus = min(len(found_keywords), 5)
        score += bonus * 2
        wins.append("Title contains %d relevant keyword(s): %s"
                     % (len(found_keywords), ", ".join(found_keywords[:3])))
    else:
        issues.append("Title contains no category-relevant keywords. "
                       "Add a key phrase users search for")

    # Has a number (listicle style tends to perform better)
    if re.search(r'\d+', name or ""):
        score += 3
        wins.append("Title includes a number - list-style titles tend to get higher CTR")

    # Capitalization quality
    words = (name or "").split()
    capped = sum(1 for w in words if w and w[0].isupper())
    if len(words) > 0 and capped >= len(words) * 0.7:
        score += 2
        wins.append("Title uses proper title capitalization")
    elif len(words) > 0 and capped == 0:
        issues.append("Title is all lowercase - use title case for better readability")

    return {"score": min(score, max_score), "max": max_score, "issues": issues, "wins": wins}


def analyze_description(desc: str, category: str) -> dict:
    """Score the product description against SEO best practices."""
    score = 0
    max_score = 35
    issues = []
    wins = []

    if not desc:
        return {"score": 0, "max": max_score,
                "issues": ["No description provided - this is critical"], "wins": []}

    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])
    desc_lower = desc.lower()

    # Length check (aim for 300+ words for rich descriptions)
    word_count = len(desc.split())
    if word_count >= 300:
        score += 8
        wins.append("Description is substantial (%d words) - great for SEO" % word_count)
    elif word_count >= 150:
        score += 5
        wins.append("Description is decent (%d words). 300+ is ideal" % word_count)
    else:
        score += max(0, word_count // 30)
        issues.append("Description is thin (%d words). Aim for at least 300" % word_count)

    # HTML structure
    has_heading = bool(re.search(r'<h[2-6]', desc))
    has_list = bool(re.search(r'<[uo]l', desc))
    has_li = bool(re.search(r'<li', desc))
    has_strong = bool(re.search(r'<(strong|b)>', desc))
    has_para = bool(re.search(r'<p>', desc))

    html_score = 0
    if has_heading:
        html_score += 3
        wins.append("Description uses headings (H2/H3) - helps SEO and readability")
    else:
        issues.append("No headings found. Use <h2>/<h3> tags to structure your description")
    if has_list:
        html_score += 3
        wins.append("Description uses lists - improves scannability and dwell time")
    else:
        issues.append("No lists found. Bullet points improve readability and CTR")
    if has_strong:
        html_score += 2
        wins.append("Description uses bold text - highlights key benefits")
    if has_para:
        html_score += 1
        wins.append("Description uses paragraph tags - proper HTML structure")
    score += html_score

    # Keyword density
    found_kw = [kw for kw in cat["keywords"] if kw.lower() in desc_lower]
    if len(found_kw) >= 5:
        score += 5
        wins.append("Strong keyword presence (%d found in description)" % len(found_kw))
    elif len(found_kw) >= 3:
        score += 3
        wins.append("Some keywords found (%d). Aim for 5+" % len(found_kw))
    else:
        issues.append("Few category keywords found (%d). Include more relevant terms: %s"
                       % (len(found_kw), ", ".join(cat["keywords"][:5])))

    # Benefit-driven language
    benefit_words = [
        "save", "get", "access", "instant", "download", "bonus", "includes",
        "learn", "create", "grow", "start", "build", "launch", "proven",
        "ready", "easy", "simple", "powerful", "exclusive",
    ]
    found_benefits = [w for w in benefit_words if w in desc_lower]
    if found_benefits:
        score += min(len(found_benefits), 5)
        wins.append("Uses benefit-driven language (%d trigger words found)"
                     % len(found_benefits))
    else:
        issues.append("No benefit-driven language detected. "
                       "Use words like 'save', 'get', 'instant', 'proven'")

    # Call to action
    cta_patterns = [r'buy now', r'get started', r'download',
                    r'add to cart', r'purchase', r'get instant']
    if any(re.search(p, desc_lower) for p in cta_patterns):
        score += 2
        wins.append("Includes a call-to-action - drives conversions")
    else:
        issues.append("No clear call-to-action found. Tell buyers what to do next")

    # Trust signals
    trust_patterns = [
        r'lifetime access', r'free updates', r'instant download',
        r'money.back', r'guarantee', r'satisfaction', r'no branding',
        r'unlimited', r'commercial use',
    ]
    if any(re.search(p, desc_lower) for p in trust_patterns):
        score += 3
        wins.append("Includes trust signals (lifetime access, instant download, guarantee)")
    else:
        issues.append("No trust signals found. "
                       "Add 'instant download', 'lifetime updates', or 'money-back guarantee'")

    # Word count bonus
    if word_count >= 500:
        score += 3
        wins.append("Excellent description length (500+ words) - top-tier SEO depth")

    return {"score": min(score, max_score), "max": max_score, "issues": issues, "wins": wins}


def analyze_tags(tags: list, category: str) -> dict:
    """Score tags against Gumroad SEO best practices (max 20 chars each)."""
    score = 0
    max_score = 20
    issues = []
    wins = []

    if not tags:
        return {"score": 0, "max": max_score,
                "issues": ["No tags provided - tags are critical for Gumroad search"],
                "wins": []}

    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])

    # Count check
    tag_count = len(tags)
    if cat["min_tags"] <= tag_count <= cat["max_tags"]:
        score += 5
        wins.append("Good tag count (%d) - within recommended range" % tag_count)
    elif tag_count < cat["min_tags"]:
        score += 2
        issues.append("Not enough tags (%d). Add at least %d" % (tag_count, cat["min_tags"]))
    else:
        score += 3
        issues.append("Too many tags (%d). Gumroad allows up to %d; focus on quality"
                       % (tag_count, cat["max_tags"]))

    # Individual tag checks
    overlong = [t for t in tags if len(t) > 20]
    if overlong:
        issues.append("%d tag(s) exceed 20 char limit: %s"
                       % (len(overlong), ", ".join(overlong)))
    else:
        score += 3
        wins.append("All tags are within the 20-character limit")

    short_tags = [t for t in tags if len(t) < 3]
    if short_tags:
        issues.append("Tags too short to be useful: %s" % ", ".join(short_tags))

    # Single-word check
    multi_word = [t for t in tags if ' ' in t]
    if len(multi_word) >= 3:
        score += 3
        wins.append("Good mix of multi-word tags - more specific and targeted")
    elif len(multi_word) < 2:
        issues.append("Most tags are single words. "
                       "Use multi-word phrases for more specific targeting")

    # Category relevance
    relevant = 0
    for t in tags:
        t_lower = t.lower()
        for kw in cat["keywords"]:
            for kw_word in kw.split():
                if kw_word in t_lower:
                    relevant += 1
                    break
            else:
                continue
            break
    if relevant >= 3:
        score += 4
        wins.append("%d tags are relevant to category '%s'"
                     % (relevant, cat["label"]))
    elif relevant >= 1:
        score += 2
        wins.append("%d tag(s) relevant to category. Target at least 3" % relevant)
    else:
        issues.append("No tags relevant to the product category")

    # Keyword overlap with competitor tags
    overlap = sum(1 for t in tags if any(ct in t.lower() for ct in cat["competitor_tags"]))
    if overlap >= 2:
        score += 3
        wins.append("Tags overlap with high-search-volume competitor keywords")
    else:
        issues.append("Low overlap with popular search terms in this niche")

    # Capitalization consistency
    if len(tags) > 0:
        consistent_caps = sum(1 for t in tags if t and t[0].isupper())
        if consistent_caps == len(tags):
            score += 2
            wins.append("Tags use consistent capitalization (title case)")
        elif consistent_caps > 0:
            issues.append("Inconsistent capitalization - use title case for all tags")

    return {"score": min(score, max_score), "max": max_score, "issues": issues, "wins": wins}


def analyze_price(price: str, category: str) -> dict:
    """Score pricing signals (value perception for SEO)."""
    score = 0
    max_score = 10
    issues = []
    wins = []

    if not price:
        return {"score": 0, "max": max_score,
                "issues": ["No price provided"], "wins": []}

    # Extract numeric value
    price_str = price.replace("$", "").replace("SGD", "").replace("USD", "").strip()
    try:
        price_val = float(price_str)
    except ValueError:
        return {"score": 2, "max": max_score,
                "issues": ["Could not parse price '%s'" % price], "wins": []}

    # Price range analysis for digital products
    if 3 <= price_val <= 10:
        score += 5
        wins.append("Price point ($%.2f) is in the impulse-buy sweet spot for digital products"
                     % price_val)
    elif 10 < price_val <= 30:
        score += 4
        wins.append("Price point ($%.2f) is reasonable - ensure description justifies value"
                     % price_val)
    elif 30 < price_val <= 50:
        score += 2
        wins.append("Higher price point ($%.2f) - strong product preview "
                     "and testimonials recommended" % price_val)
    elif price_val < 3:
        score += 3
        issues.append("Very low price ($%.2f) - may signal low perceived value. "
                       "Consider bundling" % price_val)
    else:
        score += 1
        issues.append("Premium price point ($%.2f) - need very strong copy to convert"
                       % price_val)

    # Price format
    if "SGD" in price or "USD" in price:
        score += 2
        wins.append("Price includes currency code - good for international buyers")
    elif "$" in price:
        score += 1
    else:
        issues.append("Price should clearly show the currency")

    # Psychological pricing
    if price_val == int(price_val):
        score += 1
        wins.append("Round number price - clean and professional")

    return {"score": min(score, max_score), "max": max_score, "issues": issues, "wins": wins}


def analyze_meta_readiness(name: str, desc: str, category: str) -> dict:
    """Score meta-description readiness (150-160 chars)."""
    score = 0
    max_score = 10
    issues = []
    wins = []

    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])

    # Generate a potential meta from existing description
    meta = _make_meta_description(name, desc, category)
    meta_len = len(meta)

    if 150 <= meta_len <= 160:
        score += 10
        wins.append("Derived meta description is ideal length (%d chars)" % meta_len)
    elif 140 <= meta_len <= 170:
        score += 7
        wins.append("Derived meta description is close (%d chars). Target 150-160" % meta_len)
    elif meta_len >= 100:
        score += 4
        issues.append("Derived meta is short (%d chars). Expand to 150-160" % meta_len)
    else:
        score += 2
        issues.append("Cannot generate a strong meta description from current content (%d chars)"
                       % meta_len)

    # Keyword in meta
    found_kw = [kw for kw in cat["keywords"] if kw.lower() in meta.lower()]
    if found_kw:
        score += 2
        wins.append("Meta contains relevant keywords: %s" % ", ".join(found_kw[:2]))
    else:
        issues.append("Meta description lacks category keywords")

    return {"score": min(score, max_score), "max": max_score, "issues": issues, "wins": wins}


def _make_meta_description(name: str, desc: str, category: str) -> str:
    """Derive a meta description string from available content."""
    angle = CATEGORIES.get(category, CATEGORIES["solopreneur"])["description_angle"]
    if name:
        return "%s - %s" % (name, angle)
    return angle


def score_listing(name: str, desc: str, tags: list, price: str, category: str) -> dict:
    """Full SEO analysis returning a composite score (0-100) with details."""
    title_result = analyze_title(name, category)
    desc_result = analyze_description(desc, category)
    tags_result = analyze_tags(tags, category)
    price_result = analyze_price(price, category)
    meta_result = analyze_meta_readiness(name, desc, category)

    total = (title_result["score"] + desc_result["score"]
             + tags_result["score"] + price_result["score"]
             + meta_result["score"])
    max_total = (title_result["max"] + desc_result["max"]
                 + tags_result["max"] + price_result["max"]
                 + meta_result["max"])
    pct = round((total / max_total) * 100) if max_total > 0 else 0

    all_issues = []
    all_wins = []
    all_scores = {}
    for key, result in [
        ("title", title_result),
        ("description", desc_result),
        ("tags", tags_result),
        ("price", price_result),
        ("meta", meta_result),
    ]:
        all_issues.extend(result["issues"])
        all_wins.extend(result["wins"])
        sub_pct = round((result["score"] / result["max"]) * 100) if result["max"] > 0 else 0
        all_scores[key] = {"score": result["score"], "max": result["max"], "pct": sub_pct}

    # Severity
    if pct >= 90:
        severity = "Excellent"
    elif pct >= 70:
        severity = "Good"
    elif pct >= 50:
        severity = "Fair"
    else:
        severity = "Poor"

    return {
        "total_score": total,
        "max_score": max_total,
        "percentage": pct,
        "severity": severity,
        "scores": all_scores,
        "issues": all_issues,
        "wins": all_wins,
    }


# ──────────────────────────────────────────────────────────────────────
#  GENERATION ENGINE - optimized assets
# ──────────────────────────────────────────────────────────────────────

def generate_tags(name: str, category: str) -> list:
    """Generate SEO-optimized tags (max 20 chars each, Gumroad limit)."""
    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])
    product = _find_preset(name)

    base_tags = []
    if product:
        base_tags = list(product["suggested_tags"])
    else:
        # Generate from category defaults
        base_tags = cat["competitor_tags"][:5]

    # Add name-derived tags
    name_words = [w.lower().strip(",!?.") for w in name.split() if len(w) > 2]
    extra = []
    for w in name_words:
        w_title = w.title()
        if w_title.lower() not in [t.lower() for t in base_tags] and len(w_title) <= 20:
            extra.append(w_title)

    # Deduplicate preserving order (Python 3.7+ preserves dict insertion order)
    seen = set()
    all_tags = []
    for t in base_tags + extra:
        if t.lower() not in seen:
            seen.add(t.lower())
            all_tags.append(t)

    # Enforce 20-char limit and strip whitespace
    all_tags = [t[:20].strip() for t in all_tags]
    # Return up to 10 tags (Gumroad max)
    return all_tags[:10]


def generate_html_description(name: str, category: str) -> str:
    """Generate an SEO-optimized HTML description for the product."""
    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])
    template = HTML_DESC_TEMPLATES.get(category, HTML_DESC_TEMPLATES["solopreneur"])
    return template.format(angle=cat["description_angle"])


def generate_meta_description(name: str, category: str) -> str:
    """Generate a meta description (150-160 chars)."""
    product = _find_preset(name)
    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])

    if product and product["meta_description"]:
        meta = product["meta_description"]
    else:
        meta = "%s - %s" % (name, cat["description_angle"])

    # Trim to 150-160 chars at word boundary
    if len(meta) > 160:
        meta = meta[:157].rsplit(" ", 1)[0] + "..."
    elif len(meta) < 150:
        # Pad with category keywords
        needed = 150 - len(meta)
        extra = " " + ", ".join(cat["keywords"][:3])
        meta = meta + extra[:needed]

    return meta[:160]


def generate_keyword_suggestions(category: str) -> list:
    """Generate keyword improvement suggestions based on product type."""
    cat = CATEGORIES.get(category, CATEGORIES["solopreneur"])
    suggestions = []

    for kw in cat["keywords"][:8]:
        suggestions.append({
            "keyword": kw,
            "usage": ("Include '%s' in title, description headings, and tags" % kw),
            "search_volume_hint": "High" if len(kw.split()) >= 2 else "Medium",
        })

    # Add general SEO tips
    suggestions.append({
        "keyword": "[Product Type] + [Benefit]",
        "usage": ("Structure your title as 'What + For Whom + Result' "
                  "(e.g., 'TikTok Hooks Pack for Creators - Boost Engagement')"),
        "search_volume_hint": "Strategy",
    })
    suggestions.append({
        "keyword": "Long-tail phrases",
        "usage": ("Add a sentence in your description targeting a specific search query "
                  "(e.g., 'best TikTok hooks for small business owners')"),
        "search_volume_hint": "Strategy",
    })

    return suggestions


def generate_gumroad_commands(name: str, desc: str, tags: list,
                               price: str, category: str, mode: str) -> list:
    """Generate ready-to-use Gumroad CLI commands."""
    commands = []

    # Sanitize the name for CLI
    safe_name = name.replace("'", "'\\''")

    if mode == "generate":
        # Escape HTML for shell embedding
        html_desc_escaped = desc.replace("'", "'\\''")

        # Gumroad CLI: gumroad update <product_id> --description "..."
        commands.append("# Option 1: Gumroad CLI (if configured)")
        commands.append("gumroad product update '%s' \\" % safe_name)
        commands.append("  --description '%s' \\" % html_desc_escaped)
        tags_str = ",".join(tags)
        commands.append("  --tags '%s'" % tags_str)
        commands.append("")

        # Gumroad API curl alternative
        commands.append("# Option 2: Gumroad API (curl)")
        commands.append("# curl -X PUT https://api.gumroad.com/v2/products/<PRODUCT_ID> \\")
        commands.append("#   -d 'access_token=YOUR_TOKEN' \\")
        commands.append("#   -d 'name=%s' \\" % safe_name)
        commands.append("#   -d 'tags=%s' \\" % tags_str)
        commands.append("#   -d 'description=$(cat description.html)'")
        commands.append("")

        # Quick copy commands
        commands.append("# Option 3: Quick-copy assets")
        commands.append("cat > /tmp/gumroad_desc.html << 'GUMROAD_HTML'")
        commands.append(desc)
        commands.append("GUMROAD_HTML")
        commands.append("echo 'Description written to /tmp/gumroad_desc.html'")
        tags_str2 = ", ".join(tags)
        commands.append("echo 'Tags: %s'" % tags_str2)

    return commands


def _find_preset(name: str):
    """Look up a known product by name (case-insensitive, fuzzy)."""
    if not name:
        return None
    name_lower = name.strip().lower()
    for key, preset in PRODUCT_PRESETS.items():
        if key in name_lower or name_lower in key:
            return preset
    return None


# ──────────────────────────────────────────────────────────────────────
#  DISPLAY FORMATTERS
# ──────────────────────────────────────────────────────────────────────

def print_header(text: str, char: str = "="):
    width = 70
    padding = (width - len(text)) // 2
    print("\n%s%s" % (" " * padding if padding > 0 else "", text))
    print(char * width)


def print_separator(char: str = "-"):
    print(char * 70)


def print_score_bar(pct: int, label: str = "SCORE"):
    """Print a visual score bar."""
    filled = pct // 5
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    if pct >= 70:
        color = "\033[92m"
    elif pct >= 50:
        color = "\033[93m"
    else:
        color = "\033[91m"
    reset = "\033[0m"
    print("  %s %s%s %d%%%s" % (label, color, bar, pct, reset))


def format_analysis_result(result: dict):
    """Pretty-print the full SEO analysis."""
    pct = result["percentage"]
    severity = result["severity"]

    severity_colors = {
        "Excellent": "\033[92m",
        "Good": "\033[94m",
        "Fair": "\033[93m",
        "Poor": "\033[91m",
    }
    reset = "\033[0m"
    sev_color = severity_colors.get(severity, reset)

    print_header("SEO ANALYSIS RESULTS")
    print("  Overall Score:  %s%d/%d (%d%%) - %s%s"
          % (sev_color, result["total_score"], result["max_score"], pct, severity, reset))
    print_score_bar(pct)

    print_separator()
    print("  BREAKDOWN")
    for key, s in result["scores"].items():
        sub_pct = s["pct"]
        if sub_pct >= 70:
            sub_color = "\033[92m"
        elif sub_pct >= 50:
            sub_color = "\033[93m"
        else:
            sub_color = "\033[91m"
        label = key.replace("_", " ").title()
        bar = "█" * (sub_pct // 5) + "░" * (20 - sub_pct // 5)
        print("    %-20s %s%s %d%%%s" % (label, sub_color, bar, sub_pct, reset))

    if result["wins"]:
        print_separator()
        print("  \u2705 WINS (keep these)")
        for w in result["wins"]:
            print("    \u2022 %s" % w)

    if result["issues"]:
        print_separator()
        print("  \U0001f527 RECOMMENDATIONS (improve these)")
        for i, issue in enumerate(result["issues"], 1):
            print("    %d. %s" % (i, issue))

    print_separator()


def format_generation_output(name: str, category: str, tags: list,
                              html_desc: str, meta: str,
                              keywords: list, commands: list):
    """Pretty-print generated SEO assets."""
    reset = "\033[0m"
    green = "\033[92m"
    yellow = "\033[93m"

    print_header("SEO-OPTIMIZED ASSETS")

    # Meta description
    print("\n%s\U0001f4cb META DESCRIPTION%s" % (green, reset))
    print("  Length: %d chars (target: 150-160)" % len(meta))
    print("  %s%s%s" % (yellow, meta, reset))

    # Tags
    print("\n%s\U0001f3f7\ufe0f  TAGS%s  (max 20 chars each, max 10 tags)" % (green, reset))
    for i, tag in enumerate(tags, 1):
        status = "\u2705" if len(tag) <= 20 else "\u26a0\ufe0f"
        print("  %2d. %-22s (%d chars) %s" % (i, tag, len(tag), status))

    # HTML Description
    print("\n%s\U0001f4dd HTML DESCRIPTION%s  (ready to paste into Gumroad)"
          % (green, reset))
    print_separator()
    print(html_desc)
    print_separator()

    # Keyword suggestions
    print("\n%s\U0001f511 KEYWORD SUGGESTIONS%s" % (green, reset))
    for kw in keywords:
        vol = kw["search_volume_hint"]
        if vol == "High":
            vol_tag = "\033[92mHIGH\033[0m"
        elif vol == "Medium":
            vol_tag = "\033[93mMED\033[0m"
        else:
            vol_tag = "\033[94mTIP\033[0m"
        print("  %s  %s" % (vol_tag, kw["keyword"]))
        print("        %s" % kw["usage"])

    # CLI Commands
    print("\n%s\U0001f4bb GUMROAD CLI COMMANDS%s" % (green, reset))
    for line in commands:
        print("  %s" % line)

    print_separator()


# ──────────────────────────────────────────────────────────────────────
#  COMMAND-LINE INTERFACE
# ──────────────────────────────────────────────────────────────────────

def resolve_preset(args) -> dict:
    """Resolve any preset product info from the name, filling in missing args."""
    resolved = {
        "name": args.name,
        "price": args.price,
        "category": args.category,
        "tags": args.tags,
    }

    preset = _find_preset(args.name) if args.name else None
    if preset:
        if not args.price:
            resolved["price"] = preset["price"]
        if not args.category:
            resolved["category"] = preset["category"]
        if not args.tags:
            resolved["tags"] = preset["suggested_tags"]

    # Ensure category is valid
    if resolved["category"] and resolved["category"] not in CATEGORIES:
        print("Unknown category '%s'. Using 'solopreneur'." % resolved["category"],
              file=sys.stderr)
        resolved["category"] = "solopreneur"

    # Parse tags
    if isinstance(resolved["tags"], str):
        resolved["tags"] = [t.strip() for t in resolved["tags"].split(",") if t.strip()]
    elif resolved["tags"] is None:
        resolved["tags"] = []

    return resolved


def main():
    parser = argparse.ArgumentParser(
        description="Gumroad SEO Analyzer & Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Analyze an existing listing
              %(prog)s --analyze --name "TikTok Hooks" \\
                  --desc "..." --tags "hooks,viral" \\
                  --price "$3" --category social-media-prompts

              # Generate optimized assets
              %(prog)s --generate --name "TikTok Hooks" \\
                  --category social-media-prompts

              # With a custom product
              %(prog)s --analyze --name "My Product" --desc "..." \\
                  --tags "tag1,tag2" --price "$10" --category solopreneur
        """),
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--analyze", action="store_true",
                      help="Score existing product listing (0-100) with recommendations")
    mode.add_argument("--generate", action="store_true",
                      help="Create SEO-optimized product assets")

    parser.add_argument("--name", help="Product name / title")
    parser.add_argument("--desc", help="Product description (plain text or partial HTML)")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--price", help="Price (e.g., '3', '$5', 'SGD$19')")
    parser.add_argument("--category", help="Product category. One of: %s"
                        % ", ".join(CATEGORIES.keys()))

    args = parser.parse_args()

    # Validate
    if args.analyze and not args.name:
        print("Error: --name is required for --analyze mode", file=sys.stderr)
        sys.exit(1)
    if args.generate and not args.name:
        print("Error: --name is required for --generate mode", file=sys.stderr)
        sys.exit(1)

    # Resolve presets
    resolved = resolve_preset(args)
    name = resolved["name"]
    price = resolved["price"]
    category = resolved["category"]
    tags = resolved["tags"]

    # Execute mode
    if args.analyze:
        desc = args.desc or ""
        if not desc:
            print("Note: No description provided. Results will be limited.\n")

        result = score_listing(name, desc, tags, price, category)
        format_analysis_result(result)

    elif args.generate:
        html_desc = generate_html_description(name, category)
        opt_tags = generate_tags(name, category)
        meta = generate_meta_description(name, category)
        keywords = generate_keyword_suggestions(category)
        commands = generate_gumroad_commands(name, html_desc, opt_tags,
                                              price, category, "generate")

        format_generation_output(
            name=name,
            category=category,
            tags=opt_tags,
            html_desc=html_desc,
            meta=meta,
            keywords=keywords,
            commands=commands,
        )


if __name__ == "__main__":
    main()
