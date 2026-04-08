"""Google Trends validation via BigQuery (primary) and pytrends (fallback).

Uses the free BigQuery public dataset google_trends.top_terms and
google_trends.top_rising_terms for reliable, rate-limit-free trend data.
Falls back to pytrends for specific term interest checks.
"""
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

# Cache for BigQuery results (populated once per pipeline run)
_bq_cache: dict = {}


def extract_search_terms(title: str, summary: str) -> list[str]:
    """Extract 1-2 Google-searchable terms from an article.

    Prefers known product names. Falls back to key noun phrases.
    """
    text = f"{title} {summary}"
    text_lower = text.lower()

    found = []
    for term in KNOWN_TERMS:
        if term.lower() in text_lower:
            found.append(term)
            if len(found) >= 2:
                break

    if found:
        return found

    skip = {"the", "a", "an", "and", "or", "for", "in", "on", "at", "to",
            "is", "new", "with", "its", "my", "i", "we", "you", "how",
            "why", "what", "this", "that", "just", "got", "from", "but"}
    words = title.split()
    terms = []
    for w in words:
        clean = w.strip(".,!?:;—-\"'()")
        if clean and len(clean) > 2 and clean.lower() not in skip:
            terms.append(clean)

    if len(terms) >= 2:
        return [" ".join(terms[:3])]
    elif terms:
        return [terms[0]]

    return []


# --- BigQuery: Google Trends Public Dataset ---

def _fetch_bigquery_trends() -> dict:
    """Fetch today's top terms and rising terms from BigQuery.

    Returns a dict with:
        "top": {term_lower: {"term": str, "rank": int, "score": int, "region": str}}
        "rising": {term_lower: {"term": str, "rank": int, "percent_gain": int, "region": str}}

    Results are cached for the lifetime of the process.
    """
    global _bq_cache
    if _bq_cache:
        return _bq_cache

    try:
        from google.cloud import bigquery

        client = bigquery.Client()

        # Query top terms (US, yesterday)
        top_query = """
        SELECT term, rank, score, region
        FROM `bigquery-public-data.google_trends.top_terms`
        WHERE refresh_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
          AND (region = 'US' OR region = 'CA')
        ORDER BY rank
        LIMIT 100
        """

        # Query rising terms (US, yesterday)
        rising_query = """
        SELECT term, rank, percent_gain, region
        FROM `bigquery-public-data.google_trends.top_rising_terms`
        WHERE refresh_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
          AND (region = 'US' OR region = 'CA')
        ORDER BY rank
        LIMIT 100
        """

        top_results = {}
        for row in client.query(top_query).result():
            key = row.term.lower()
            if key not in top_results:
                top_results[key] = {
                    "term": row.term,
                    "rank": row.rank,
                    "score": row.score,
                    "region": row.region,
                }

        rising_results = {}
        for row in client.query(rising_query).result():
            key = row.term.lower()
            if key not in rising_results:
                rising_results[key] = {
                    "term": row.term,
                    "rank": row.rank,
                    "percent_gain": row.percent_gain,
                    "region": row.region,
                }

        _bq_cache = {"top": top_results, "rising": rising_results}
        logger.info("BigQuery: loaded %d top terms, %d rising terms",
                     len(top_results), len(rising_results))
        return _bq_cache

    except Exception as e:
        logger.warning("BigQuery trends failed: %s", e)
        _bq_cache = {"top": {}, "rising": {}}
        return _bq_cache


def _match_in_bigquery(search_terms: list[str]) -> Optional[dict]:
    """Check if any of the search terms appear in BigQuery trends data.

    Returns a trend result dict if found, None otherwise.
    """
    bq = _fetch_bigquery_trends()
    if not bq["top"] and not bq["rising"]:
        return None

    for term in search_terms:
        term_lower = term.lower()

        # Check rising terms first (strongest signal)
        for key, data in bq["rising"].items():
            if term_lower in key or key in term_lower:
                return {
                    "term": term,
                    "direction": "RISING",
                    "current_interest": 0,
                    "change_pct": data.get("percent_gain", 0),
                    "geo": data.get("region", "US"),
                    "rank": data.get("rank", 0),
                    "source": "BigQuery Rising",
                }

        # Check top terms
        for key, data in bq["top"].items():
            if term_lower in key or key in term_lower:
                return {
                    "term": term,
                    "direction": "TOP",
                    "current_interest": data.get("score", 0),
                    "change_pct": 0,
                    "geo": data.get("region", "US"),
                    "rank": data.get("rank", 0),
                    "source": "BigQuery Top",
                }

    return None


# --- pytrends fallback for specific term interest ---

def _check_pytrends(search_terms: list[str], geo: str = "US") -> Optional[dict]:
    """Check Google Trends via pytrends (fallback, rate-limited)."""
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(5, 10))
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
                "geo": geo,
                "source": "pytrends",
            }

        values = data[term].tolist()
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
            "geo": geo,
            "source": "pytrends",
        }

    except Exception as e:
        logger.warning("pytrends check failed for %s: %s", search_terms, e)
        return None


# --- Public API ---

def check_trend(search_terms: list[str], geo: str = "US") -> Optional[dict]:
    """Check Google Trends for the given search terms.

    Strategy:
    1. Check BigQuery public dataset first (free, no rate limit)
    2. Fall back to pytrends for specific interest data (rate-limited)

    Returns a dict with trend data or None if all checks fail.
    """
    if not search_terms:
        return None

    # Try BigQuery first — instant, no rate limits
    bq_result = _match_in_bigquery(search_terms)
    if bq_result:
        return bq_result

    # Fall back to pytrends for specific term interest
    return _check_pytrends(search_terms, geo=geo)


def format_trend_line(trend: Optional[dict]) -> str:
    """Format a trend result into a human-readable line."""
    if trend is None:
        return "SEARCH DEMAND: Could not check (Google Trends unavailable)"

    source = trend.get("source", "")

    if trend["direction"] == "RISING":
        gain = trend.get("change_pct", 0)
        rank = trend.get("rank", 0)
        gain_str = f"+{gain}%" if gain else ""
        rank_str = f"#{rank} rising" if rank else ""
        parts = [p for p in [gain_str, rank_str] if p]
        detail = f" ({', '.join(parts)})" if parts else ""
        return (
            f"SEARCH DEMAND: RISING FAST \"{trend['term']}\"{detail} in {trend['geo']} "
            f"— MAKE THIS VIDEO NOW, search demand is spiking"
        )
    elif trend["direction"] == "TOP":
        rank = trend.get("rank", 0)
        score = trend.get("current_interest", 0)
        return (
            f"SEARCH DEMAND: TOP SEARCH \"{trend['term']}\" "
            f"(#{rank} in {trend['geo']}, score: {score}/100) "
            f"— massive audience, high competition"
        )
    elif trend["direction"] == "NO_DATA":
        return f"SEARCH DEMAND: NO DATA for \"{trend['term']}\" — topic may be too niche for broad search"
    elif trend["direction"] == "DOWN":
        return (
            f"SEARCH DEMAND: DECLINING \"{trend['term']}\" "
            f"({trend['change_pct']:+d}% this week, interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— consider waiting for a new angle"
        )
    elif trend["direction"] == "UP":
        return (
            f"SEARCH DEMAND: TRENDING UP \"{trend['term']}\" "
            f"({trend['change_pct']:+d}% this week, interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— strike now, search demand is growing"
        )
    else:  # FLAT
        return (
            f"SEARCH DEMAND: STABLE \"{trend['term']}\" "
            f"(interest: {trend['current_interest']}/100 in {trend['geo']}) "
            f"— steady audience, not time-sensitive"
        )
