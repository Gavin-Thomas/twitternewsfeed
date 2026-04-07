"""Main orchestrator: fetch -> dedup -> score -> format -> send."""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import (
    DB_PATH, RECIPIENTS, NTFY_TOPIC, LOG_DIR, RETENTION_DAYS,
    MIN_SCORE_NOTABLE, DELIVERY_MODE, MAX_VIDEO_SCRIPTS,
)
from src.sources import fetch_all_sources
from src.scorer import score_article, categorize, generate_video_hook
from src.store import Article, ArticleStore
from src.formatter import format_digest
from src.scripts import generate_scripts_for_digest
from src.notify import send_ntfy_long


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
        source_type = "github" if article.source == "GitHub" else "rss"
        hn_points = 0
        if article.source == "HackerNews" and article.summary.startswith("HN:"):
            try:
                hn_points = int(article.summary.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass

        article.score = score_article(
            title=article.title,
            summary=article.summary,
            source_type=source_type,
            hn_points=hn_points,
        )

        article.category = categorize(article.title, article.summary)
        article.video_hook = generate_video_hook(article.title, article.summary, article.score)

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

        # Format digest
        now = datetime.now()
        digest = format_digest(unsent, now=now)

        # Generate video scripts for top stories
        scripts = generate_scripts_for_digest(unsent, max_scripts=MAX_VIDEO_SCRIPTS)

        # Combine digest + scripts
        full_message = digest
        if scripts:
            full_message += "\n" + scripts

        logger.info("Full message: %d chars", len(full_message))

        # Deliver
        success = True

        if delivery in ("ntfy", "both") and ntfy_topic:
            logger.info("Sending via ntfy...")
            if not _send_ntfy(full_message, ntfy_topic, logger):
                success = False

        if delivery in ("imessage", "both") and recipients:
            # Only attempt iMessage if not in GitHub Actions (no Mac GUI there)
            if os.environ.get("GITHUB_ACTIONS"):
                logger.info("Skipping iMessage (running in GitHub Actions)")
            else:
                logger.info("Sending via iMessage...")
                if not _send_imessage(full_message, recipients, logger):
                    success = False

        if success:
            urls = [a.url for a in unsent]
            store.mark_sent(urls)
            logger.info("Delivered, %d articles marked as sent", len(urls))
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
