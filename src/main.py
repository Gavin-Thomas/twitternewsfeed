"""Main orchestrator: fetch -> dedup -> score -> format -> send -> export."""
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import (
    DB_PATH, RECIPIENTS, NTFY_TOPIC, FALLBACK_EMAIL, LOG_DIR, RETENTION_DAYS,
    MIN_SCORE_NOTABLE, DELIVERY_MODE,
)
from src.sources import fetch_all_sources
from src.scorer import score_article, categorize, generate_video_hook
from src.store import Article, ArticleStore
from src.formatter import format_digest
from src.notify import send_ntfy_long, send_email


def setup_logging() -> None:
    """Configure logging to both file and stderr."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"digest_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def process_articles(raw_articles: list[Article], store: ArticleStore) -> list[Article]:
    """Score, categorize, and deduplicate articles."""
    processed = []
    for article in raw_articles:
        source_type = "github" if article.source in ("GitHub", "GitHub Release") else "rss"

        hn_points = 0
        if article.source == "HackerNews" and article.summary.startswith("HN:"):
            try:
                hn_points = int(article.summary.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass

        reddit_score = 0
        if article.source == "Reddit":
            try:
                # Extract score from "r/sub (123 pts)" format
                match = re.search(r"\((\d+) pts\)", article.summary)
                if match:
                    reddit_score = int(match.group(1))
            except (ValueError, AttributeError):
                pass

        article.score = score_article(
            title=article.title,
            summary=article.summary,
            source_name=article.source,
            source_type=source_type,
            hn_points=hn_points,
            reddit_score=reddit_score,
            published=article.published,
        )

        article.category = categorize(article.title, article.summary)

        if store.add(article):
            processed.append(article)

    return processed


def _send_imessage(message: str, recipients: list[str], logger: logging.Logger) -> bool:
    """Send via iMessage (local Mac only)."""
    from src.imessage import send_imessage
    all_ok = True
    for recipient in recipients:
        logger.info("iMessage -> %s", recipient)
        if not send_imessage(message, recipient):
            logger.error("iMessage failed for %s", recipient)
            all_ok = False
    return all_ok


def _send_ntfy(message: str, topic: str, logger: logging.Logger) -> bool:
    """Send via ntfy.sh (works from anywhere)."""
    now = datetime.now().strftime("%a %b %-d, %-I:%M %p")
    return send_ntfy_long(message, topic, title=f"AI Digest — {now}")


def run_digest(
    db_path: Optional[Path] = None,
    recipients: Optional[list[str]] = None,
    ntfy_topic: Optional[str] = None,
    delivery: Optional[str] = None,
) -> bool:
    """Run the full digest pipeline."""
    logger = logging.getLogger(__name__)

    if db_path is None:
        db_path = DB_PATH
    if recipients is None:
        recipients = RECIPIENTS
    if ntfy_topic is None:
        ntfy_topic = NTFY_TOPIC
    if delivery is None:
        delivery = DELIVERY_MODE

    store = ArticleStore(db_path)

    try:
        # Fetch
        logger.info("Fetching articles from all sources...")
        raw_articles = fetch_all_sources()
        logger.info("Fetched %d raw articles", len(raw_articles))

        # Process
        new_articles = process_articles(raw_articles, store)
        logger.info("After dedup: %d new articles", len(new_articles))

        # Get unsent
        unsent = store.get_unsent(min_score=MIN_SCORE_NOTABLE)
        logger.info("Unsent above threshold: %d", len(unsent))

        # Format digest (clean news only — no video ideas)
        now = datetime.now()
        full_message = format_digest(unsent, now=now)

        logger.info("Full message: %d chars", len(full_message))

        # Deliver — at least one method must succeed
        any_delivered = False

        # Email (works from anywhere — GitHub Actions, local Mac, etc.)
        if delivery in ("email", "both"):
            email_to = FALLBACK_EMAIL
            if email_to:
                logger.info("Sending via email to %s...", email_to)
                now_str = datetime.now().strftime("%a %b %-d")
                if send_email(full_message, email_to, subject=f"AI Digest — {now_str}"):
                    any_delivered = True
                else:
                    logger.warning("Email delivery failed")

        # ntfy (works from anywhere — GitHub Actions, local Mac, etc.)
        if delivery in ("ntfy", "both") and ntfy_topic:
            logger.info("Sending via ntfy...")
            if _send_ntfy(full_message, ntfy_topic, logger):
                any_delivered = True

        # iMessage (local Mac only)
        if delivery in ("imessage", "both") and recipients:
            if os.environ.get("GITHUB_ACTIONS"):
                logger.info("Skipping iMessage (running in GitHub Actions)")
            else:
                logger.info("Sending via iMessage...")
                if _send_imessage(full_message, recipients, logger):
                    any_delivered = True

        success = any_delivered

        if success:
            urls = [a.url for a in unsent]
            store.mark_sent(urls)
            logger.info("Delivered, %d articles marked as sent", len(urls))

            # Export scored articles for the video ideas trigger to consume
            export_path = db_path.parent / "latest_digest.json"
            _export_articles(unsent, export_path, logger)

            # Send video ideas email for high-scoring articles
            _send_video_ideas(unsent, logger)
        else:
            logger.error("Delivery failed — articles NOT marked as sent (will retry)")

        # Cleanup
        removed = store.cleanup(days=RETENTION_DAYS)
        if removed:
            logger.info("Cleaned up %d old articles", removed)

        return success

    except Exception as e:
        logger.exception("Digest pipeline failed: %s", e)
        return False

    finally:
        store.close()


def _export_articles(articles: list[Article], path: Path, logger: logging.Logger) -> None:
    """Export scored articles to JSON for the video ideas trigger."""
    data = [
        {
            "title": a.title,
            "summary": a.summary,
            "source": a.source,
            "score": a.score,
            "category": a.category,
            "url": a.url,
        }
        for a in articles
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    logger.info("Exported %d articles to %s", len(data), path)


def _send_video_ideas(articles: list[Article], logger: logging.Logger) -> None:
    """Generate and email video ideas for high-scoring articles."""
    top = [a for a in articles if a.score >= 4]
    if not top:
        logger.info("No articles scored 4+ for video ideas")
        return

    email_to = FALLBACK_EMAIL
    if not email_to:
        return

    now_str = datetime.now().strftime("%a %b %-d")
    lines = [f"VIDEO IDEAS — {now_str}", ""]
    lines.append(f"{len(top)} articles scored 4+ for video potential:")
    lines.append("")

    for i, a in enumerate(top, 1):
        hook = generate_video_hook(a.title, a.summary, a.score)
        cat = f" [{a.category}]" if a.category else ""
        lines.append(f"--- IDEA #{i} (Score: {a.score}/10){cat} ---")
        lines.append(f"Title: {a.title}")
        lines.append(f"Source: {a.source}")
        if hook:
            lines.append(f"Video Hook: {hook}")
        lines.append(f"Link: {a.url}")
        summary = (a.summary or "")[:200]
        if summary:
            lines.append(f"Summary: {summary}")
        lines.append("")

    message = "\n".join(lines)
    if send_email(message, email_to, subject=f"AI Video Ideas — {now_str}"):
        logger.info("Video ideas email sent (%d ideas)", len(top))
    else:
        logger.warning("Video ideas email failed")


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== AI Digest starting ===")

    success = run_digest()

    logger.info("=== AI Digest finished (success=%s) ===", success)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
