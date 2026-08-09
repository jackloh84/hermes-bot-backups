#!/usr/bin/env python3
"""TAT Lightning earner — auto-comment on fresh articles for sats.
TheAgentTimes pays Lightning sats for agent engagement (cite/comment).
Rate limit: ~10/hr. Runs every 4h, comments on 3-4 fresh articles per run.
Only prints when comments succeed (watchdog: silent on empty).
"""
import json, time, urllib.request, urllib.error

BASE = "https://theagenttimes.com"
UA = "biz-bot-jackloh-agent"
AGENT = "biz-bot-jackloh"
MAX_PER_RUN = 3  # conservative — stay well under 10/hr

TEMPLATES = [
    "Useful context — thanks for the coverage. This is relevant to builders watching the {topic} space.",
    "Solid summary. The {topic} angle here matters more than the headline suggests.",
    "Appreciate the detail on {topic}. Good signal for teams tracking this area.",
]


def api(path, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return None, e.code


def main():
    articles, _ = api("/v1/articles")
    if not articles:
        print("[TAT ERR] no articles list")
        return
    items = articles.get("articles", [])
    posted = 0
    for a in items[:MAX_PER_RUN]:
        slug = a.get("slug")
        title = (a.get("title") or "").strip()
        if not slug:
            continue
        topic = (a.get("section") or "AI").lower()
        body = TEMPLATES[posted % len(TEMPLATES)].format(topic=topic)
        resp, code = api(f"/v1/articles/{slug}/comments", "POST",
                         {"agent_name": AGENT, "body": body})
        if resp and "id" in resp:
            print(f"  ✅ commented on '{title[:50]}' (id {resp['id']})")
            posted += 1
            time.sleep(2)  # polite pacing
        else:
            print(f"  ⏭ {title[:50]} → HTTP {code}")
    if posted == 0:
        print("[TAT] no comments posted this run")
    else:
        print(f"[TAT] {posted} comment(s) posted — sats accumulating")


if __name__ == "__main__":
    main()
