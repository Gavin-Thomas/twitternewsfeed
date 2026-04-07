"""Video-worthiness scoring and topic categorization."""
import re

from src.config import (
    IMPACT_KEYWORDS, DEMO_KEYWORDS, MODEL_KEYWORDS,
    CATEGORIES, MAX_SCORE,
)


def score_article(
    title: str = "",
    summary: str = "",
    source_type: str = "rss",
    hn_points: int = 0,
) -> int:
    """Score an article 0-10 for video-worthiness.

    Components:
    - Impact keywords (max 5)
    - Demo-ability keywords (max 3)
    - Model keywords (max 2)
    - HN points bonus (max 2)
    - GitHub bonus (1 if source_type == 'github')
    """
    text = f"{title} {summary}".lower()

    impact = 0
    for keyword, weight in IMPACT_KEYWORDS.items():
        if keyword.lower() in text:
            impact += weight
    impact = min(impact, 5)

    demo = 0
    for keyword, weight in DEMO_KEYWORDS.items():
        if keyword.lower() in text:
            demo += weight
    demo = min(demo, 3)

    model = 0
    for keyword, weight in MODEL_KEYWORDS.items():
        if keyword.lower() in text:
            model += weight
    model = min(model, 2)

    hn_bonus = 0
    if hn_points >= 500:
        hn_bonus = 2
    elif hn_points >= 200:
        hn_bonus = 1

    gh_bonus = 1 if source_type == "github" else 0

    total = impact + demo + model + hn_bonus + gh_bonus
    return max(0, min(total, MAX_SCORE))


def categorize(title: str, summary: str) -> str:
    """Assign the best-matching category to an article.

    Returns the category with the most keyword hits, or "" if none match.
    """
    text = f"{title} {summary}".lower()
    best_cat = ""
    best_count = 0

    for cat, keywords in CATEGORIES.items():
        count = sum(1 for kw in keywords if kw.lower() in text)
        if count > best_count:
            best_count = count
            best_cat = cat

    return best_cat


def generate_video_hook(title: str, summary: str, score: int = 5) -> str:
    """Generate a short video hook suggestion for high-scoring stories.

    Returns empty string for stories scoring below 4.
    """
    if score < 4:
        return ""

    text = f"{title} {summary}".lower()

    if any(kw in text for kw in ["launch", "release", "announce"]):
        name = _extract_product_name(title)
        return f'"I tested {name} so you don\'t have to"'

    if any(kw in text for kw in ["tool", "sdk", "framework", "library"]):
        name = _extract_product_name(title)
        return f'"I built something with {name} in 10 minutes"'

    if any(kw in text for kw in ["open-source", "open source", "free"]):
        return '"This free AI tool changes everything"'

    if any(kw in text for kw in ["agent", "automation", "workflow"]):
        return '"I automated this with AI agents"'

    if any(kw in text for kw in ["gpt", "claude", "gemini", "llama"]):
        return '"The new model everyone is talking about"'

    if any(kw in text for kw in ["breakthrough", "state-of-the-art", "sota"]):
        return '"This AI breakthrough is insane"'

    return f'"{title[:50]}... here\'s what you need to know"'


def _extract_product_name(title: str) -> str:
    """Extract a likely product/company name from the title."""
    stopwords = {"the", "a", "an", "and", "or", "for", "in", "on", "at", "to", "is", "new", "with", "its"}
    words = title.split()
    name_parts = []
    for w in words:
        if w[0:1].isupper() and w.lower() not in stopwords:
            name_parts.append(w)
            if len(name_parts) >= 3:
                break
    return " ".join(name_parts) if name_parts else (words[0] if words else "this")
