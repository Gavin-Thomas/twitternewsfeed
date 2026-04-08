"""Format scored articles into a readable news briefing."""
from datetime import datetime, timezone
from typing import Optional

from src.store import Article
from src.config import (
    MAX_TOP_STORIES, MAX_NOTABLE_STORIES, MIN_SCORE_TOP, MIN_SCORE_NOTABLE,
    LAUNCH_KEYWORDS,
)


def _truncate(text: str, max_len: int = 120) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "..."


def _freshness_label(published: Optional[datetime]) -> str:
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
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in LAUNCH_KEYWORDS)


def _clean_title(title: str) -> str:
    """Clean up titles — remove repo-style formatting for readability."""
    # "anthropics/claude-code: v2.1.94" → "Claude Code v2.1.94"
    if ": " in title and "/" in title.split(": ")[0]:
        return title.split(": ", 1)[1]
    # "@AnthropicAI: R to @AnthropicAI: ..." → clean up retweet noise
    if title.startswith("@") and "R to @" in title:
        parts = title.split("R to @", 1)
        if len(parts) > 1:
            after = parts[1]
            # Skip past the username
            if ": " in after:
                return after.split(": ", 1)[1].strip()
    # "@handle: text" → keep the text, note the handle
    if title.startswith("@") and ": " in title:
        return title
    return title


def _format_article(article: Article, num: int) -> str:
    """Format one article as a readable numbered item."""
    title = _clean_title(article.title)
    freshness = _freshness_label(article.published)
    is_new = _is_launch(article.title, article.summary)

    # Line 1: number + title + NEW badge
    new_badge = " [NEW]" if is_new else ""
    line1 = f"{num}. {title}{new_badge}"

    # Line 2: summary (cleaned up)
    summary = article.summary or ""
    # Strip Reddit prefix like "r/ClaudeAI (574 pts): "
    if summary.startswith("r/") and ": " in summary[:40]:
        summary = summary.split(": ", 1)[1] if ": " in summary else summary
    # Strip "HN: 500 points"
    if summary.startswith("HN: "):
        summary = ""
    # Strip "Release v1.2.3 — "
    if summary.startswith("Release "):
        summary = summary.split(" — ", 1)[1] if " — " in summary else summary
    summary = _truncate(summary.strip(), 120)

    line2 = f"   {summary}" if summary else ""

    # Line 3: metadata
    meta_parts = []
    if article.score >= 8:
        meta_parts.append(f"Score: {article.score}/10")
    if freshness:
        meta_parts.append(freshness)
    meta_parts.append(article.source)
    if article.category:
        meta_parts.append(article.category)
    line3 = f"   {' · '.join(meta_parts)}"

    # Line 4: link
    line4 = f"   {article.url}"

    parts = [line1]
    if line2:
        parts.append(line2)
    parts.append(line3)
    parts.append(line4)
    return "\n".join(parts)


def format_digest(
    articles: list[Article],
    now: Optional[datetime] = None,
    min_top: int = MIN_SCORE_TOP,
    min_notable: int = MIN_SCORE_NOTABLE,
) -> str:
    """Format articles into a readable news briefing for ntfy + email."""
    if now is None:
        now = datetime.now()

    date_str = now.strftime("%a %b %-d, %-I:%M %p")

    top_stories = [a for a in articles if a.score >= min_top][:MAX_TOP_STORIES]
    notable_stories = [a for a in articles if min_notable <= a.score < min_top][:MAX_NOTABLE_STORIES]

    if not top_stories and not notable_stories:
        return f"AI Digest — {date_str}\n\nNo notable stories this cycle. Check back later."

    parts = []
    parts.append(f"AI Digest — {date_str}")
    parts.append("")

    # Video pick — the #1 story you should film today
    if top_stories and top_stories[0].score >= 7:
        best = top_stories[0]
        best_title = _clean_title(best.title)
        parts.append(f"Today's video pick: {best_title} ({best.score}/10)")
        parts.append("")

    if top_stories:
        parts.append(f"TOP STORIES ({len(top_stories)})")
        parts.append("")
        for i, a in enumerate(top_stories, 1):
            parts.append(_format_article(a, i))
            parts.append("")

    if notable_stories:
        start_num = len(top_stories) + 1
        parts.append(f"ALSO NOTABLE ({len(notable_stories)})")
        parts.append("")
        for i, a in enumerate(notable_stories, start_num):
            parts.append(_format_article(a, i))
            parts.append("")

    # Footer
    all_articles = top_stories + notable_stories
    sources = sorted(set(a.source for a in all_articles if a.source))
    parts.append(f"Sources: {', '.join(sources)}")

    return "\n".join(parts)
