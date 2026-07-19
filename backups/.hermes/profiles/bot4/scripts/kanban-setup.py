#!/usr/bin/env python3
"""Shared Kanban — Biz Bot + CC Bot collaboration board.

Both bots read/write to /tmp/tiktok-kanban.json
"""
import json, datetime
from pathlib import Path

KANBAN = Path("/tmp/tiktok-kanban.json")

TASKS = {
    "todo": [
        {"id": "T-001", "task": "Film Waterproof Test (30s)", "bot": "CC Bot", "product": "Anker Soundcore 2", "priority": "HIGH"},
        {"id": "T-002", "task": "Film Honest Review (30s)", "bot": "CC Bot", "product": "Anker Soundcore 2", "priority": "MED"},
        {"id": "T-003", "task": "Film Pool Setup (25s)", "bot": "CC Bot", "product": "Anker Soundcore 2", "priority": "LOW"},
    ],
    "in_progress": [],
    "done": [
        {"id": "B-001", "task": "Product specs research", "bot": "Biz Bot", "done_at": "2026-07-12T14:01"},
        {"id": "B-002", "task": "3 video scripts written", "bot": "Biz Bot", "done_at": "2026-07-12T14:01"},
        {"id": "B-003", "task": "TikTok policy checked", "bot": "Biz Bot", "done_at": "2026-07-12T14:01"},
        {"id": "B-004", "task": "Captions + hashtags ready", "bot": "Biz Bot", "done_at": "2026-07-12T14:01"},
        {"id": "B-005", "task": "Visual storyboard done", "bot": "Biz Bot", "done_at": "2026-07-12T14:01"},
    ],
    "files": [
        "~/gumroad-promo/tiktok-brief-anker-soundcore2.md",
        "/tmp/tiktok-storyboard/storyboard-preview.png",
        "/tmp/tiktok-storyboard/scene_01.png - scene_06.png",
    ],
    "posted_videos": [],
    "last_updated": datetime.datetime.now().isoformat()
}

KANBAN.write_text(json.dumps(TASKS, indent=2, default=str))
print(f"✅ Kanban saved: {KANBAN}")
print(f"   TO DO: {len(TASKS['todo'])} | DONE: {len(TASKS['done'])} | FILES: {len(TASKS['files'])}")
print(f"   CC Bot can read it: cat {KANBAN}")
