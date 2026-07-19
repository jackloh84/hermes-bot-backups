#!/usr/bin/env python3
"""Content SEO Grader v1.0

Scores any text/article for SEO readiness (0-100)
Checks: headings, keyword usage, readability, length, structure, links, meta.

Usage:
  ./content-seo-grader.py --file article.md    # Score a file
  ./content-seo-grader.py --text "content..." --keyword "tiktok hooks"
  ./content-seo-grader.py --article my_article.md --keyword "AI prompts"
  ./content-seo-grader.py --improve my_article.md  # Get fix suggestions
"""
import sys, re, os
from pathlib import Path

def count_syllables(word):
    word = word.lower().strip('.,!?;:')
    if not word: return 0
    vowels = 'aeiouy'
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith('e') and count > 1: count -= 1
    if word.endswith('le') and len(word) > 2: count += 1
    return max(1, count)

def flesch_kincaid(text):
    """Readability score. 60-70 = easy to read."""
    words = text.split()
    if len(words) < 10: return 0
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    if not sentences: return 0
    total_syllables = sum(count_syllables(w) for w in words)
    avg_words_per_sent = len(words) / len(sentences)
    avg_syllables_per_word = total_syllables / len(words)
    score = 206.835 - 1.015 * avg_words_per_sent - 84.6 * avg_syllables_per_word
    return round(score, 1)

def grade_content(text, target_keyword=""):
    """Score content 0-100 for SEO readiness."""
    if not text or len(text.strip()) < 50:
        return {
            "score": 0,
            "grade": "F",
            "issues": ["Content too short — needs at least 300 words for SEO"],
            "wins": [],
            "readability": 0,
            "word_count": 0
        }
    
    issues = []
    wins = []
    score = 0
    word_count = len(text.split())
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    
    # 1. Length (max 20 pts)
    if word_count >= 1500: score += 20; wins.append(f"Long-form content ({word_count} words) — great for ranking")
    elif word_count >= 800: score += 15; wins.append(f"Good length ({word_count} words)")
    elif word_count >= 500: score += 10; wins.append(f"Adequate length ({word_count} words)")
    elif word_count >= 300: score += 5
    else: issues.append(f"Too short ({word_count} words). Target 800+ for ranking")
    
    # 2. Headings (max 15 pts)
    h2_count = len(re.findall(r'^##\s', text, re.MULTILINE))
    h3_count = len(re.findall(r'^###\s', text, re.MULTILINE))
    total_heads = h2_count + h3_count
    if total_heads >= 5: score += 15; wins.append(f"Excellent heading structure ({total_heads} headings)")
    elif total_heads >= 3: score += 10
    elif total_heads >= 1: score += 5
    else: issues.append("No headings found. Use ## and ### to structure content")
    
    # 3. Keyword usage (max 20 pts)
    if target_keyword:
        kw_lower = target_keyword.lower()
        text_lower = text.lower()
        kw_count = text_lower.count(kw_lower)
        if kw_count >= 5 and kw_count <= 15:
            score += 20; wins.append(f"Good keyword density ({kw_count} mentions of '{target_keyword}')")
        elif kw_count > 15: score += 10; issues.append(f"Keyword stuffing risk ({kw_count} mentions). Aim for 5-10")
        elif kw_count >= 2: score += 10; wins.append(f"Keyword mentioned {kw_count}x")
        else: issues.append(f"Keyword '{target_keyword}' not found in content")
        
        # Keyword in first 100 words
        if kw_lower in text_lower[:100].lower():
            score += 5; wins.append("Keyword in first 100 words ✅")
        else:
            issues.append("Add keyword to first paragraph")
        
        # Keyword in headings
        headings_text = ' '.join(re.findall(r'^#{1,3}\s.*$', text, re.MULTILINE))
        if kw_lower in headings_text.lower():
            score += 5; wins.append("Keyword in heading ✅")
        else:
            issues.append("Add keyword to at least one heading")
    else:
        score += 5; issues.append("No target keyword specified — pass --keyword for better analysis")
    
    # 4. Readability (max 15 pts)
    readability = flesch_kincaid(text)
    if readability >= 60: score += 15; wins.append(f"Great readability ({readability}) — easy to read")
    elif readability >= 45: score += 10
    elif readability >= 30: score += 5; wins.append(f"OK readability ({readability})")
    else: issues.append(f"Hard to read ({readability}). Target 50+ for general audience")
    
    # 5. List/Structure (max 10 pts)
    list_items = len(re.findall(r'^\s*[-*]\s', text, re.MULTILINE))
    if list_items >= 5: score += 10; wins.append(f"Good use of lists ({list_items} items) — improves scannability")
    elif list_items >= 2: score += 5
    else: issues.append("Add bullet lists for scannability")
    
    # 6. Links (max 10 pts)
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
    internal_links = [l for l in links if 'jackalope86' in l[1] or 'gumroad' in l[1].lower()]
    external_links = [l for l in links if 'jackalope86' not in l[1]]
    
    if len(internal_links) >= 1: score += 5; wins.append(f"Has {len(internal_links)} product link(s)")
    else: issues.append("Add link to your Gumroad products")
    if len(external_links) >= 2: score += 5; wins.append(f"Has {len(external_links)} external reference(s)")
    else: issues.append("Add 2+ external references (authority building)")
    
    # 7. Meta readiness (max 5 pts)
    first_150 = text[:150].replace('\n', ' ')
    if len(first_150) >= 120: score += 5; wins.append("First 150 chars could work as meta description")
    else: issues.append("First 150 chars too short for meta description")
    
    # Final grade
    final_score = min(score, 100)
    if final_score >= 80: grade = "A"
    elif final_score >= 65: grade = "B"
    elif final_score >= 50: grade = "C"
    elif final_score >= 30: grade = "D"
    else: grade = "F"
    
    return {
        "score": final_score,
        "grade": grade,
        "word_count": word_count,
        "readability": readability,
        "heading_count": total_heads,
        "keyword_mentions": text.lower().count(target_keyword.lower()) if target_keyword else 0,
        "internal_links": len(internal_links),
        "external_links": len(external_links),
        "issues": issues[:8],
        "wins": wins[:8],
        "improvement_tips": suggest_improvements(final_score, issues, wins)
    }

def suggest_improvements(score, issues, wins):
    tips = []
    if score < 40: tips.append("🚀 Major rewrite needed. Focus on: length (800+ words), headings, keyword usage")
    elif score < 60: tips.append("📝 Needs improvement. Priority: fix the 'issues' section first")
    else: tips.append("✅ Content is in good shape. Minor tweaks recommended")
    return tips[:3]

def display_report(result, keyword=""):
    print(f"""
╔══════════════════════════════════════╗
║  📊 SEO Content Scorecard            ║
╠══════════════════════════════════════╣""")
    
    bar_len = 40
    filled = int(result['score'] / 100 * bar_len)
    bar = '█' * filled + '░' * (bar_len - filled)
    print(f"║  Score: {result['score']}/100 ({result['grade']}){' ' * (17 - len(str(result['score'])))}║")
    print(f"║  {bar}  ║")
    print(f"╠══════════════════════════════════════╣")
    print(f"║  📐 Content Stats:")
    print(f"║     Words: {result['word_count']:<5} | Readability: {result['readability']:<5}")
    print(f"║     Headings: {result['heading_count']:<3} | Keyword mentions: {result['keyword_mentions']:<3}")
    print(f"║     Internal links: {result['internal_links']:<3} | External: {result['external_links']:<3}")
    
    if result['wins']:
        print(f"╠══════════════════════════════════════╣")
        print(f"║  ✅ Strengths:")
        for w in result['wins'][:5]:
            print(f"║     ✓ {w[:56]}")
    
    if result['issues']:
        print(f"╠══════════════════════════════════════╣")
        print(f"║  ❌ Issues to Fix:")
        for i in result['issues'][:6]:
            print(f"║     ✗ {i[:56]}")
    
    if result['improvement_tips']:
        print(f"╠══════════════════════════════════════╣")
        for t in result['improvement_tips']:
            print(f"║  {t[:58]}")
    
    print("╚══════════════════════════════════════╝")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    text = ""
    keyword = ""
    
    for i, arg in enumerate(sys.argv):
        if arg == "--file" and i+1 < len(sys.argv):
            path = Path(sys.argv[i+1])
            if path.exists(): text = path.read_text()
            else: print(f"❌ File not found: {path}"); sys.exit(1)
        elif arg == "--text" and i+1 < len(sys.argv):
            text = sys.argv[i+1]
        elif arg == "--keyword" and i+1 < len(sys.argv):
            keyword = sys.argv[i+1]
        elif arg == "--improve" and i+1 < len(sys.argv):
            path = Path(sys.argv[i+1])
            if path.exists():
                text = path.read_text()
                keyword = os.path.basename(sys.argv[i+1]).replace('.md','').replace('.txt','')
                keyword = keyword.replace('-', ' ').replace('_', ' ')
    
    if not text:
        print("❌ No content provided. Use --file, --text, or --improve")
        sys.exit(1)
    
    result = grade_content(text, keyword)
    display_report(result, keyword)
