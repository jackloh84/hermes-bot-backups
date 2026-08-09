#!/usr/bin/env python3
"""gh_watch.py — watch selected GitHub repos for NEW issues (bounties/opportunities).

Repos watched (from Jack's forwarded emails; Tenstorrent EXCLUDED — off-limits):
  - runxhq/runx
  - moorcheh-ai/memanto

Prints new issues (compact) to stdout; prints NOTHING when nothing new (watchdog pattern).
State: ~/.hermes/profiles/bot4/state/gh_watch_seen.json  (seen issue numbers per repo)
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone

REPOS = ["runxhq/runx", "moorcheh-ai/memanto"]
STATE_FILE = os.path.expanduser("~/.hermes/profiles/bot4/state/gh_watch_seen.json")
ENV_FILES = ["/home/ubuntu/.hermes/.env", "/home/ubuntu/.hermes/profiles/bot4/.env"]
UA = {"User-Agent": "jackloh-bizbot-gh-watch", "Accept": "application/vnd.github+json"}

def load_token():
    for f in ENV_FILES:
        if os.path.exists(f):
            for line in open(f):
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def gh_get(url, token):
    hdrs = dict(UA)
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def load_seen():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {}

def main():
    token = load_token()
    seen = load_seen()
    new_items = []
    for repo in REPOS:
        try:
            issues = gh_get(f"https://api.github.com/repos/{repo}/issues?state=open&sort=created&direction=desc&per_page=20", token)
        except Exception as e:
            new_items.append(f"[{repo}] ERROR: {str(e)[:120]}")
            continue
        repo_seen = set(seen.get(repo, []))
        fresh = [i for i in issues if isinstance(i, dict) and "pull_request" not in i and i.get("number") not in repo_seen]
        # sort newest first
        fresh.sort(key=lambda i: i.get("created_at", ""), reverse=True)
        for i in fresh[:6]:
            labels = ",".join(l.get("name", "") for l in i.get("labels", [])) or "none"
            body = (i.get("body") or "").replace("\r", " ").replace("\n", " ")[:220]
            title = i.get("title", "")
            # bounty/paid signal: labels or title mention reward keywords
            low = (labels + " " + title).lower()
            sig = "⭐" if any(k in low for k in ["bounty", "reward", "paid", "$", "usdc", "funded", "sponsor"]) else "  "
            new_items.append(
                f"{sig}🔔 {repo} #{i['number']} [{labels}]\n"
                f"   {title}\n"
                f"   {i.get('html_url','')}\n"
                f"   {body}"
            )
            repo_seen.add(i["number"])
        seen[repo] = sorted(repo_seen)
    if new_items:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        json.dump(seen, open(STATE_FILE, "w"), indent=1)
        print(f"GH WATCH — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ({len(new_items)} new)\n")
        print("\n\n".join(new_items))

if __name__ == "__main__":
    main()
