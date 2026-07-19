#!/usr/bin/env python3
"""
Daily Affiliate Product Scout — Hermes Automation Script
Scrapes trending products and generates affiliate video concepts.
Outputs a markdown report with hooks, scripts, and product links.
"""

import json
import sys
from datetime import datetime

def get_daily_briefing():
    """Generate today's content briefing based on day of week."""
    day = datetime.now().strftime("%A")
    date = datetime.now().strftime("%Y-%m-%d")
    
    # Product rotation based on day
    rotation = {
        "Monday": {
            "theme": "Tech Gadgets",
            "hook_angle": "Budget-friendly tech that actually works",
            "focus": "USB-C accessories, chargers, cables"
        },
        "Tuesday": {
            "theme": "Productivity",
            "hook_angle": "Tools that save you 2 hours/day",
            "focus": "Desk organization, planners, apps"
        },
        "Wednesday": {
            "theme": "AI/Software",
            "hook_angle": "AI tools replacing expensive subscriptions",
            "focus": "Prompt packs, AI templates, automation tools"
        },
        "Thursday": {
            "theme": "Lifestyle Gadgets",
            "hook_angle": "Under $20 upgrades everyone needs",
            "focus": "Phone accessories, lighting, small electronics"
        },
        "Friday": {
            "theme": "Weekend Setup",
            "hook_angle": "Weekend upgrade for your workspace",
            "focus": "Desk accessories, cable management, audio"
        },
        "Saturday": {
            "theme": "Review/Roundup",
            "hook_angle": "Best things I bought this week",
            "focus": "Top 5 products from this week"
        },
        "Sunday": {
            "theme": "Planning/Prep",
            "hook_angle": "Set up your week in 10 minutes",
            "focus": "Weekly planning, productivity systems"
        }
    }
    
    today = rotation.get(day, rotation["Monday"])
    
    return {
        "date": date,
        "day": day,
        "theme": today["theme"],
        "hook_angle": today["hook_angle"],
        "focus": today["focus"]
    }

def generate_video_concept(briefing):
    """Generate a video concept based on the daily briefing."""
    
    hooks = {
        "Tech Gadgets": [
            "Stop overpaying for tech. Here's what actually works.",
            "I tested 10 budget gadgets. Only 2 survived.",
            "This $15 gadget replaced 3 things on my desk."
        ],
        "Productivity": [
            "I automated 80% of my work. Here's how.",
            "You're wasting 2 hours a day. Fix it in 10 minutes.",
            "My secret weapon? It costs less than coffee."
        ],
        "AI/Software": [
            "I fired 3 subscriptions. Replaced them with AI.",
            "Your boss doesn't want you to know about this.",
            "This prompt does what 5 apps used to do."
        ],
        "Lifestyle Gadgets": [
            "Everything in this video is under $20.",
            "You already own 90% of what you need.",
            "These cheap upgrades feel premium."
        ],
        "Weekend Setup": [
            "Your desk is costing you money. Fix it.",
            "I spent $50 and my productivity doubled.",
            "The 10-minute desk transformation."
        ],
        "Review/Roundup": [
            "5 things under $50 that changed my workflow.",
            "My weekly tech picks that actually deliver.",
            "Don't buy anything until you see these."
        ],
        "Planning/Prep": [
            "Sunday ritual that sets up my whole week.",
            "10 minutes on Sunday saves 5 hours this week.",
            "The system that made me actually productive."
        ]
    }
    
    today_hooks = hooks.get(briefing["theme"], hooks["Tech Gadgets"])
    
    hashtag_theme = briefing['theme'].replace(' ', '').replace('/', '-')
    return {
        "hook": today_hooks[0],
        "alt_hooks": today_hooks[1:],
        "best_post_time": "7:00 PM SGT",
        "hashtags": f"#{hashtag_theme} #affiliate #tiktokshop #fyp #productivity"
    }

def main():
    briefing = get_daily_briefing()
    concept = generate_video_concept(briefing)
    
    report = f"""# Daily Content Briefing — {briefing['date']} ({briefing['day']})

## Today's Theme: {briefing['theme']}

### Hook Angle
> {briefing['hook_angle']}

### Focus Products
> {briefing['focus']}

---

## Recommended Video Concept

### Primary Hook
> "{concept['hook']}"

### Alternative Hooks
1. "{concept['alt_hooks'][0]}"
2. "{concept['alt_hooks'][1]}"

### Production Specs
| Element | Value |
|---------|-------|
| Best post time | {concept['best_post_time']} |
| Ideal length | 45-60 seconds |
| Hashtags | {concept['hashtags']} |
| Format | Talking head + b-roll |

---

## Quick Script Outline

**0-3s:** Hook with visual demonstration
**3-15s:** State the problem (relatable pain point)
**15-40s:** Show the solution (product demo, before/after)
**40-50s:** Results/proof (testimonial or data)
**50-60s:** CTA — "Link in bio"

---

*Generated automatically by Hermes Agent - {briefing['date']}*
"""
    
    print(report)

if __name__ == "__main__":
    main()
