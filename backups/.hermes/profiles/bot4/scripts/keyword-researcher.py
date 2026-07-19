#!/usr/bin/env python3
"""
keyword-researcher.py — Free keyword research using Google Suggest, Related Searches, HN Algolia, and Reddit.

No API keys required. Uses only Python stdlib + urllib. Returns scored keywords ready for content planning.

Usage:
    python3 keyword-researcher.py --seed "tiktok hooks" --all
    python3 keyword-researcher.py --seed "AI productivity" --limit 25
    python3 keyword-researcher.py --trends
    python3 keyword-researcher.py --seed "chatgpt prompts" --save

Output:
    - Rich console table
    - JSON when --json flag
    - Markdown when --save flag → ~/.hermes/profiles/bot4/seo-output/keywords-{seed}.md
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
]

COMMERCIAL_WORDS = {
    "buy", "best", "cheap", "review", "reviews", "alternative", "alternatives",
    "vs", "versus", "comparison", "compare", "pricing", "price", "cost",
    "free", "download", "template", "templates", "pack", "bundle", "tool",
    "tools", "software", "app", "service", "agency", "course", "guide",
    "tutorial", "examples", "prompts", "ideas", "list", "top",
}

QUESTION_STARTERS = ("how", "what", "why", "when", "where", "who", "which", "can", "is", "are", "do", "does")


def http_get(url, timeout=10, headers=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENTS[hash(url) % len(USER_AGENTS)],
        "Accept": "application/json,text/html,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def google_suggest(seed, lang="en"):
    """Query Google's public suggest endpoint (no API key)."""
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={lang}&q={urllib.parse.quote(seed)}"
    try:
        raw = http_get(url, timeout=8)
        data = json.loads(raw)
        return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"[warn] google_suggest failed for '{seed}': {e}", file=sys.stderr)
        return []


def google_related(seed):
    """Extract related searches from Google SERP (best-effort, often rate-limited)."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(seed)}&num=20"
    try:
        raw = http_get(url, timeout=10).decode("utf-8", errors="ignore")
        # Find "related searches" patterns — Google embeds these in HTML
        matches = re.findall(r'<div[^>]*>([A-Za-z0-9][A-Za-z0-9\s\+\-\?\!\.&]{2,80})</div>', raw)
        cleaned = []
        for m in matches:
            m = m.strip()
            # Filter out things that look like nav/buttons
            if len(m) < 30 and not re.search(r"http|sign in|settings|privacy", m, re.I):
                cleaned.append(m)
        # Dedupe + cap
        return list(dict.fromkeys(cleaned))[:15]
    except Exception as e:
        print(f"[warn] google_related failed: {e}", file=sys.stderr)
        return []


def expand_with_letters(seed):
    """Run alphabet expansion: 'seed a', 'seed b' ... → long-tail ideas."""
    expansions = []
    for suffix in list("abcdefghijklmnopqrstuvwxyz") + ["for", "with", "near me", "2026", "free", "best"]:
        query = f"{seed} {suffix}".strip()
        expansions.extend(google_suggest(query))
    return list(dict.fromkeys(expansions))


def hn_algolia(query, hits_per_page=30):
    """Search Hacker News for trending discussions of the topic (free Algolia API)."""
    url = (
        f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}"
        f"&tags=story&hitsPerPage={hits_per_page}"
    )
    try:
        raw = http_get(url, timeout=10)
        data = json.loads(raw)
        titles = []
        for hit in data.get("hits", []):
            title = hit.get("title") or hit.get("story_title") or ""
            if title:
                titles.append({"title": title, "points": hit.get("points", 0), "comments": hit.get("num_comments", 0)})
        return titles
    except Exception as e:
        print(f"[warn] hn_algolia failed: {e}", file=sys.stderr)
        return []


def reddit_search(query, limit=25):
    """Search Reddit JSON endpoint (free, no auth)."""
    url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(query)}&limit={limit}&sort=relevance"
    try:
        raw = http_get(url, timeout=10, headers={"User-Agent": USER_AGENTS[0]})
        data = json.loads(raw)
        titles = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            titles.append({
                "title": d.get("title", ""),
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
            })
        return titles
    except Exception as e:
        print(f"[warn] reddit_search failed: {e}", file=sys.stderr)
        return []


def prime_score(keyword):
    """
    PRIME scoring (free-tier replacement for Keyword Planner volume).
    Higher = better opportunity. Range ~0-15.
    """
    k = keyword.lower().strip()
    tokens = k.split()

    score = 0
    # Google suggests it → already passed in (3 pts)
    score += 3
    # Question format
    if any(k.startswith(q + " ") or k.startswith(q + ",") for q in QUESTION_STARTERS):
        score += 2
    # Commercial intent
    if any(w in tokens for w in COMMERCIAL_WORDS):
        score += 2
    # Long-tail bonus (>3 words = lower competition)
    if len(tokens) >= 4:
        score += 1
    elif len(tokens) >= 3:
        score += 1
    # Niche-specific bonus (contains profession/role words)
    niche_words = {"realtor", "teacher", "freelancer", "developer", "marketer", "founder",
                   "writer", "designer", "consultant", "agency", "startup", "shopify",
                   "small business", "solopreneur", "creator", "coach", "author"}
    if any(w in k for w in niche_words):
        score += 2
    # 2026 / fresh / trending bonus
    if re.search(r"\b202[5-9]\b|\bnew\b|\blatest\b|\bupdated\b", k):
        score += 1
    return min(score, 15)


def tier(score):
    if score >= 10:
        return "🟢 A"
    if score >= 7:
        return "🟡 B"
    if score >= 4:
        return "🟠 C"
    return "⚪ D"


def research(seed, expand=True, with_hn=False, with_reddit=False, limit=30):
    """Main research pipeline: collects, dedupes, scores."""
    print(f"\n🔍 Researching: {seed}\n", file=sys.stderr)

    raw = set()
    raw.update(google_suggest(seed))
    if expand:
        raw.update(expand_with_letters(seed))

    # Always include the seed itself as a baseline
    raw.add(seed)

    scored = []
    for kw in raw:
        if not kw or len(kw) < 3 or len(kw) > 80:
            continue
        s = prime_score(kw)
        scored.append({"keyword": kw.strip(), "score": s, "tier": tier(s)})

    scored.sort(key=lambda x: (-x["score"], x["keyword"]))
    scored = scored[:limit]

    extras = {}
    if with_hn:
        extras["hn"] = hn_algolia(seed)
    if with_reddit:
        extras["reddit"] = reddit_search(seed)

    return {"seed": seed, "keywords": scored, "extras": extras, "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}


def print_table(result):
    print(f"\n📊 Keywords for: {result['seed']}\n")
    print(f"{'TIER':<8} {'SCORE':<6} KEYWORD")
    print("─" * 60)
    for kw in result["keywords"]:
        print(f"{kw['tier']:<8} {kw['score']:<6} {kw['keyword']}")
    a_count = sum(1 for k in result["keywords"] if k["tier"].startswith("🟢"))
    b_count = sum(1 for k in result["keywords"] if k["tier"].startswith("🟡"))
    print(f"\n🟢 A-tier (top priority): {a_count}  |  🟡 B-tier (good): {b_count}")
    if result.get("extras", {}).get("hn"):
        print(f"\n📰 Top HN mentions ({len(result['extras']['hn'])}):")
        for h in result["extras"]["hn"][:5]:
            print(f"  • [{h['points']}pts, {h['comments']}c] {h['title'][:70]}")
    if result.get("extras", {}).get("reddit"):
        print(f"\n🟥 Top Reddit mentions ({len(result['extras']['reddit'])}):")
        for r in result["extras"]["reddit"][:5]:
            print(f"  • [r/{r['subreddit']}, {r['score']}↑, {r['num_comments']}c] {r['title'][:70]}")


def save_markdown(result, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    seed_slug = re.sub(r"[^a-z0-9]+", "-", result["seed"].lower()).strip("-")
    path = out / f"keywords-{seed_slug}.md"
    lines = [
        f"# Keywords — {result['seed']}",
        f"\n_Generated: {result['generated_at']}_\n",
        "| Tier | Score | Keyword |",
        "|------|-------|---------|",
    ]
    for kw in result["keywords"]:
        lines.append(f"| {kw['tier']} | {kw['score']} | {kw['keyword']} |")
    lines.append(f"\n## Summary\n- Total: {len(result['keywords'])}\n- 🟢 A-tier: {sum(1 for k in result['keywords'] if k['tier'].startswith('🟢'))}\n- 🟡 B-tier: {sum(1 for k in result['keywords'] if k['tier'].startswith('🟡'))}\n")
    if result.get("extras", {}).get("hn"):
        lines.append("\n## Hacker News mentions\n")
        for h in result["extras"]["hn"][:10]:
            lines.append(f"- [{h['points']}pts] {h['title']}")
    if result.get("extras", {}).get("reddit"):
        lines.append("\n## Reddit mentions\n")
        for r in result["extras"]["reddit"][:10]:
            lines.append(f"- [r/{r['subreddit']}, {r['score']}↑] {r['title']}")
    path.write_text("\n".join(lines))
    print(f"\n💾 Saved: {path}")
    return path


def main():
    p = argparse.ArgumentParser(description="Free keyword research (Google Suggest + HN + Reddit)")
    p.add_argument("--seed", help="Seed keyword to expand")
    p.add_argument("--all", action="store_true", help="Include HN + Reddit mentions")
    p.add_argument("--hn", action="store_true", help="Include Hacker News mentions")
    p.add_argument("--reddit", action="store_true", help="Include Reddit mentions")
    p.add_argument("--limit", type=int, default=30, help="Max keywords to return")
    p.add_argument("--no-expand", action="store_true", help="Skip alphabet expansion")
    p.add_argument("--save", action="store_true", help="Save markdown to seo-output/")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--trends", action="store_true", help="Show pre-curated trend seeds across niches")
    p.add_argument("--outdir", default="~/.hermes/profiles/bot4/seo-output", help="Output directory for --save")
    args = p.parse_args()

    if args.trends:
        trends = [
            "AI prompts for solopreneurs",
            "tiktok hooks that go viral",
            "chatgpt prompts for small business",
            "best AI tools for content creators 2026",
            "how to automate business with AI",
            "faceless youtube channel ideas",
            "digital products to sell on gumroad",
            "AI side hustle ideas 2026",
            "tiktok shop affiliate for beginners",
            "make money with AI prompts",
        ]
        print("\n🔥 Trend Seeds (Jack's Gumroad niches, Jul 2026)\n")
        for t in trends:
            print(f"  → {t}")
        print(f"\nRe-run with: --seed \"<keyword>\" --all\n")
        return

    if not args.seed:
        p.error("--seed required (or use --trends)")

    result = research(
        args.seed,
        expand=not args.no_expand,
        with_hn=(args.hn or args.all),
        with_reddit=(args.reddit or args.all),
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_table(result)

    if args.save:
        save_markdown(result, args.outdir)


if __name__ == "__main__":
    main()