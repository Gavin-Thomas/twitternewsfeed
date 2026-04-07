"""Launch-focused scoring and topic categorization for video planning."""
import re
from datetime import datetime, timezone
from typing import Optional

from src.config import (
    LAUNCH_KEYWORDS, LAUNCH_MAX, WEAK_LAUNCH_KEYWORDS, WEAK_LAUNCH_MAX,
    TOOL_KEYWORDS, TOOL_MAX, DEMO_KEYWORDS, DEMO_MAX,
    ANTI_SIGNAL_KEYWORDS, OPINION_KEYWORDS, MEME_KEYWORDS,
    FRESHNESS_BRACKETS, SOURCE_AUTHORITY, SOURCE_AUTHORITY_DEFAULT,
    CATEGORIES, MAX_SCORE,
)


def _count_keyword_hits(text: str, keywords: dict[str, int], cap: int) -> int:
    """Sum keyword weights found in text, capped at cap."""
    total = 0
    for keyword, weight in keywords.items():
        if keyword.lower() in text:
            total += weight
    return min(total, cap)


def _count_penalties(text: str, keywords: dict[str, int]) -> int:
    """Sum penalty weights for anti-signal keywords found in text.

    Uses word-boundary matching to avoid false positives
    (e.g. "debugging" should not trigger "bug").
    """
    total = 0
    for keyword, weight in keywords.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text):
            total += weight
    return total


def _freshness_multiplier(published: Optional[datetime]) -> float:
    """Calculate freshness multiplier based on article age."""
    if published is None:
        return 1.0

    now = datetime.now(timezone.utc)
    # Make published timezone-aware if it isn't
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    age_hours = (now - published).total_seconds() / 3600
    if age_hours < 0:
        age_hours = 0

    for max_hours, multiplier in FRESHNESS_BRACKETS:
        if max_hours is None or age_hours <= max_hours:
            return multiplier

    return 0.4


def _authority_multiplier(source_name: str) -> float:
    """Calculate source authority multiplier."""
    return SOURCE_AUTHORITY.get(source_name, SOURCE_AUTHORITY_DEFAULT)


def score_article(
    title: str = "",
    summary: str = "",
    source_name: str = "",
    source_type: str = "rss",
    hn_points: int = 0,
    reddit_score: int = 0,
    published: Optional[datetime] = None,
) -> int:
    """Score an article 0-10 for video-worthiness.

    Prioritizes NEW launches and releases over keyword mentions.
    Penalizes bug reports, complaints, and opinion pieces.

    Components:
    - Launch detection (max 4)
    - Tool relevance (max 3)
    - Demo-ability (max 2)
    - Anti-signal penalties
    - Freshness multiplier
    - Source authority multiplier
    """
    text = f"{title} {summary}".lower()

    # 1. Launch detection: is this something NEW?
    launch = _count_keyword_hits(text, LAUNCH_KEYWORDS, LAUNCH_MAX)
    weak_launch = _count_keyword_hits(text, WEAK_LAUNCH_KEYWORDS, WEAK_LAUNCH_MAX)
    launch_score = min(launch + weak_launch, LAUNCH_MAX)

    # 2. Tool relevance: is this about tools we care about?
    tool_score = _count_keyword_hits(text, TOOL_KEYWORDS, TOOL_MAX)

    # 3. Demo-ability: can we screen-record this?
    demo_score = _count_keyword_hits(text, DEMO_KEYWORDS, DEMO_MAX)

    # 4. GitHub source bonus
    gh_bonus = 1 if source_type == "github" else 0

    # 5. Community validation bonus (high engagement = worth covering)
    community_bonus = 0
    if hn_points >= 500:
        community_bonus = 2
    elif hn_points >= 200:
        community_bonus = 1
    if reddit_score >= 500:
        community_bonus = max(community_bonus, 2)
    elif reddit_score >= 200:
        community_bonus = max(community_bonus, 1)

    # Base score before penalties
    raw = launch_score + tool_score + demo_score + gh_bonus + community_bonus

    # 6. Anti-signal penalties
    anti_penalty = _count_penalties(text, ANTI_SIGNAL_KEYWORDS)
    opinion_penalty = _count_penalties(text, OPINION_KEYWORDS)
    meme_penalty = _count_penalties(text, MEME_KEYWORDS)
    raw = max(0, raw - anti_penalty - opinion_penalty - meme_penalty)

    # 7. Apply freshness multiplier
    fresh_mult = _freshness_multiplier(published)
    adjusted = raw * fresh_mult

    # 8. Apply source authority multiplier
    auth_mult = _authority_multiplier(source_name)
    adjusted = adjusted * auth_mult

    return max(0, min(int(round(adjusted)), MAX_SCORE))


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
    """Generate a short video hook for AI automation YouTube content.

    Returns empty string for stories scoring below 4.
    """
    if score < 4:
        return ""

    text = f"{title} {summary}".lower()

    if any(kw in text for kw in ["vapi", "voiceflow", "bland ai", "voice agent", "voice ai"]):
        name = _extract_product_name(title)
        return f'"I built an AI voice agent with {name} — full walkthrough"'

    if any(kw in text for kw in ["n8n", "make.com", "zapier", "automation", "workflow"]):
        return '"This AI automation makes money while you sleep"'

    if any(kw in text for kw in ["mcp", "claude code"]):
        name = _extract_product_name(title)
        return f'"I connected {name} to everything — here\'s how"'

    if any(kw in text for kw in ["chatbot", "agent", "assistant"]):
        return '"Build this AI agent in 15 minutes (no code)"'

    if any(kw in text for kw in ["launch", "release", "announce", "introducing", "just shipped"]):
        name = _extract_product_name(title)
        return f'"FIRST LOOK: {name} just dropped — here\'s what it does"'

    if any(kw in text for kw in ["open-source", "open source", "free"]):
        return '"This free AI tool replaces a $500/mo subscription"'

    if any(kw in text for kw in ["agency", "client", "saas", "revenue"]):
        return '"How to sell this AI automation to clients"'

    if any(kw in text for kw in ["cursor", "bolt", "lovable", "v0", "replit"]):
        name = _extract_product_name(title)
        return f'"I built a full app with {name} in one sitting"'

    if any(kw in text for kw in ["gpt", "claude", "gemini"]):
        return '"The new model changes everything for automations"'

    name = _extract_product_name(title)
    return f'"How to use {name} for AI automation"'


def _extract_product_name(title: str) -> str:
    """Extract a likely product/tool name from the title.

    Checks known product names first, then falls back to capitalized words.
    """
    text_lower = title.lower()

    # Check for known product names first (most reliable)
    known_products = [
        "Claude Code", "Claude", "Anthropic", "GPT-5", "GPT-4o", "GPT",
        "Gemini", "Gemma", "DeepSeek", "Cursor", "Windsurf",
        "Vapi", "Voiceflow", "Bland AI", "n8n", "LangChain",
        "CrewAI", "AutoGen", "MCP", "Codex", "NotebookLM",
        "Ollama", "LM Studio", "Hugging Face",
    ]
    for product in known_products:
        if product.lower() in text_lower:
            return product

    # Fall back to first 2 capitalized words (skip common sentence starters)
    skip = {"the", "a", "an", "and", "or", "for", "in", "on", "at", "to",
            "is", "new", "with", "its", "my", "i", "we", "you", "how",
            "why", "what", "this", "that", "just", "got", "from", "but",
            "so", "if", "it", "our", "some", "someone", "introducing"}
    words = title.split()
    name_parts = []
    for w in words:
        clean = w.strip(".,!?:;—-\"'()")
        if clean and clean[0:1].isupper() and clean.lower() not in skip:
            name_parts.append(clean)
            if len(name_parts) >= 2:
                break
    return " ".join(name_parts) if name_parts else "this new AI tool"
