#!/usr/bin/env python3
"""TikTok Collaboration Hub — Biz Bot → CC Bot Handoff

Biz Bot (me) researches, plans, and generates creative briefs.
CC Bot reads the brief and executes video production.

Workflow:
1. Biz Bot runs: research product → check policy → write brief → save here
2. CC Bot polls: read latest task → film/edit → mark complete → post
"""
import json, datetime
from pathlib import Path

HUB_DIR = Path.home() / ".hermes" / "profiles" / "bot4" / "state" / "tiktok-hub"
TASKS_FILE = HUB_DIR / "tasks.json"
HUB_DIR.mkdir(parents=True, exist_ok=True)

# Product categories and their TikTok Shop info
PRODUCTS = {
    "anker-soundcore-2": {
        "name": "Anker Soundcore 2 Bluetooth Speaker",
        "price": "$31.99 SGD",
        "commission": "5-15%",
        "features": ["IPX7 Waterproof", "24H Battery", "12W BassUp", "Bluetooth 5.0"],
        "tiktok_shop_url": "https://www.tiktok.com/@shop/anker-soundcore-2",
        "notes": "Best selling point is waterproof test. Micro USB is the main con.",
    },
}

def create_task(product_key, format_preference="auto"):
    """Create a new task for CC Bot."""
    product = PRODUCTS.get(product_key)
    if not product:
        available = list(PRODUCTS.keys())
        return {"error": f"Unknown product. Available: {available}"}
    
    task = {
        "id": datetime.datetime.now().strftime("TASK-%Y%m%d-%H%M%S"),
        "created_by": "Biz Bot (@her_a04_bot)",
        "assigned_to": "CC Bot (@her_a03_bot)",
        "product": product["name"],
        "product_key": product_key,
        "price": product["price"],
        "commission": product["commission"],
        "key_features": product["features"],
        "format_preference": format_preference,
        "status": "ready",
        "created_at": datetime.datetime.now().isoformat(),
        "brief_file": None,
        "completed_at": None,
        "notes": product.get("notes", ""),
    }
    
    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)
    return task

def load_tasks():
    """Load all tasks."""
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return []

def save_tasks(tasks):
    """Save tasks."""
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, default=str))

def mark_complete(task_id):
    """Mark a task as completed."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["completed_at"] = datetime.datetime.now().isoformat()
            save_tasks(tasks)
            return {"ok": True, "task": t}
    return {"error": f"Task {task_id} not found"}

def get_next_task():
    """Get the next ready task for CC Bot."""
    tasks = load_tasks()
    ready = [t for t in tasks if t["status"] == "ready"]
    if ready:
        return ready[0]
    return {"message": "No pending tasks"}

def list_tasks():
    """List all tasks."""
    tasks = load_tasks()
    if not tasks:
        print("📭 No tasks yet")
        return
    for t in tasks:
        status_icon = "✅" if t["status"] == "completed" else "🔄" if t["status"] == "in-progress" else "📋"
        print(f"  {status_icon} {t['id']}")
        print(f"     Product: {t['product']}")
        print(f"     By: {t['created_by']} → {t['assigned_to']}")
        print(f"     Status: {t['status']}")
        print(f"     Created: {t['created_at'][:16]}")
        if t.get("completed_at"):
            print(f"     Done: {t['completed_at'][:16]}")
        print()

def cc_bot_summary():
    """Generate a summary CC Bot can read to know what to do."""
    task = get_next_task()
    if "message" in task:
        return "📭 No pending tasks for CC Bot."
    
    return f"""
═══════════════════════════════════════
🎬 TIKTOK TASK FOR CC BOT (@her_a03_bot)
═══════════════════════════════════════

📋 Task: {task['id']}
📦 Product: {task['product']}
💰 Price: {task['price']} | Commission: {task['commission']}
🎯 Format: {task['format_preference']}
📌 Key Features: {', '.join(task['key_features'])}

📝 Notes: {task['notes']}

📄 Full brief: ~/gumroad-promo/tiktok-brief-{task['product_key']}.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CC Bot — please:
1. Read the brief file
2. Check policy checklist
3. Film/edit the video
4. Post with #ad #affiliate
5. Mark task complete: mark_complete("{task['id']}")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tiktok-hub.py create <product_key> [format]  — New task")
        print("  python3 tiktok-hub.py list                          — Show all tasks")
        print("  python3 tiktok-hub.py next                          — Next task for CC")
        print("  python3 tiktok-hub.py done <task_id>                — Mark complete")
        print("  python3 tiktok-hub.py summary                       — CC Bot summary")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == "create" and len(sys.argv) > 2:
        key = sys.argv[2]
        fmt = sys.argv[3] if len(sys.argv) > 3 else "auto"
        result = create_task(key, fmt)
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ Task created: {result['id']}")
            print(f"   Product: {result['product']}")
            print(f"   CC Bot can see it: python3 tiktok-hub.py next")
    elif cmd == "list":
        list_tasks()
    elif cmd == "next":
        task = get_next_task()
        if "message" in task:
            print(task["message"])
        else:
            print(f"📋 Next task: {task['id']}")
            print(f"   {task['product']} — Status: {task['status']}")
            print(f"   Created: {task['created_at'][:16]}")
    elif cmd == "done" and len(sys.argv) > 2:
        result = mark_complete(sys.argv[2])
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ Task {sys.argv[2]} marked complete")
    elif cmd == "summary":
        print(cc_bot_summary())
    else:
        print("Unknown command")
