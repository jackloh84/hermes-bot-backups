#!/usr/bin/env python3
"""Execution Market task watcher — silent watchdog.
Prints ONLY when a worthwhile remote task appears:
  - location is null (remote digital work)
  - bounty >= $1.00
  - category in code/research/data/api (digital work, not physical presence)
Empty stdout = nothing to report = no message sent.
"""
import json, urllib.request

API = "https://api.execution.market/api/v1/tasks/available"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"}

GOOD_CATEGORIES = {"code_execution", "research", "data_collection", "data_processing",
                   "api_integration", "content_generation", "knowledge_access",
                   "multi_step_workflow", "verification", "social_proof", "creative"}
MIN_BOUNTY = 1.00


def main():
    try:
        req = urllib.request.Request(API, headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        print(f"[EXEC MARKET ERR] {e}")
        return

    tasks = data.get("tasks", [])
    good = []
    for t in tasks:
        if t.get("location"):  # geo/physical — skip
            continue
        cat = t.get("category", "")
        try:
            bounty = float(t.get("bounty_usd", 0))
        except (TypeError, ValueError):
            continue
        if bounty >= MIN_BOUNTY and cat in GOOD_CATEGORIES:
            good.append(t)

    if good:
        print("💼 EXECUTION MARKET — worthwhile remote tasks found!")
        for t in sorted(good, key=lambda x: float(x.get("bounty_usd", 0)), reverse=True):
            print(f"  ${float(t.get('bounty_usd', 0)):.2f} [{t.get('category')}] "
                  f"{t.get('title', '')[:80]}")
            print(f"    id: {t.get('id')}  deadline: {t.get('deadline', '?')[:10]}")
        print("\nApply: POST /api/v1/tasks/{id}/apply with executor_id "
              "d891323e-6a41-4d0f-9f80-8064736be5e3")


if __name__ == "__main__":
    main()
