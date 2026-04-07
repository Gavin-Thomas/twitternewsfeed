"""Format scored articles into an iMessage digest."""
from datetime import datetime
from typing import Optional

from src.store import Article
from src.config import MAX_TOP_STORIES, MAX_NOTABLE_STORIES, MIN_SCORE_TOP, MIN_SCORE_NOTABLE


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_article_line(article: Article, include_hook: bool = True) -> str:
    """Format a single article into digest lines."""
    fire = " 🔥" if article.score >= 8 else ""
    cat = f" [{article.category}]" if article.category else ""
    lines = [f"[{article.score}/10]{fire}{cat} {article.title}"]
    if article.summary:
        lines.append(f"→ {_truncate(article.summary)}")
    if include_hook and article.video_hook:
        lines.append(f"📹 {article.video_hook}")
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

    header = f"🤖 AI DIGEST — {now.strftime('%a %b %-d, %-I:%M %p')}"

    top_stories = [a for a in articles if a.score >= min_top][:MAX_TOP_STORIES]
    notable_stories = [a for a in articles if min_notable <= a.score < min_top][:MAX_NOTABLE_STORIES]

    if not top_stories and not notable_stories:
        return f"{header}\n\nNo notable stories this cycle."

    parts = [header, ""]

    if top_stories:
        parts.append("━━━ TOP STORIES ━━━")
        parts.append("")
        for a in top_stories:
            parts.append(_format_article_line(a, include_hook=True))
            parts.append("")

    if notable_stories:
        parts.append("━━━ ALSO NOTABLE ━━━")
        parts.append("")
        for a in notable_stories:
            parts.append(_format_article_line(a, include_hook=False))
            parts.append("")

    all_articles = top_stories + notable_stories
    sources = sorted(set(a.source for a in all_articles if a.source))
    if sources:
        parts.append("━━━")
        parts.append(f"Sources: {', '.join(sources)}")

    return "\n".join(parts)
