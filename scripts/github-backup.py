#!/usr/bin/env python3
"""
GitHub Weekly Backup — Biz Bot
Backs up all scripts + cron configs to the hermes-bot-backups repo.
"""
import os
import sys
import json
import base64
from datetime import datetime
from pathlib import Path
import urllib.request

# Config
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "jackloh84/hermes-bot-backups"
BRANCH = "master"
BACKUP_PATHS = [
    "~/.hermes/profiles/bot4/scripts/",
    "~/.hermes/profiles/bot4/state/",
    "~/.hermes/profiles/bot4/cron/jobs.json",
]

SKIP_EXT = {".pyc", ".log", ".pid", ".swp", ".tmp", ".bak", ".mp4", ".mp3", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz"}
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules", "logs"}

def should_skip(path: Path) -> bool:
    if path.suffix.lower() in SKIP_EXT:
        return True
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False

def upload_file(repo_path: str, local_path: Path, sha: str = None) -> bool:
    """Upload one file to GitHub."""
    url = f"https://api.github.com/repos/{REPO}/contents/{repo_path}"
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    payload = {
        "message": f"backup: {repo_path} ({datetime.now().isoformat()[:10]})",
        "content": content,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "BizBot-Backup/1.0",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(f"  ❌ {repo_path}: {e}")
        return False

def get_sha(repo_path: str) -> str:
    """Get existing file SHA (None if not exists)."""
    url = f"https://api.github.com/repos/{REPO}/contents/{repo_path}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}", "User-Agent": "BizBot-Backup/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["sha"]
    except urllib.error.HTTPError:
        return None

def main():
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set")
        sys.exit(1)

    print(f"🔄 Backup starting — {datetime.now().isoformat()[:19]}")
    uploaded = 0
    failed = 0

    for backup_path in BACKUP_PATHS:
        p = Path(backup_path).expanduser()
        if not p.exists():
            continue

        # Single file
        if p.is_file():
            rel = f"backups/{p.name}"
            sha = get_sha(rel)
            if upload_file(rel, p, sha):
                print(f"  ✅ {rel}")
                uploaded += 1
            else:
                failed += 1
            continue

        # Directory
        for f in p.rglob("*"):
            if not f.is_file() or should_skip(f):
                continue
            rel = "backups/" + str(f.relative_to(Path("~").expanduser()))
            sha = get_sha(rel)
            if upload_file(rel, f, sha):
                print(f"  ✅ {rel}")
                uploaded += 1
            else:
                failed += 1

    print(f"\n📊 Done: {uploaded} uploaded, {failed} failed")

if __name__ == "__main__":
    main()