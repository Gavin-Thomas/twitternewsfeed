"""Format scored articles into an iMessage digest."""
from datetime import datetime, timezone
from typing import Optional

from src.store import Article
from src.config import (
    MAX_TOP_STORIES, MAX_NOTABLE_STORIES, MIN_SCORE_TOP, MIN_SCORE_NOTABLE,
    LAUNCH_KEYWORDS,
)


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _freshness_label(published: Optional[datetime]) -> str:
    """Return a human-readable freshness label like '2h ago' or 'yesterday'."""
    if published is None:
        return ""

    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    delta = now - published
    hours = delta.total_seconds() / 3600

    if hours < 0:
        return ""
    elif hours < 1:
        return f"{int(delta.total_seconds() / 60)}m ago"
    elif hours < 24:
        return f"{int(hours)}h ago"
    elif hours < 48:
        return "yesterday"
    elif hours < 168:
        return f"{int(hours / 24)}d ago"
    else:
        return ""


def _is_launch(title: str, summary: str) -> bool:
    """Check if article has strong launch signals."""
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in LAUNCH_KEYWORDS)


def _format_article_line(article: Article) -> str:
    """Format a single article into digest lines."""
    tags = []

    # NEW tag for launches
    if _is_launch(article.title, article.summary):
        tags.append("NEW")

    # Category tag
    if article.category:
        tags.append(article.category)

    # Freshness
    freshness = _freshness_label(article.published)

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    fresh_str = f" ({freshness})" if freshness else ""

    lines = [f"[{article.score}/10]{tag_str} {article.title}{fresh_str}"]
    if article.summary:
        lines.append(f"  {_truncate(article.summary)}")
    return "\n".join(lines)


def format_digest(
    articles: list[Article],
    now: Optional[datetime] = None,
    min_top: int = MIN_SCORE_TOP,
    min_notable: int = MIN_SCORE_NOTABLE,
) -> str:
    """Format a list of articles into the full digest message.

    Articles should already be sorted by score descending.
    """
    if now is None:
        now = datetime.now()

    header = f"AI DIGEST — {now.strftime('%a %b %-d, %-I:%M %p')}"

    top_stories = [a for a in articles if a.score >= min_top][:MAX_TOP_STORIES]
    notable_stories = [a for a in articles if min_notable <= a.score < min_top][:MAX_NOTABLE_STORIES]

    if not top_stories and not notable_stories:
        return f"{header}\n\nNo notable stories this cycle."

    parts = [header, ""]

    if top_stories:
        parts.append("--- TOP STORIES ---")
        parts.append("")
        for a in top_stories:
            parts.append(_format_article_line(a))
            parts.append("")

    if notable_stories:
        parts.append("--- ALSO NOTABLE ---")
        parts.append("")
        for a in notable_stories:
            parts.append(_format_article_line(a))
            parts.append("")

    all_articles = top_stories + notable_stories
    sources = sorted(set(a.source for a in all_articles if a.source))
    if sources:
        parts.append("---")
        parts.append(f"Sources: {', '.join(sources)}")

    return "\n".join(parts)
