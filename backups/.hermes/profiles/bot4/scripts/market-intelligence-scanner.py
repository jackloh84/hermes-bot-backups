#!/usr/bin/env python3
"""
Market Intelligence Scanner — Autonomous Multi-Source Research
Biz Bot (bot4) for Jack Loh
==============================================================
Scans 5+ sources autonomously, extracts actionable signals,
produces a ready-to-act briefing. No human prompting needed.

Sources:
1. Hacker News Algolia — trending earning/business stories
2. GitHub trending — AI tools worth monetizing
3. Product Hunt — new products in creator economy
4. Polymarket — prediction market trends (read-only)
5. RSS/blogwatcher — saved feed monitoring

Output: Concise markdown brief with signal score (1-10) + action items
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
import re
import os
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
NOW = datetime.now(SGT)
DATE_STR = NOW.strftime("%Y-%m-%d %H:%M SGT")

BRIEF_SECTIONS = []
SIGNALS = []

def section(title, body):
    BRIEF_SECTIONS.append(f"\n## {title}\n\n{body}")

def add_signal(source, signal_text, score):
    SIGNALS.append({"source": source, "signal": signal_text, "score": score})

def safe_fetch(url, timeout=15):
    """Fetch URL with error handling, returns text or None."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json,text/html,*/*"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"__FETCH_ERROR__: {e}"

def fetch_hn_trending(limit=10):
    """Hacker News Algolia API — trending stories about earning/business/AI."""
    queries = ["gumroad", "digital+products", "solopreneur", "side+hustle",
               "AI+business", "monetization", "creator+economy"]
    results = []
    for q in queries:
        url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage=5"
        data = safe_fetch(url)
        if data and "__FETCH_ERROR__" not in data:
            try:
                parsed = json.loads(data)
                for hit in parsed.get("hits", []):
                    results.append({
                        "title": hit.get("title", ""),
                        "url": hit.get("url", ""),
                        "points": hit.get("points", 0),
                        "objectID": hit.get("objectID", ""),
                        "num_comments": hit.get("num_comments", 0)
                    })
            except json.JSONDecodeError:
                pass
    # Deduplicate by objectID, keep highest points
    seen = set()
    deduped = []
    for r in sorted(results, key=lambda x: -x["points"]):
        if r["objectID"] not in seen and r["points"] > 2:
            seen.add(r["objectID"])
            deduped.append(r)
    return deduped[:limit]

def fetch_github_trending():
    """GitHub trending — AI repos that could be monetized."""
    url = "https://api.github.com/search/repositories?q=AI+tool+created:>2026-06-01&sort=stars&order=desc&per_page=5"
    data = safe_fetch(url)
    if data and "__FETCH_ERROR__" not in data:
        try:
            parsed = json.loads(data)
            items = []
            for repo in parsed.get("items", [])[:5]:
                items.append({
                    "name": repo.get("full_name", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "description": repo.get("description", ""),
                    "url": repo.get("html_url", ""),
                    "language": repo.get("language", "N/A")
                })
            return items
        except json.JSONDecodeError:
            pass
    # Fallback: scrape trending page
    html = safe_fetch("https://github.com/trending/python?since=weekly")
    if html and "__FETCH_ERROR__" not in html:
        repos = []
        # Extract repo names from trending page
        for match in re.finditer(r'href="/([^"]+?)"', html):
            name = match.group(1)
            if "/" in name and len(name.split("/")) == 2:
                repos.append({"name": name})
                if len(repos) >= 5:
                    break
        return repos
    return []

def fetch_polymarket_trends():
    """Polymarket — query trending markets for business intelligence."""
    # Market volume as signal of where capital is flowing
    url = "https://gamma-api.polymarket.com/markets?tag=technology&closed=false&limit=5&order=volume&asc=false"
    data = safe_fetch(url)
    if data and "__FETCH_ERROR__" not in data:
        try:
            parsed = json.loads(data)
            markets = []
            for m in parsed[:5]:
                markets.append({
                    "question": m.get("question", ""),
                    "volume": m.get("volume", "0"),
                    "outcome": m.get("outcomePrices", ["N/A"]),
                    "tags": m.get("tags", [])
                })
            return markets
        except (json.JSONDecodeError, TypeError):
            pass
    return []

def fetch_rss_blogs():
    """Scan blogwatcher RSS feeds if installed."""
    try:
        result = subprocess.run(["blogwatcher-cli", "scan"],
                                capture_output=True, text=True, timeout=30)
        scan_out = result.stdout.strip() if result.stdout else ""
        result2 = subprocess.run(["blogwatcher-cli", "articles", "--limit", "10"],
                                 capture_output=True, text=True, timeout=15)
        articles = result2.stdout.strip() if result2.stdout else ""
        return scan_out + "\n" + articles
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return "blogwatcher-cli not installed or error"
    except Exception:
        return "blogwatcher-cli unavailable"

def extract_signals():
    """Analyze all collected data, extract high-signal insights."""
    signal_items = []
    
    # Combine and rank
    for s in SIGNALS:
        signal_items.append(f"[{s['score']}/10 | {s['source']}] {s['signal']}")
    
    return "\n".join(signal_items) if signal_items else "No significant signals detected this scan."

def build_action_items():
    """From signals, generate concrete action items Jack can take."""
    actions = []
    for s in sorted(SIGNALS, key=lambda x: -x["score"])[:5]:
        if s["score"] >= 7:
            actions.append(f"🔴 HIGH: {s['signal']}")
        elif s["score"] >= 4:
            actions.append(f"🟡 MEDIUM: {s['signal']}")
        else:
            actions.append(f"🟢 LOW: {s['signal']}")
    return "\n".join(actions) if actions else "No urgent action items."

# ==============================================================
# EXECUTION
# ==============================================================

print(f"# Market Intelligence Brief — {DATE_STR}")
print(f"_Generated autonomously by Biz Bot (bot4) | No human prompt_")
print(f"\n---")

# 1. Hacker News Trending
hn_stories = fetch_hn_trending(8)
if hn_stories and not isinstance(hn_stories, str):
    items = []
    for s in hn_stories:
        items.append(f"- **{s['title']}** ({s['points']} pts, {s['num_comments']} comments)")
        # Signal extraction
        title_lower = s['title'].lower()
        if any(kw in title_lower for kw in ["gumroad", "digital product", "sell", "monetize", "revenue", "profit", "passive income"]):
            add_signal("HN", f"Earning-relevant story: {s['title']}", 7)
        elif any(kw in title_lower for kw in ["AI", "prompt", "automation", "tool"]):
            add_signal("HN", f"AI trend: {s['title']}", 5)
    section("Hacker News — Earning & Business Signals", "\n".join(items) if items else "No stories found")
else:
    section("Hacker News — Earning & Business Signals", "No stories found (API rate limit)")

# 2. GitHub Trending AI Tools
gh_repos = fetch_github_trending()
if gh_repos:
    items = []
    for r in gh_repos:
        desc = r.get('description', '')[:100] if r.get('description') else 'No description'
        stars = r.get('stars', 'N/A')
        items.append(f"- **{r['name']}** ⭐{stars} — {desc}")
        if any(kw in r['name'].lower() + desc.lower() for kw in ["prompt", "content", "writing", "marketing", "video", "image", "automation"]):
            add_signal("GitHub", f"Monetizable tool: {r['name']} — {desc[:80]}", 6)
    section("GitHub Trending — AI Tools Worth Watching", "\n".join(items))
else:
    section("GitHub Trending — AI Tools", "API limited; check manually at https://github.com/trending")

# 3. Polymarket Trends
pm_markets = fetch_polymarket_trends()
if pm_markets:
    items = []
    for m in pm_markets:
        q = m.get('question', '')[:80]
        vol = m.get('volume', '0')
        items.append(f"- **{q}** — Vol: ${vol}")
        add_signal("Polymarket", f"Capital flowing into: {q} (${vol} volume)", 6)
    section("Polymarket — Where Capital Is Flowing (Read-Only)", "\n".join(items))
else:
    section("Polymarket Markets", "Read-only query unavailable (expected — API access may be blocked in SG)")

# 4. RSS/Blogwatcher Feed
rss_out = fetch_rss_blogs()
if rss_out and "not installed" not in rss_out.lower():
    # Extract article titles and URLs for signal
    lines = rss_out.strip().split("\n")
    shown = [l for l in lines if l.strip() and len(l.strip()) > 15][:8]
    if shown:
        section("RSS Feeds — Latest Articles", "\n".join(shown))
    else:
        section("RSS Feeds", "No new articles since last scan")
else:
    section("RSS Feeds", "blogwatcher-cli not installed — run setup to enable RSS monitoring")

# 5. Signal Extraction & Action Items
section("📊 Signal Summary", extract_signals())
section("🎯 Action Items", build_action_items())

# 6. Autonomous Earning Opportunity Spotlight
# This is where the AI identifies THE BEST opportunity found
# Let the LLM-driven cron fill this section — this script just collects data

print(f"\n---\n_Scan complete. Data ready for LLM-driven analysis._")
print(f"_Sources checked: HN Algolia, GitHub API, Polymarket gamma-api, RSS_")
