"""Keyword-based scoring engine and category assignment for articles."""

from dataclasses import replace

from src.config import (
    CATEGORIES,
    DEMO_KEYWORDS,
    IMPACT_KEYWORDS,
    MAX_SCORE,
    MODEL_KEYWORDS,
)
from src.store import Article


def keyword_score(text: str, keywords: dict[str, int]) -> int:
    """Return the sum of weights for each keyword found in *text*.

    Each keyword is counted at most once regardless of how many times it
    appears.  Matching is case-insensitive.
    """
    if not text or not keywords:
        return 0
    text_lower = text.lower()
    total = 0
    for kw, weight in keywords.items():
        if kw.lower() in text_lower:
            total += weight
    return total


def assign_category(text: str, categories: dict[str, list[str]] | None = None) -> str:
    """Return the best-matching category name for *text*, or ``"GENERAL"``."""
    if categories is None:
        categories = CATEGORIES
    if not text:
        return "GENERAL"

    text_lower = text.lower()
    best_cat = "GENERAL"
    best_hits = 0

    for cat_name, cat_keywords in categories.items():
        hits = sum(1 for kw in cat_keywords if kw.lower() in text_lower)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat_name

    return best_cat


def score_article(article: Article) -> Article:
    """Score and categorize an article, returning a **new** Article instance.

    The combined text (title + summary) is matched against the three
    keyword dictionaries (impact, demo, model).  The raw total is clamped
    to ``MAX_SCORE``.  A category is assigned from ``CATEGORIES``.
    """
    combined = f"{article.title} {article.summary}"

    raw = (
        keyword_score(combined, IMPACT_KEYWORDS)
        + keyword_score(combined, DEMO_KEYWORDS)
        + keyword_score(combined, MODEL_KEYWORDS)
    )
    clamped = min(raw, MAX_SCORE)

    category = assign_category(combined)

    return replace(article, score=clamped, category=category)
