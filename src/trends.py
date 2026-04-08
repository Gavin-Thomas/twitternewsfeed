"""Google Trends validation — check if topics have real search demand."""
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Known product/tool names to search for in article text
KNOWN_TERMS = [
    "Claude Code", "Claude", "Anthropic", "GPT-5", "GPT-4o", "ChatGPT",
    "Gemini", "Gemma", "DeepSeek", "Cursor AI", "Windsurf",
    "Vapi", "Voiceflow", "n8n", "LangChain", "MCP",
    "Codex", "NotebookLM", "Ollama", "LM Studio",
    "CrewAI", "AutoGen", "AI agent", "AI automation",
    "voice agent", "AI agency",
]


def extract_search_terms(title: str, summary: str) -> list[str]:
    """Extract 1-2 Google-searchable terms from an article.

    Prefers known product names. Falls back to key noun phrases.
    """
    text = f"{title} {summary}"
    text_lower = text.lower()

    # First: check for known products (most reliable search terms)
    found = []
    for term in KNOWN_TERMS:
        if term.lower() in text_lower:
            found.append(term)
            if len(found) >= 2:
                break

    if found:
        return found

    # Fallback: extract capitalized noun phrases from title
    skip = {"the", "a", "an", "and", "or", "for", "in", "on", "at", "to",
            "is", "new", "with", "its", "my", "i", "we", "you", "how",
            "why", "what", "this", "that", "just", "got", "from", "but"}
    words = title.split()
    terms = []
    for w in words:
        clean = w.strip(".,!?:;—-\"'()")
        if clean and len(clean) > 2 and clean.lower() not in skip:
            terms.append(clean)

    # Take the 2 most distinctive words, join as a phrase
    if len(terms) >= 2:
        return [" ".join(terms[:3])]
    elif terms:
        return [terms[0]]

    return []


def check_trend(search_terms: list[str], geo: str = "") -> Optional[dict]:
    """Check Google Trends for the given search terms.

    Args:
        search_terms: 1-5 terms to check
        geo: Country code ("US", "CA", or "" for worldwide)

    Returns:
        Dict with trend data or None if the check fails.
        {
            "term": "Claude Code",
            "direction": "UP" | "FLAT" | "DOWN" | "NO_DATA",
            "current_interest": 75,  # 0-100 scale
            "change_pct": 25,  # percent change vs prior period
            "geo": "US",
        }
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(5, 10))

        # Only check the first term to minimize rate limiting
        term = search_terms[0] if search_terms else None
        if not term:
            return None

        pytrends.build_payload([term], cat=0, timeframe="now 7-d", geo=geo)
        data = pytrends.interest_over_time()

        if data.empty or term not in data.columns:
            return {
                "term": term,
                "direction": "NO_DATA",
                "current_interest": 0,
                "change_pct": 0,
                "geo": geo or "Worldwide",
            }

        values = data[term].tolist()

        # Split into first half and second half to determine direction
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / max(len(values[:mid]), 1)
        second_half_avg = sum(values[mid:]) / max(len(values[mid:]), 1)
        current = values[-1] if values else 0

        if first_half_avg == 0:
            change_pct = 100 if second_half_avg > 0 else 0
        else:
            change_pct = int(((second_half_avg - first_half_avg) / first_half_avg) * 100)

        if change_pct >= 20:
            direction = "UP"
        elif change_pct <= -20:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "term": term,
            "direction": direction,
            "current_interest": int(current),
            "change_pct": change_pct,
            "geo": geo or "Worldwide",
        }

    except Exception as e:
        logger.warning("Google Trends check failed for %s: %s", search_terms, e)
        return None


def check_trends_batch(articles_with_terms: list[tuple], delay: float = 1.5) -> dict[str, dict]:
    """Check trends for multiple articles, respecting rate limits.

    Args:
        articles_with_terms: List of (article_url, search_terms) tuples
        delay: Seconds between queries to avoid rate limiting

    Returns:
        Dict mapping article URL to trend result.
    """
    results = {}

    for i, (url, terms) in enumerate(articles_with_terms):
        if not terms:
            continue

        # Check US trends (largest English-speaking audience)
        result = check_trend(terms, geo="US")
        if result:
            results[url] = result

        # Rate limit: wait between queries
        if i < len(articles_with_terms) - 1:
            time.sleep(delay)

    logger.info("Google Trends: checked %d/%d articles", len(results), len(articles_with_terms))
    return results


def format_trend_line(trend: Optional[dict]) -> str:
    """Format a trend result into a human-readable line."""
    if trend is None:
        return "SEARCH DEMAND: Could not check (Google Trends unavailable)"

    arrows = {"UP": "^", "DOWN": "v", "FLAT": "=", "NO_DATA": "?"}
    arrow = arrows.get(trend["direction"], "?")

    if trend["direction"] == "NO_DATA":
        return f"SEARCH DEMAND: NO DATA for \"{trend['term']}\" — topic may be too niche"
    elif trend["direction"] == "DOWN":
        return (
            f"SEARCH DEMAND: DECLINING {arrow} \"{trend['term']}\" "
            f"({trend['change_pct']:+d}% this week, interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— consider waiting for a new angle"
        )
    elif trend["direction"] == "UP":
        return (
            f"SEARCH DEMAND: TRENDING UP {arrow} \"{trend['term']}\" "
            f"({trend['change_pct']:+d}% this week, interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— strike now, search demand is growing"
        )
    else:
        return (
            f"SEARCH DEMAND: STABLE {arrow} \"{trend['term']}\" "
            f"(interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— steady audience, not time-sensitive"
        )
