#!/usr/bin/env python3
"""
Competitor Intelligence Scanner
===============================
Scans Gumroad, Product Hunt, Hacker News (Algolia), and Dev.to for
competitor intelligence about AI prompt packs and digital products.

Output: Markdown brief → stdout (or file with --output).
Caching: /tmp/competitor_cache.json with 24-hour TTL (or override with --ttl).
Dependencies: stdlib only (urllib, json, re, hashlib, time).
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────

CACHE_FILE = "/tmp/competitor_cache.json"
CACHE_TTL_SECONDS = 86400  # 24 hours

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

TIMEOUT = 20  # seconds per request


# ── Helpers ─────────────────────────────────────────────────────────────────

def _rotate_ua(index=0):
    return USER_AGENTS[index % len(USER_AGENTS)]


def _ua_header(rotation=0):
    return {"User-Agent": _rotate_ua(rotation)}


def _fetch(url, rotation=0, data=None, headers_extra=None):
    """Fetch a URL with rotating User-Agent and return decoded text."""
    headers = _ua_header(rotation)
    if headers_extra:
        headers.update(headers_extra)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")
    except urllib.error.HTTPError as exc:
        print(f"  [WARN] HTTP {exc.code} fetching {url}", file=sys.stderr)
        return None
    except urllib.error.URLError as exc:
        print(f"  [WARN] Connection error for {url}: {exc.reason}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"  [WARN] Unexpected error fetching {url}: {exc}", file=sys.stderr)
        return None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ── Cache ───────────────────────────────────────────────────────────────────

def _cache_load(ttl_seconds):
    """Load cached data if still fresh; return None otherwise."""
    if not os.path.isfile(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    cached_at = data.get("cached_at", 0)
    age = time.time() - cached_at
    if age < ttl_seconds:
        return data.get("results")
    return None


def _cache_save(results):
    """Save results to cache file."""
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    payload = {
        "cached_at": time.time(),
        "cached_at_iso": _now_iso(),
        "ttl_seconds": CACHE_TTL_SECONDS,
        "results": results,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ── Source scanners ─────────────────────────────────────────────────────────

def scan_gumroad(query="AI prompt pack"):
    """Scan Gumroad Discover for products matching the query."""
    print("  \U0001f50d Scanning Gumroad Discover...", file=sys.stderr)
    url = f"https://gumroad.com/discover?query={urllib.parse.quote(query)}"
    html_text = _fetch(url, rotation=0)
    if not html_text:
        print("  \u26a0\ufe0f  Gumroad returned no content (may be JS-rendered).", file=sys.stderr)
        return []

    products = []

    # Pattern 1: JSON-LD structured data
    ld_pattern = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in ld_pattern.finditer(html_text):
        try:
            ld_data = json.loads(match.group(1))
            items = ld_data if isinstance(ld_data, list) else [ld_data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in (
                    "Product", "DigitalDocument",
                ):
                    products.append({
                        "name": item.get("name", "Unknown"),
                        "price": item.get("offers", {}).get("price", "N/A"),
                        "currency": item.get("offers", {}).get("priceCurrency", "USD"),
                        "rating": item.get("aggregateRating", {}).get("ratingValue", "N/A"),
                        "reviews": item.get("aggregateRating", {}).get("reviewCount", 0),
                        "url": item.get("url", ""),
                        "description": (item.get("description", "") or "")[:200],
                        "source": "Gumroad",
                    })
        except (json.JSONDecodeError, AttributeError):
            continue

    # Pattern 2: Product card DOM elements
    card_pattern = re.compile(
        r'<a[^>]*class="[^"]*product-card[^"]*"[^>]*href="([^"]+)"[^>]*>.*?'
        r'<div[^>]*class="[^"]*product-title[^"]*"[^>]*>(.*?)</div>.*?'
        r'<div[^>]*class="[^"]*product-price[^"]*"[^>]*>\$?([\d.]+)',
        re.DOTALL | re.IGNORECASE,
    )
    for match in card_pattern.finditer(html_text):
        name = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        price = match.group(3)
        products.append({
            "name": name or "Unknown",
            "price": price,
            "currency": "USD",
            "rating": "N/A",
            "reviews": 0,
            "url": "https://gumroad.com" + match.group(1)
            if match.group(1).startswith("/")
            else match.group(1) or "",
            "description": "",
            "source": "Gumroad",
        })

    # Pattern 3: Embedded JSON state
    state_pattern = re.compile(
        r'__GUMROAD_INITIAL_STATE__\s*=\s*({.*?});',
        re.DOTALL,
    )
    state_match = state_pattern.search(html_text)
    if state_match:
        try:
            state = json.loads(state_match.group(1))
            for item in (
                state.get("discoverResults", [])
                or state.get("products", [])
                or state.get("results", [])
            ):
                if isinstance(item, dict):
                    products.append({
                        "name": item.get("name", item.get("title", "Unknown")),
                        "price": item.get("price", item.get("formattedPrice", "N/A")),
                        "currency": item.get("currency", "USD"),
                        "rating": item.get("rating", item.get("averageRating", "N/A")),
                        "reviews": item.get("reviewCount", item.get("numReviews", 0)),
                        "url": item.get("url", item.get("shortUrl", "")),
                        "description": (item.get("description", "") or "")[:200],
                        "source": "Gumroad",
                    })
        except (json.JSONDecodeError, AttributeError):
            pass

    # Deduplicate
    seen = set()
    unique = []
    for p in products:
        key = p["name"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"  \u2705 Gumroad: found {len(unique)} products", file=sys.stderr)
    return unique


def scan_producthunt(topic="ai"):
    """Scan Product Hunt for trending AI / prompt-related products."""
    print("  \U0001f50d Scanning Product Hunt...", file=sys.stderr)
    all_products = []

    # Attempt 1: Product Hunt search results
    url = f"https://www.producthunt.com/search?q={urllib.parse.quote(topic)}"
    html_text = _fetch(url, rotation=1)
    if html_text:
        ld_pattern = re.compile(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in ld_pattern.finditer(html_text):
            try:
                ld_data = json.loads(match.group(1))
                items = ld_data if isinstance(ld_data, list) else [ld_data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in (
                        "Product", "SoftwareApplication",
                    ):
                        all_products.append({
                            "name": item.get("name", "Unknown"),
                            "tagline": (item.get("description", "") or "")[:200],
                            "url": item.get("url", ""),
                            "source": "Product Hunt",
                        })
            except (json.JSONDecodeError, AttributeError):
                continue

        # Fallback: product links in HTML
        title_pattern = re.compile(
            r'<a[^>]*href="/(posts/[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        seen_urls = set()
        for match in title_pattern.finditer(html_text):
            post_url = "https://www.producthunt.com/" + match.group(1)
            name = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
            if name and post_url not in seen_urls and len(name) > 3:
                seen_urls.add(post_url)
                all_products.append({
                    "name": name,
                    "tagline": "",
                    "url": post_url,
                    "source": "Product Hunt",
                })

    # Attempt 2: Topics page
    topics_url = "https://www.producthunt.com/topics/artificial-intelligence"
    topics_html = _fetch(topics_url, rotation=2)
    if topics_html:
        title_pattern = re.compile(
            r'<a[^>]*href="/(posts/[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        seen_urls = {p["url"] for p in all_products}
        for match in title_pattern.finditer(topics_html):
            post_url = "https://www.producthunt.com/" + match.group(1)
            name = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
            if name and post_url not in seen_urls and len(name) > 3:
                seen_urls.add(post_url)
                all_products.append({
                    "name": name,
                    "tagline": "",
                    "url": post_url,
                    "source": "Product Hunt",
                })

    # Deduplicate
    seen = set()
    unique = []
    for p in all_products:
        key = p["name"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"  \u2705 Product Hunt: found {len(unique)} products", file=sys.stderr)
    return unique


def scan_hacker_news(query="AI prompt pack", limit=20):
    """Query Hacker News Algolia API for mentions."""
    print("  \U0001f50d Querying Hacker News (Algolia API)...", file=sys.stderr)
    api_url = (
        f"https://hn.algolia.com/api/v1/search?"
        f"query={urllib.parse.quote(query)}"
        f"&hitsPerPage={limit}"
        f"&tags=story"
    )
    response = _fetch(api_url, rotation=0, headers_extra={"Accept": "application/json"})
    if not response:
        print("  \u26a0\ufe0f  HN Algolia API returned nothing.", file=sys.stderr)
        return []

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        print("  \u26a0\ufe0f  Could not parse HN Algolia response.", file=sys.stderr)
        return []

    hits = data.get("hits", [])
    results = []
    for hit in hits:
        results.append({
            "title": hit.get("title", "Untitled"),
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
            "points": hit.get("points", 0),
            "num_comments": hit.get("num_comments", 0),
            "author": hit.get("author", "unknown"),
            "created_at": hit.get("created_at", ""),
            "object_id": hit.get("objectID", ""),
            "source": "Hacker News",
        })

    print(f"  \u2705 HN Algolia: {len(results)} mentions found", file=sys.stderr)
    return results


def scan_devto(query="AI prompt", limit=15):
    """Query Dev.to API for trending articles."""
    print("  \U0001f50d Querying Dev.to API...", file=sys.stderr)
    api_url = f"https://dev.to/api/articles?tag=ai&per_page={limit}"
    response = _fetch(api_url, rotation=3, headers_extra={"Accept": "application/json"})
    if not response:
        print("  \u26a0\ufe0f  Dev.to API returned nothing.", file=sys.stderr)
        return []

    try:
        articles = json.loads(response)
    except json.JSONDecodeError:
        print("  \u26a0\ufe0f  Could not parse Dev.to response.", file=sys.stderr)
        return []

    keywords = ["prompt", "ai tool", "digital product", "prompt pack", "gumroad",
                "llm", "chatgpt prompt", "midjourney", "stable diffusion"]
    results = []
    for article in articles:
        title = (article.get("title", "") or "").lower()
        tags = [t.lower() for t in (article.get("tag_list", []) or [])]
        description = (article.get("description", "") or "").lower()
        is_relevant = any(kw in title for kw in keywords) or any(
            kw in description for kw in keywords
        )
        results.append({
            "title": article.get("title", "Untitled"),
            "url": article.get("url", ""),
            "tags": article.get("tag_list", []),
            "reactions": article.get("positive_reactions_count", 0),
            "comments": article.get("comments_count", 0),
            "user": article.get("user", {}).get("username", "unknown"),
            "published_at": article.get("published_at", ""),
            "description": (article.get("description", "") or "")[:200],
            "relevance_to_prompts": is_relevant,
            "source": "Dev.to",
        })

    print(f"  \u2705 Dev.to: {len(results)} articles found", file=sys.stderr)
    return results


# ── Brief generation ───────────────────────────────────────────────────────

def generate_brief(gumroad, producthunt, hn, devto):
    """Compile all results into a Markdown competitor brief."""
    now = _now_iso()
    lines = []
    lines.append("# \U0001f916 Competitor Intelligence Brief")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Gumroad Products ──
    lines.append("## \U0001f6cd\ufe0f Gumroad \u2014 Competitor Products")
    lines.append("")
    if gumroad:
        lines.append(f"**{len(gumroad)} products found** on Gumroad Discover.\n")
        lines.append("| # | Product | Price | Rating | Reviews | URL |")
        lines.append("|---|---|---|---|---|---|")
        for i, p in enumerate(gumroad, 1):
            name = p.get("name", "Unknown")[:60]
            price = p.get("price", "N/A")
            if isinstance(price, (int, float)):
                price_str = f"${price:.2f}"
            else:
                price_str = str(price) if price else "N/A"
                if price_str and not price_str.startswith("$") and price_str != "N/A":
                    price_str = f"${price_str}"
            rating = p.get("rating", "N/A")
            rating_str = str(rating) if rating and rating != "N/A" else "\u2014"
            reviews = p.get("reviews", 0)
            reviews_str = str(_safe_int(reviews)) if reviews else "\u2014"
            url = p.get("url", "")[:80] or "\u2014"
            lines.append(
                f"| {i} | {name} | {price_str} | {rating_str} | {reviews_str} | {url} |"
            )
    else:
        lines.append("*No Gumroad products detected (page may be JS-rendered).*\n")
        lines.append(
            "> \U0001f4a1 Tip: Open https://gumroad.com/discover?query=AI+prompt+pack "
            "in a browser for full results (Gumroad is JS-heavy for search)."
        )

    lines.append("")

    # ── Product Hunt ──
    lines.append("## \U0001f680 Product Hunt \u2014 Trending AI Tools")
    lines.append("")
    if producthunt:
        lines.append(f"**{len(producthunt)} products** trending on Product Hunt.\n")
        lines.append("| # | Product | Tagline | URL |")
        lines.append("|---|---|---|---|")
        for i, p in enumerate(producthunt, 1):
            name = p.get("name", "Unknown")[:60]
            tagline = (p.get("tagline", "") or "")[:80] or "\u2014"
            url = p.get("url", "")[:80] or "\u2014"
            lines.append(f"| {i} | {name} | {tagline} | {url} |")
    else:
        lines.append("*No Product Hunt products extracted (page may be JS-rendered).*\n")
        lines.append(
            "> \U0001f4a1 Tip: Visit https://www.producthunt.com/search?q=ai "
            "in a browser for the interactive feed."
        )

    lines.append("")

    # ── Hacker News Mentions ──
    lines.append("## \U0001f4f0 Hacker News \u2014 Mentions & Discussions")
    lines.append("")
    if hn:
        lines.append(f"**{len(hn)} stories** mentioning AI prompts/packs.\n")
        lines.append("| # | Title | Points | Comments | Author | URL |")
        lines.append("|---|---|---|---|---|---|")
        for i, h in enumerate(hn, 1):
            title = (h.get("title", "") or "")[:70]
            points = h.get("points", 0)
            comments = h.get("num_comments", 0)
            author = h.get("author", "?")
            url = h.get("url", "")[:70] or "\u2014"
            lines.append(f"| {i} | {title} | {points} | {comments} | {author} | {url} |")
    else:
        lines.append("*No Hacker News mentions found.*")
    lines.append("")

    # ── Dev.to Articles ──
    lines.append("## \u270d\ufe0f Dev.to \u2014 Trending Articles")
    lines.append("")
    if devto:
        lines.append(f"**{len(devto)} articles** from Dev.to (tagged AI).\n")
        lines.append("| # | Title | Reactions | Comments | Author | Tags | URL |")
        lines.append("|---|---|---|---|---|---|---|")
        for i, a in enumerate(devto, 1):
            title = (a.get("title", "") or "")[:60]
            reactions = a.get("reactions", 0)
            comments = a.get("comments", 0)
            user = a.get("user", "?")
            tags = ", ".join((a.get("tags", []) or [])[:3]) or "\u2014"
            url = a.get("url", "")[:60] or "\u2014"
            marker = " \u26a1" if a.get("relevance_to_prompts") else ""
            lines.append(
                f"| {i} | {title}{marker} | {reactions} | {comments} | {user} | {tags} | {url} |"
            )
    else:
        lines.append("*No articles found via Dev.to API.*")
    lines.append("")

    # ── Market Trends Summary ──
    lines.append("---")
    lines.append("## \U0001f4ca Market Trends Summary")
    lines.append("")

    prices = []
    if gumroad:
        for p in gumroad:
            pr = p.get("price", "N/A")
            if isinstance(pr, (int, float)):
                prices.append(pr)
            else:
                try:
                    cleaned = re.sub(r"[^0-9.]", "", str(pr))
                    if cleaned:
                        prices.append(float(cleaned))
                except ValueError:
                    pass
        if prices:
            lines.append(f"- **Gumroad price range:** ${min(prices):.2f} \u2013 ${max(prices):.2f}")
            lines.append(f"- **Average price:** ${sum(prices) / len(prices):.2f}")
            lines.append(f"- **Total products scanned:** {len(gumroad)}")

    total_hn_points = sum(h.get("points", 0) for h in hn)
    total_hn_comments = sum(h.get("num_comments", 0) for h in hn)
    total_devto_reactions = sum(a.get("reactions", 0) for a in devto)

    lines.append(f"- **HN community activity:** {total_hn_points} total points, {total_hn_comments} comments across {len(hn)} stories")
    lines.append(f"- **Dev.to engagement:** {total_devto_reactions} reactions across {len(devto)} articles")
    lines.append(f"- **Product Hunt signals:** {len(producthunt)} products identified")
    lines.append("")

    lines.append("### \U0001f52e Key Observations")
    lines.append("")

    observations = []
    if total_hn_points > 50:
        observations.append(
            f"\U0001f525 **High interest on Hacker News** \u2014 {total_hn_points} points "
            f"suggest strong community interest in AI prompt tools."
        )
    elif total_hn_points > 0:
        observations.append(
            f"\U0001f4c8 **Moderate HN activity** \u2014 {total_hn_points} points across {len(hn)} stories."
        )

    if len(producthunt) >= 10:
        observations.append(
            f"\U0001f680 **Active Product Hunt landscape** \u2014 {len(producthunt)} AI products "
            f"found, indicating a competitive market."
        )

    if prices:
        avg_price = sum(prices) / len(prices)
        if avg_price < 10:
            observations.append(
                f"\U0001f4b0 **Low-price market** (avg ${avg_price:.2f}) \u2014 "
                f"competitors are pricing aggressively. Consider premium positioning "
                f"if quality differentiates."
            )
        elif avg_price < 30:
            observations.append(
                f"\U0001f4b5 **Mid-range pricing** (avg ${avg_price:.2f}) \u2014 "
                f"standard for digital products in this space."
            )
        else:
            observations.append(
                f"\U0001f48e **Premium pricing observed** (avg ${avg_price:.2f}) \u2014 "
                f"room for high-margin positioning."
            )

    if not observations:
        observations.append(
            "\U0001f4e1 **Limited data this scan** \u2014 some sources may be JS-rendered. "
            "Run again or check sources manually for comprehensive intel."
        )

    for obs in observations:
        lines.append(obs + "\n")

    lines.append("---")
    lines.append(f"*Cache: {CACHE_FILE} (TTL: {CACHE_TTL_SECONDS // 3600}h) \u2014 "
                 f"run with --no-cache to force refresh.*")
    lines.append("")

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Competitor Intelligence Scanner \u2014 scan Gumroad, Product Hunt, "
                    "HN, Dev.to for AI prompt pack / digital product intel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s                              # full scan, use cache\n"
            "  %(prog)s --no-cache                    # full scan, skip cache\n"
            "  %(prog)s --output brief.md             # write to file\n"
            "  %(prog)s --source gumroad              # only scan Gumroad\n"
            "  %(prog)s --query \"prompt template\"     # custom search query\n"
            "  %(prog)s --ttl 3600                    # 1-hour cache TTL\n"
        ),
    )
    parser.add_argument(
        "--query",
        default="AI prompt pack",
        help="Search query for Gumroad and HN (default: 'AI prompt pack')",
    )
    parser.add_argument(
        "--hn-limit",
        type=int,
        default=20,
        help="Max hits from Hacker News Algolia (default: 20)",
    )
    parser.add_argument(
        "--devto-limit",
        type=int,
        default=15,
        help="Max articles from Dev.to (default: 15)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write brief to file instead of stdout",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache and re-fetch all sources",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=CACHE_TTL_SECONDS,
        help=f"Cache TTL in seconds (default: {CACHE_TTL_SECONDS})",
    )
    parser.add_argument(
        "--source",
        choices=["gumroad", "producthunt", "hn", "devto", "all"],
        default="all",
        help="Only scan a specific source (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results instead of markdown brief",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557", file=sys.stderr)
    print("\u2551  \U0001f916 Competitor Intelligence Scanner      \u2551", file=sys.stderr)
    print("\u2551  AI Prompt Packs & Digital Products       \u2551", file=sys.stderr)
    print("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d", file=sys.stderr)
    print(file=sys.stderr)

    # Check cache
    if not args.no_cache:
        cached = _cache_load(args.ttl)
        if cached is not None:
            print("\U0001f4e6 Using cached results (--no-cache to refresh).\n", file=sys.stderr)
            if args.json:
                print(json.dumps(cached, indent=2, ensure_ascii=False))
                return
            brief = generate_brief(
                cached.get("gumroad", []),
                cached.get("producthunt", []),
                cached.get("hn", []),
                cached.get("devto", []),
            )
            if args.output:
                with open(args.output, "w") as f:
                    f.write(brief)
                print(f"\U0001f4c4 Brief written to {args.output}", file=sys.stderr)
            else:
                print(brief)
            return

    # Run scans
    results = {
        "gumroad": [],
        "producthunt": [],
        "hn": [],
        "devto": [],
        "scanned_at": _now_iso(),
    }

    sources_enabled = {
        "gumroad": args.source in ("all", "gumroad"),
        "producthunt": args.source in ("all", "producthunt"),
        "hn": args.source in ("all", "hn"),
        "devto": args.source in ("all", "devto"),
    }

    if sources_enabled["gumroad"]:
        results["gumroad"] = scan_gumroad(query=args.query)
    if sources_enabled["producthunt"]:
        results["producthunt"] = scan_producthunt()
    if sources_enabled["hn"]:
        results["hn"] = scan_hacker_news(query=args.query, limit=args.hn_limit)
    if sources_enabled["devto"]:
        results["devto"] = scan_devto(limit=args.devto_limit)

    # Cache results (strip metadata)
    _cache_save({
        "gumroad": results["gumroad"],
        "producthunt": results["producthunt"],
        "hn": results["hn"],
        "devto": results["devto"],
    })

    print(f"\n\U0001f4e6 Results cached to {CACHE_FILE}", file=sys.stderr)

    # Output
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    brief = generate_brief(
        results["gumroad"],
        results["producthunt"],
        results["hn"],
        results["devto"],
    )
    if args.output:
        with open(args.output, "w") as f:
            f.write(brief)
        print(f"\U0001f4c4 Brief written to {args.output}", file=sys.stderr)
    else:
        print(brief)


if __name__ == "__main__":
    main()
