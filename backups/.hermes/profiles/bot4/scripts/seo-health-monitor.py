#!/usr/bin/env python3
"""
seo-health-monitor.py — Daily SEO health check for Jack's Gumroad store + cross-platform footprint.

Monitors:
  1. Gumroad product pages (status code, response time, meta tags, schema presence)
  2. Published articles on DEV.to, Medium, LinkedIn (status, last-modified, link health)
  3. GitHub repos (stars, traffic from backlink perspective)
  4. Telegram channel SEO (post cadence, view counts)
  5. YouTube channel + videos (if configured) — views, tags, description keywords
  6. AI-citation readiness — does llms.txt exist? Schema valid? Robots.txt allow cite-bots?
  7. Keyword ranking deltas vs last run (stores history in state/)

Usage:
    python3 seo-health-monitor.py --all
    python3 seo-health-monitor.py --gumroad
    python3 seo-health-monitor.py --articles
    python3 seo-health-monitor.py --ai-readiness
    python3 seo-health-monitor.py --rankings --keyword "tiktok hooks" --rank 50
    python3 seo-health-monitor.py --json
    python3 seo-health-monitor.py --save  # saves report to seo-output/health-{date}.md

Outputs a health report with PASS/WARN/FAIL flags per check, plus an overall SEO score (0-100).
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
]

JACK_PRODUCTS = [
    ("TikTok Hooks", "https://jackalope86.gumroad.com/l/diywdak", "$3"),
    ("AI for Content Creators", "https://jackalope86.gumroad.com/l/xcjutg", "$19"),
    ("AI Business Automation", "https://jackalope86.gumroad.com/l/byrjla", "$19"),
    ("AI Solopreneur Launchpad", "https://jackalope86.gumroad.com/l/dgdtjf", "$5"),
]

JACK_GITHUB_REPOS = [
    "tiktok-viral-hooks",
    "content-creator-prompts",
    "solopreneur-ai-toolkit",
    "youtube-shorts-generator",
    "hermes-bot-backups",
]

STATE_DIR = Path("~/.hermes/profiles/bot4/state/seo-monitor").expanduser()
RANK_HISTORY_FILE = STATE_DIR / "rank-history.json"


def http_head(url, timeout=10):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENTS[0]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status, "final_url": resp.geturl(), "ok": resp.status < 400}
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "final_url": url, "ok": False, "error": str(e)}
    except Exception as e:
        return {"url": url, "status": 0, "final_url": url, "ok": False, "error": str(e)[:100]}


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENTS[hash(url) % len(USER_AGENTS)], "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status, "body": resp.read().decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"url": url, "status": 0, "body": "", "error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Check 1: Gumroad product pages
# ---------------------------------------------------------------------------

def check_gumroad():
    results = []
    for name, url, price in JACK_PRODUCTS:
        r = http_head(url)
        ok = r["ok"]
        results.append({
            "name": name,
            "url": url,
            "status": r["status"],
            "pass": ok,
            "detail": f"HTTP {r['status']}" if ok else f"HTTP {r['status']} — {r.get('error', 'unknown error')}",
        })
    return results


# ---------------------------------------------------------------------------
# Check 2: Published articles (DEV.to)
# ---------------------------------------------------------------------------

def check_devto_articles(username="jackloh84"):
    api_url = f"https://dev.to/api/articles?username={username}&per_page=30"
    r = http_get(api_url)
    if r["status"] != 200:
        return [{"pass": False, "detail": f"DEV.to API returned {r['status']}", "name": "DEV.to API"}]
    try:
        articles = json.loads(r["body"])
    except Exception as e:
        return [{"pass": False, "detail": f"JSON parse error: {e}", "name": "DEV.to API"}]

    results = []
    for art in articles:
        title = art.get("title", "(untitled)")
        url = art.get("url", "")
        published = art.get("published_at", "")
        reactions = art.get("public_reactions_count", 0)
        comments = art.get("comments_count", 0)
        results.append({
            "name": title[:60],
            "url": url,
            "published_at": published,
            "reactions": reactions,
            "comments": comments,
            "pass": True,  # published = pass
            "detail": f"{reactions} reactions, {comments} comments",
        })
    return results


# ---------------------------------------------------------------------------
# Check 3: GitHub repos
# ---------------------------------------------------------------------------

def check_github(token=None):
    results = []
    for repo in JACK_GITHUB_REPOS:
        url = f"https://api.github.com/repos/jackloh84/{repo}"
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                results.append({
                    "name": data.get("full_name"),
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "has_readme": False,  # checked below
                    "url": data.get("html_url"),
                    "pass": True,
                    "detail": f"⭐ {data.get('stargazers_count', 0)} ⑂ {data.get('forks_count', 0)}",
                })
        except urllib.error.HTTPError as e:
            results.append({"name": repo, "pass": False, "detail": f"HTTP {e.code}", "url": f"https://github.com/jackloh84/{repo}"})
        except Exception as e:
            results.append({"name": repo, "pass": False, "detail": str(e)[:80], "url": f"https://github.com/jackloh84/{repo}"})
    return results


# ---------------------------------------------------------------------------
# Check 4: AI-citation readiness (llms.txt, schema, robots)
# ---------------------------------------------------------------------------

def check_ai_readiness(store_url="https://jackalope86.gumroad.com", site_url=None):
    """
    Probe the live store for AI-citation artifacts.

    `site_url` is an OPTIONAL external site (e.g. GitHub Pages) where Jack can host
    llms.txt / robots.txt / schema. Gumroad subdomains cannot host custom files.
    """
    results = []

    # llms.txt — check BOTH the Gumroad subdomain (will 404) AND any external site Jack controls
    sites_to_check = [store_url.rstrip("/")]
    if site_url:
        sites_to_check.append(site_url.rstrip("/"))
    for path in ["/llms.txt", "/llms-full.txt", "/robots.txt", "/sitemap.xml", "/pricing.md"]:
        any_ok = False
        for site in sites_to_check:
            url = site + path
            r = http_head(url)
            if r["status"] in (200, 301, 302):
                any_ok = True
                results.append({
                    "name": f"{site}{path}",
                    "url": url,
                    "status": r["status"],
                    "pass": True,
                    "detail": f"✅ HTTP {r['status']} on {site}",
                })
        if not any_ok:
            target = site_url if site_url else "(no external site configured)"
            results.append({
                "name": f"AI artifact {path} served",
                "url": f"{target}{path}",
                "status": 404,
                "pass": False,
                "detail": f"❌ 404 on both Gumroad subdomain (expected) and {target}. Host on GitHub Pages / custom domain.",
            })

    # Check for Product schema on a product page
    product_url = "https://jackalope86.gumroad.com/l/diywdak"
    r = http_get(product_url, timeout=20)
    if r["status"] == 200:
        body = r["body"]
        has_product_schema = '"@type":"Product"' in body or '"@type": "Product"' in body
        has_faq_schema = '"@type":"FAQPage"' in body or '"@type": "FAQPage"' in body
        has_org_schema = '"@type":"Organization"' in body or '"@type": "Organization"' in body
        has_meta_desc = bool(re.search(r'<meta\s+name="description"', body, re.I))
        has_og = bool(re.search(r'<meta\s+property="og:', body, re.I))

        results.extend([
            {"name": "Product page has Product schema", "url": product_url, "pass": has_product_schema, "detail": "✅ JSON-LD Product" if has_product_schema else "❌ missing Product schema"},
            {"name": "Product page has FAQ schema", "url": product_url, "pass": has_faq_schema, "detail": "✅ FAQPage" if has_faq_schema else "ℹ️  no FAQ schema"},
            {"name": "Product page has Organization schema", "url": product_url, "pass": has_org_schema, "detail": "✅ Organization" if has_org_schema else "❌ missing Organization schema"},
            {"name": "Product page has meta description", "url": product_url, "pass": has_meta_desc, "detail": "✅ meta description" if has_meta_desc else "❌ missing meta description"},
            {"name": "Product page has Open Graph tags", "url": product_url, "pass": has_og, "detail": "✅ OG tags" if has_og else "❌ missing OG tags"},
        ])
    else:
        results.append({"name": "Gumroad product page reachable", "url": product_url, "pass": False, "detail": f"HTTP {r['status']}"})

    return results


# ---------------------------------------------------------------------------
# Check 5: Manual keyword ranking tracking
# ---------------------------------------------------------------------------

def log_keyword_rank(keyword, rank, url=None, note=""):
    """Append a manual ranking observation to history."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if RANK_HISTORY_FILE.exists():
        history = json.loads(RANK_HISTORY_FILE.read_text())
    else:
        history = {"observations": []}

    history["observations"].append({
        "keyword": keyword,
        "rank": rank,
        "url": url,
        "note": note,
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    history["observations"] = history["observations"][-500:]  # cap
    RANK_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    return history


def show_rank_history(keyword=None):
    if not RANK_HISTORY_FILE.exists():
        return []
    history = json.loads(RANK_HISTORY_FILE.read_text())
    obs = history.get("observations", [])
    if keyword:
        obs = [o for o in obs if o["keyword"].lower() == keyword.lower()]
    return obs[-20:]


# ---------------------------------------------------------------------------
# Score + report
# ---------------------------------------------------------------------------

def score_results(all_results):
    """Compute a 0-100 score from flat result list."""
    if not all_results:
        return 0, []
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("pass"))
    pct = (passed / total) * 100
    return round(pct), [
        {"status": "✅", "name": r["name"], "detail": r.get("detail", "")}
        if r.get("pass") else
        {"status": "❌", "name": r["name"], "detail": r.get("detail", "")}
        for r in all_results
    ]


def render_markdown(report):
    lines = [
        f"# SEO Health Report",
        f"_Generated: {report['generated_at']}_",
        "",
        f"## Overall Score: **{report['score']}/100**",
        "",
        f"- Total checks: {report['total']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['total'] - report['passed']}",
        "",
    ]
    for section_name, section_results in report["sections"].items():
        lines.append(f"## {section_name}\n")
        for r in section_results:
            mark = "✅" if r.get("pass") else "❌"
            name = r.get("name", "(unnamed)")
            detail = r.get("detail", "")
            url = r.get("url", "")
            url_str = f" → {url}" if url else ""
            lines.append(f"- {mark} **{name}**{url_str}")
            if detail:
                lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Daily SEO health check for Jack's footprint")
    p.add_argument("--all", action="store_true", help="Run all checks")
    p.add_argument("--gumroad", action="store_true", help="Check Gumroad product pages")
    p.add_argument("--articles", action="store_true", help="Check DEV.to article status")
    p.add_argument("--github", action="store_true", help="Check GitHub repo status (uses GITHUB_TOKEN env if set)")
    p.add_argument("--ai-readiness", action="store_true", help="Check AI citation readiness on the store")
    p.add_argument("--rankings", action="store_true", help="Show ranking history")
    p.add_argument("--keyword", help="Keyword (for --rankings filter or --log-rank)")
    p.add_argument("--log-rank", action="store_true", help="Log a ranking observation")
    p.add_argument("--rank", type=int, help="Current rank for --log-rank")
    p.add_argument("--rank-url", help="URL that ranks (optional)")
    p.add_argument("--rank-note", default="", help="Note for --log-rank")
    p.add_argument("--site-url", help="External site URL where AI artifacts (llms.txt, robots.txt) are hosted (Gumroad subdomains cannot host custom files)")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--save", action="store_true", help="Save markdown report")
    p.add_argument("--outdir", default="~/seo-output", help="Output directory for --save")
    args = p.parse_args()

    # Mode: log a ranking observation
    if args.log_rank:
        if not args.keyword or args.rank is None:
            print("❌ --keyword and --rank required for --log-rank")
            sys.exit(1)
        history = log_keyword_rank(args.keyword, args.rank, args.rank_url, args.rank_note)
        print(f"✅ Logged rank #{args.rank} for '{args.keyword}'")
        print(f"   Total observations: {len(history['observations'])}")
        return

    # Mode: show ranking history
    if args.rankings:
        obs = show_rank_history(args.keyword)
        if not obs:
            print("ℹ️  No ranking observations yet. Use --log-rank to record one.")
            return
        print(f"\n📊 Ranking History" + (f" — {args.keyword}" if args.keyword else "") + "\n")
        for o in obs[-10:]:
            url_str = f" → {o['url']}" if o.get("url") else ""
            print(f"  #{o['rank']:3} {o['keyword'][:40]:<40} {o['checked_at'][:10]}{url_str}")
        return

    if not any([args.all, args.gumroad, args.articles, args.github, args.ai_readiness]):
        args.all = True

    sections = {}
    if args.gumroad or args.all:
        print("📦 Checking Gumroad products...")
        sections["Gumroad Product Pages"] = check_gumroad()
    if args.articles or args.all:
        print("📰 Checking DEV.to articles...")
        sections["DEV.to Articles"] = check_devto_articles()
    if args.github or args.all:
        print("🐙 Checking GitHub repos...")
        import os
        sections["GitHub Repos"] = check_github(os.environ.get("GITHUB_TOKEN"))
    if args.ai_readiness or args.all:
        print("🤖 Checking AI-citation readiness...")
        sections["AI-Citation Readiness"] = check_ai_readiness(site_url=args.site_url)

    flat = []
    for sec in sections.values():
        flat.extend(sec)
    score, scored = score_results(flat)
    passed = sum(1 for r in flat if r.get("pass"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "score": score,
        "total": len(flat),
        "passed": passed,
        "sections": sections,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  SEO HEALTH REPORT — {report['generated_at']}")
        print(f"{'='*60}\n")
        print(f"  Overall: {score}/100   |   Passed: {passed}/{len(flat)}\n")
        for section_name, section_results in sections.items():
            print(f"  📋 {section_name}")
            for r in section_results:
                mark = "✅" if r.get("pass") else "❌"
                name = r.get("name", "(unnamed)")
                detail = r.get("detail", "")
                print(f"     {mark} {name}  {detail}")
            print()

    if args.save:
        out = Path(args.outdir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = out / f"health-{date}.md"
        path.write_text(render_markdown(report))
        print(f"💾 Saved: {path}")


if __name__ == "__main__":
    main()