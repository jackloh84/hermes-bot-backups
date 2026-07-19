#!/usr/bin/env python3
"""SEO Article Generator v1.0

Generates SEO-optimized articles targeting specific keywords,
with proper structure, headings, keyword placement, and Gumroad product links.

Usage:
  ./seo-article-generator.py --keyword "tiktok hooks" --product 1
  ./seo-article-generator.py --keyword "AI productivity" --product 3 --out article.md
  ./seo-article-generator.py --list-topics   # Show suggested topics
"""
import sys, os, datetime
from pathlib import Path

PRODUCTS = {
    1: {"name": "50 Viral TikTok Hooks + AI Prompts", "price": "$3", "url": "https://jackalope86.gumroad.com/l/diywdak", "slug": "tiktok-hooks"},
    2: {"name": "AI for Content Creators Vol 2", "price": "SGD$19", "url": "https://jackalope86.gumroad.com/l/xcjutg", "slug": "content-creators"},
    3: {"name": "AI Business Automation Prompt Pack", "price": "SGD$19", "url": "https://jackalope86.gumroad.com/l/byrjla", "slug": "biz-automation"},
    4: {"name": "The AI Solopreneur Launchpad", "price": "$5", "url": "https://jackalope86.gumroad.com/l/dgdtjf", "slug": "solopreneur-launchpad"},
}

# Pre-researched article topics with target keywords (25 validated from Google Suggest)
ARTICLE_TOPICS = [
    # ── Validated from Google Suggest (25 keywords researched Jul 2026) ──
    {
        "title": "10 TikTok Hooks That Stop the Scroll (With AI Prompts)",
        "keyword": "tiktok hooks",
        "product": 1,
        "description": "10 proven hook formulas with AI prompt templates to remix for any niche",
        "platform": "medium, devto, blog"
    },
    {
        "title": "Best ChatGPT Prompts for Small Business Owners (2026 Guide)",
        "keyword": "ChatGPT prompts for small business",
        "product": 3,
        "description": "Ready-to-use ChatGPT prompts that save small business owners 10+ hours a week on marketing, sales, and operations",
        "platform": "medium, devto, linkedin"
    },
    {
        "title": "AI Prompts for Content Creation: 50+ Templates for YouTube, TikTok & Instagram",
        "keyword": "AI prompts for content creation",
        "product": 2,
        "description": "AI prompt templates for social media content creators — write scripts, captions, and grow your audience faster",
        "platform": "medium, devto"
    },
    {
        "title": "ChatGPT Prompts for Copywriting: Write Better Sales Copy in Half the Time",
        "keyword": "ChatGPT prompts for copywriting",
        "product": 3,
        "description": "Copywriting prompts for ChatGPT that help you write sales pages, ads, emails, and landing pages faster",
        "platform": "medium, devto, linkedin"
    },
    {
        "title": "AI Prompts for Social Media Marketing: 30 Templates That Drive Engagement",
        "keyword": "AI prompts for social media marketing",
        "product": 2,
        "description": "Social media marketing prompts for TikTok, Instagram, LinkedIn — captions, hooks, and content strategies",
        "platform": "medium, devto"
    },
    {
        "title": "Best AI Prompts for Email Marketing Campaigns (That Actually Convert)",
        "keyword": "Best AI prompts for email marketing",
        "product": 3,
        "description": "Email marketing prompts for cold outreach, newsletters, and automated sequences that get replies and sales",
        "platform": "medium, linkedin"
    },
    {
        "title": "ChatGPT Prompts for Blog Writing: 400+ Blog Post Ideas & Outlines",
        "keyword": "ChatGPT prompts for blog writing",
        "product": 2,
        "description": "Blog writing prompts for ChatGPT that generate topic ideas, outlines, and full drafts in minutes",
        "platform": "medium, devto"
    },
    {
        "title": "From Side Hustle to Full-Time: A Solopreneur's Guide",
        "keyword": "solopreneur side hustle guide",
        "product": 4,
        "description": "Guide to transitioning from side project to main business with AI tools and templates",
        "platform": "medium, linkedin"
    },
    {
        "title": "AI Prompt Engineering for Beginners (Complete 2026 Guide)",
        "keyword": "AI prompt engineering for beginners",
        "product": 2,
        "description": "Beginner-friendly guide to writing effective AI prompts that produce consistent, high-quality results",
        "platform": "medium, devto"
    },
    {
        "title": "10 Business Processes You Can Automate With ChatGPT Today",
        "keyword": "automate business with ChatGPT",
        "product": 3,
        "description": "Practical business automation examples with ready-to-use ChatGPT prompts for solopreneurs",
        "platform": "medium, linkedin"
    },
    {
        "title": "ChatGPT Prompts for Facebook Ads: High-Converting Ad Copy Templates",
        "keyword": "Prompts for Facebook ads",
        "product": 3,
        "description": "Facebook ad copy prompts that generate high-converting ad variations for any product or audience",
        "platform": "medium, devto"
    },
    {
        "title": "AI Prompts for LinkedIn: Grow Your Professional Brand",
        "keyword": "AI prompts for LinkedIn",
        "product": 4,
        "description": "LinkedIn growth prompts for profile optimization, content strategy, and networking messages",
        "platform": "medium, linkedin"
    },
    {
        "title": "How to Start a Digital Product Business With Under $10",
        "keyword": "start digital product business",
        "product": 4,
        "description": "Zero-to-launch guide for aspiring solopreneurs — validate, create, and sell digital products",
        "platform": "medium, devto"
    },
]

def generate_article(keyword, product_id):
    """Generate a full SEO-optimized article for a keyword + product."""
    prod = PRODUCTS.get(product_id, PRODUCTS[1])
    today = datetime.date.today().strftime("%B %d, %Y")
    
    # Find the topic template
    topic = None
    for t in ARTICLE_TOPICS:
        if keyword.lower() in t["keyword"].lower() or keyword.lower() in t["title"].lower():
            topic = t
            break
    
    if not topic:
        topic = {
            "title": f"Complete Guide to {keyword.title()}",
            "keyword": keyword,
            "product": product_id,
            "description": f"Guide about {keyword}",
            "platform": "medium"
        }
    
    # Generate different article types based on keyword
    if "how to" in keyword.lower() or "guide" in topic["title"].lower():
        return generate_how_to_guide(topic, prod, today)
    elif "best" in topic["title"].lower():
        return generate_listicle(topic, prod, today)
    elif "tips" in keyword.lower() or "hooks" in keyword.lower():
        return generate_tips_article(topic, prod, today)
    else:
        return generate_general_article(topic, prod, today)

def generate_how_to_guide(topic, product, date_str):
    """Generate a how-to guide article."""
    kw = topic["keyword"]
    title = topic["title"]
    
    return f"""---
title: "{title}"
description: "{topic['description']}"
date: {date_str}
author: Jack Loh
tags: [{', '.join(kw.split()[:4])}]
---

# {title}

Are you looking for practical ways to use {kw}? You're not alone. Thousands of creators and entrepreneurs are discovering how AI can transform their workflow.

In this guide, I'll walk you through exactly how to get started — no technical experience required.

## What Is {kw.title()}?

{kw.title()} is one of the most searched topics in the creator economy right now. Whether you're a solopreneur, content creator, or small business owner, understanding this can save you hours every week.

## Why This Matters Now

We're in 2026. The tools available today make what was impossible last year completely accessible. The gap between those who use AI effectively and those who don't is widening fast.

## Step 1: Start With the Right Foundation

Before diving in, make sure you have the basics set up. The most important thing is having the right templates and prompts ready to go. This is where having a structured prompt pack makes all the difference.

> **Pro tip:** A well-organized prompt pack can save you 10+ hours per week. Check out the [{product['name']}]({product['url']}) for ready-to-use templates.

## Step 2: Implement the Core Workflow

Here's the simple 3-step process that works:

1. **Identify** the task you want to automate or improve
2. **Apply** the right prompt template from your collection
3. **Refine** based on results — AI gets better with iteration

## Step 3: Scale What Works

Once you have a working workflow, replicate it across other areas. The same approach that works for content creation can be adapted for email marketing, customer support, and business operations.

## Common Mistakes to Avoid

- **Overcomplicating:** Start simple. One good prompt beats ten mediocre ones
- **Not iterating:** The first output isn't always the best — refine it
- **Ignoring structure:** Organized prompts produce better results

## Tools You'll Need

| Tool | Purpose | Cost |
|------|---------|------|
| ChatGPT / Claude | AI assistant | Free or paid |
| {product['name']} | Ready prompts | {product['price']} |
| Your favorite editor | Implementation | Free |

## Take Action Today

The best time to start was yesterday. The second best time is now.

👉 **Get started with [{product['name']}]({product['url']})** — {product['price']} one-time payment, instant download.

*This article was originally published on [Medium](https://medium.com). For more resources, visit [jackalope86.gumroad.com](https://jackalope86.gumroad.com).*
"""

def generate_listicle(topic, product, date_str):
    """Generate a listicle-style article."""
    kw = topic["keyword"]
    title = topic["title"]
    items = [
        f"**{kw.title()} Strategy** — The foundational approach that works for most creators. Start here if you're new.",
        f"**Advanced {kw} Techniques** — For when you've mastered the basics and want to level up.",
        f"**Free {kw} Resources** — Curated tools and templates that cost nothing to use.",
        f"**{kw} Automation** — How to set it up once and let it run on autopilot.",
        f"**Pro {kw} Tips** — What experienced practitioners do differently.",
    ]
    
    return f"""---
title: "{title}"
description: "{topic['description']}"
date: {date_str}
author: Jack Loh
tags: [{', '.join(kw.split()[:4])}]
---

# {title}

Looking for the best {kw}? I've compiled the top strategies, tools, and templates to help you get results fast.

## Why {kw.title()} Matters

In 2026, {kw} isn't just a nice-to-have — it's essential for anyone serious about growing their online presence or business. The creators who master this pull ahead. Those who don't get left behind.

## The Top {len(items)} {kw.title()} Strategies

|{chr(10).join(f'{i+1}. {item}' for i, item in enumerate(items))}

## What Successful People Do Differently

The difference between average and exceptional results often comes down to having the right templates and prompts ready. Instead of reinventing the wheel every time, top performers use structured systems.

That's exactly why I created the [{product['name']}]({product['url']}) — so you can skip the trial and error and get straight to results.

## Quick Comparison

| Approach | Time Investment | Results | Cost |
|----------|----------------|---------|------|
| DIY (from scratch) | High | Variable | Free |
| Templates + AI | Low | Consistent | Minimal |
| Professional system | Very Low | Proven | {product['price']} |

## Your Next Step

Don't overthink this. Pick one strategy from the list above and implement it today. The difference between those who succeed and those who don't is simply starting.

👉 **[Get the {product['name']}]({product['url']})** for {product['price']} — instant download, lifetime access.

---

*Found this helpful? Share it with a friend. Visit [jackalope86.gumroad.com](https://jackalope86.gumroad.com) for more resources.*
"""

def generate_tips_article(topic, product, date_str):
    """Generate a tips/hacks style article."""
    kw = topic["keyword"]
    title = topic["title"]
    
    return f"""---
title: "{title}"
description: "{topic['description']}"
date: {date_str}
author: Jack Loh
tags: [{', '.join(kw.split()[:4])}]
---

# {title}

After spending months testing what works, here are the most effective {kw} strategies I've found.

## Why These Tips Work

Every tip below has been tested in real projects. These aren't theoretical — they're battle-tested approaches that save time and deliver results.

## 1. Start With a Proven Template

The biggest mistake beginners make is writing prompts from scratch every time. Instead, maintain a library of proven templates that you can adapt.

> **Example:** Instead of "Write a TikTok caption about..." use a structured template that includes hooks, CTAs, and hashtag suggestions. The [{product['name']}]({product['url']}) has these ready to go.

## 2. Focus on One Platform at a Time

Don't try to master everything at once. Pick the platform that matters most for your goals and go deep before expanding.

## 3. Measure What Works

Keep track of which approaches drive results. Double down on winners, cut what doesn't work.

## 4. Use the 80/20 Rule

80% of results come from 20% of efforts. Identify your highest-impact activities and prioritize them.

## 5. Automate Repetitive Tasks

If you're doing the same task more than 3 times, automate it. AI prompts are perfect for this — one good prompt can replace hours of manual work.

## Quick Start Checklist

- [ ] Define your goal
- [ ] Choose your platform
- [ ] Set up your prompt templates
- [ ] Create your first piece of content
- [ ] Measure results
- [ ] Iterate and improve

## Resources

Ready to implement these tips? The [{product['name']}]({product['url']}) includes everything you need to get started — {product['price']} one-time, instant download.

---

*Jack Loh is a Singapore-based solopreneur building AI-powered digital products. Follow for more tips.*
"""

def generate_general_article(topic, product, date_str):
    """Generate a general informative article."""
    kw = topic["keyword"]
    title = topic["title"]
    
    return f"""---
title: "{title}"
description: "{topic['description']}"
date: {date_str}
author: Jack Loh
tags: [{', '.join(kw.split()[:4])}]
---

# {title}

{kw.title()} is transforming how creators and entrepreneurs work. In this article, I'll share what I've learned and how you can apply it.

## The Current Landscape

We're seeing unprecedented growth in AI-powered tools for content creation, business automation, and solopreneurship. The barrier to entry has never been lower — but the window of opportunity won't stay open forever.

## What Actually Works

After testing dozens of approaches, here's what consistently delivers results:

1. **Structured systems** beat ad-hoc approaches every time
2. **Quality templates** save more time than you'd think
3. **Consistent execution** matters more than perfect strategy

## The Hidden Opportunity

Most people spend too much time on setup and not enough on execution. Having ready-to-use templates and prompts eliminates the setup phase entirely.

That's why I created the [{product['name']}]({product['url']}) — to give you a proven system that works from day one.

## Key Takeaways

- **Start today** — perfection is the enemy of progress
- **Use systems** — templates save hours every week
- **Stay consistent** — small daily actions compound
- **Measure results** — data beats opinions

## Get Started

The most important step is the first one. Don't wait until you have everything figured out — start with what you have and improve as you go.

👉 **[Get the {product['name']}]({product['url']})** for {product['price']}. Instant download, lifetime access.

---

*Built in Singapore 🇸🇬. Visit [jackalope86.gumroad.com](https://jackalope86.gumroad.com) for more digital products.*
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if sys.argv[1] == "--list-topics":
        print("\n📝 Suggested Article Topics:\n")
        print(f"{'#':<3} {'Title':<55} {'Keyword':<25} {'Product':<20}")
        print(f"{'─'*3} {'─'*55} {'─'*25} {'─'*20}")
        for i, t in enumerate(ARTICLE_TOPICS, 1):
            p = PRODUCTS[t['product']]['name'][:18]
            print(f"{i:<3} {t['title'][:52]:<55} {t['keyword'][:22]:<25} {p:<20}")
        print(f"\nGenerate one: python3 seo-article-generator.py --keyword \"tiktok hooks\" --product 1")
        sys.exit(0)
    
    keyword = ""
    product_id = 1
    output = None
    
    for i, arg in enumerate(sys.argv):
        if arg == "--keyword" and i+1 < len(sys.argv):
            keyword = sys.argv[i+1]
        elif arg == "--product" and i+1 < len(sys.argv):
            product_id = int(sys.argv[i+1])
        elif arg == "--out" and i+1 < len(sys.argv):
            output = sys.argv[i+1]
    
    if not keyword:
        print("❌ Required: --keyword \"your keyword\"")
        sys.exit(1)
    
    article = generate_article(keyword, product_id)
    
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True) if path.parent != Path() else None
        path.write_text(article)
        print(f"✅ Article saved to {path}")
    else:
        print(article)
