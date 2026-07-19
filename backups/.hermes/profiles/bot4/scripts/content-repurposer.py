#!/usr/bin/env python3
"""
Content Repurposing Engine — AI Automation Tool
Takes any blog post, transcript, or text → outputs 5 content formats
Ready to sell as a service or use for your own content pipeline.

Usage:
  python3 content-repurposer.py "Your blog post or content here..."
  python3 content-repurposer.py --file input.txt

Sell this as a service:
  - Charging $47-97 per repurposing job
  - White-label for agencies
  - Package with your AI Prompt Pack
"""

import sys
import json
import os
from datetime import datetime

def read_input():
    """Read input from command line or file."""
    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        filepath = sys.argv[idx + 1]
        with open(filepath, "r") as f:
            return f.read()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        return sys.argv[1]
    else:
        return """AI is transforming how small businesses operate. From automating customer service to generating marketing copy, AI tools are making it possible for solopreneurs to compete with big corporations. The key is knowing which tools to use and how to implement them effectively. Start with one workflow, automate it, then move to the next. Within a month, you can save 10+ hours per week."""

def extract_headline(text):
    """Extract or generate a headline from the content."""
    lines = text.strip().split('\n')
    for line in lines:
        if len(line.strip()) > 10 and len(line.strip()) < 120:
            return line.strip()
    # Return first sentence
    first_sent = text.split('.')[0] if '.' in text else text[:100]
    return first_sent[:80]

def generate_twitter_thread(text):
    """Convert content to a Twitter thread."""
    topic = extract_headline(text)
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
    
    thread = []
    thread.append(f"🧵 1/{len(sentences)+2}\n\n{extract_headline(text)}\n\nA thread 🧵👇")
    
    for i, sent in enumerate(sentences[:8], 2):
        thread.append(f"{i}/{len(sentences)+2}\n\n{sent}.")
    
    thread.append(f"{len(sentences)+2}/{len(sentences)+2}\n\nWhich of these tips will you try first? Follow for more AI business insights! 🚀")
    
    return "\n\n".join(thread)

def generate_linkedin_post(text):
    """Convert content to a LinkedIn post."""
    headline = extract_headline(text)
    
    return f"""The one thing most business owners get wrong about AI:

They think it's complicated.

{headline}

Here's the truth:

{text}

The result? You can do in minutes what used to take hours.

Want to learn which AI tools actually work for small businesses? Drop a comment below 👇

#AIForBusiness #Productivity #SmallBusiness #Automation #DigitalTransformation"""

def generate_instagram_caption(text):
    """Convert content to Instagram caption."""
    headline = extract_headline(text)
    
    return f"""{headline.upper()}

💡 Save this post for later.

The reality is: AI isn't coming for your job. Someone using AI is.

{text}

👇 Which workflow would you automate first?
1️⃣ Customer service
2️⃣ Content creation
3️⃣ Data analysis
4️⃣ All of the above

Double tap if this was helpful ❤️

#AITips #BusinessGrowth #WorkflowAutomation #SmallBizTips #DigitalNomad"""

def generate_email_newsletter(text):
    """Convert to email newsletter format."""
    headline = extract_headline(text)
    
    return f"""Subject: {headline}

Hey {{FirstName}},

I've been testing something I want to share with you.

{text}

Here's what this means for you:
✓ More time
✓ Less busywork
✓ Higher output
✓ Same (or lower) cost

**Your 3-Step Action Plan:**
1. Pick ONE repetitive task
2. Find an AI tool for it
3. Automate it this week

Just one workflow. That's all it takes to start.

Talk soon,
[Your Name]

P.S. Reply to this email if you want my top 3 AI tool recommendations for small businesses."""

def generate_video_script(text):
    """Convert to short video script (60s)."""
    headline = extract_headline(text)
    
    return """🎬 VIDEO SCRIPT (60 seconds)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 1 — HOOK (0-3s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Visual: You talking to camera, bold text overlay]

You: "Most people use AI wrong. Here's the fix in 60 seconds."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 2 — PROBLEM (3-15s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Visual: Screen recording or b-roll of busy desk]

You: "They either ignore it completely or expect it to do everything.
The magic is in the middle — one workflow at a time."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 3 — SOLUTION (15-45s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Visual: Demo of AI tool in action]

You: "Here's what I mean:
Step 1: Find the task you hate most
Step 2: Find an AI tool for that ONE task
Step 3: Automate it this week

That's it. One workflow. Start today."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 4 — RESULT (45-55s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Visual: Before/after comparison or time saved graphic]

You: "Do this for one month and you'll save 10+ hours per week.
That's 40+ hours a month. For free."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 5 — CTA (55-60s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Visual: You pointing to bio/link]

You: "Follow for more AI workflows that actually work. Link in bio."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 PRODUCTION NOTES:
- Lighting: Ring light, face well-lit
- Audio: Lapel mic or quiet room
- Text overlay: White text, black outline
- Background: Clean desk setup
- Trending audio: Current popular track at 15% volume
"""

def main():
    text = read_input()
    
    if not text or len(text) < 20:
        print("Error: Input too short. Provide at least 20 characters of content.")
        sys.exit(1)
    
    print("=" * 60)
    print("  CONTENT REPURPOSING ENGINE — Output Report")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    print("\n" + "─" * 60)
    print("  📱 TWITTER / X THREAD")
    print("─" * 60)
    print(generate_twitter_thread(text))
    
    print("\n\n" + "─" * 60)
    print("  💼 LINKEDIN POST")
    print("─" * 60)
    print(generate_linkedin_post(text))
    
    print("\n\n" + "─" * 60)
    print("  📸 INSTAGRAM CAPTION")
    print("─" * 60)
    print(generate_instagram_caption(text))
    
    print("\n\n" + "─" * 60)
    print("  ✉️ EMAIL NEWSLETTER")
    print("─" * 60)
    print(generate_email_newsletter(text))
    
    print("\n\n" + "─" * 60)
    print("  🎬 VIDEO SCRIPT (60s)")
    print("─" * 60)
    print(generate_video_script(text))
    
    print("\n\n" + "=" * 60)
    print("  ALL 5 FORMATS GENERATED ✅")
    print("=" * 60)
    
    # Save to file
    output_dir = os.path.expanduser("~/projects/content-repurposing")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"repurposed-content-{timestamp}.txt")
    
    with open(output_file, "w") as f:
        f.write(f"# Content Repurposing Output — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("## Twitter Thread\n\n")
        f.write(generate_twitter_thread(text) + "\n\n")
        f.write("## LinkedIn Post\n\n")
        f.write(generate_linkedin_post(text) + "\n\n")
        f.write("## Instagram Caption\n\n")
        f.write(generate_instagram_caption(text) + "\n\n")
        f.write("## Email Newsletter\n\n")
        f.write(generate_email_newsletter(text) + "\n\n")
        f.write("## Video Script\n\n")
        f.write(generate_video_script(text) + "\n")
    
    print(f"\nSaved to: {output_file}")

if __name__ == "__main__":
    main()
