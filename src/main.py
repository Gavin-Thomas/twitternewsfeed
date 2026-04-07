"""Main orchestrator: fetch -> dedup -> score -> format -> send."""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import (
    DB_PATH, PHONE_NUMBER, LOG_DIR, RETENTION_DAYS,
    MIN_SCORE_TOP, MIN_SCORE_NOTABLE,
)
from src.sources import fetch_all_sources
from src.scorer import score_article, categorize, generate_video_hook
from src.store import Article, ArticleStore
from src.formatter import format_digest
from src.imessage import send_imessage


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
    """Score, categorize, and deduplicate articles.

    Returns the list of new (non-duplicate) articles with scores and categories set.
    """
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


def run_digest(
    db_path: Optional[Path] = None,
    phone: Optional[str] = None,
) -> bool:
    """Run the full digest pipeline. Returns True if digest was sent successfully."""
    logger = logging.getLogger(__name__)

    if db_path is None:
        db_path = DB_PATH
    if phone is None:
        phone = PHONE_NUMBER

    store = ArticleStore(db_path)

    try:
        logger.info("Fetching articles from all sources...")
        raw_articles = fetch_all_sources()
        logger.info("Fetched %d raw articles", len(raw_articles))

        new_articles = process_articles(raw_articles, store)
        logger.info("After dedup: %d new articles", len(new_articles))

        unsent = store.get_unsent(min_score=MIN_SCORE_NOTABLE)
        logger.info("Total unsent articles above threshold: %d", len(unsent))

        now = datetime.now()
        digest = format_digest(unsent, now=now)
        logger.info("Digest formatted (%d chars)", len(digest))

        success = send_imessage(digest, phone)
        if success:
            urls = [a.url for a in unsent]
            store.mark_sent(urls)
            logger.info("Digest sent and %d articles marked as sent", len(urls))
        else:
            logger.error("Failed to send digest")

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
