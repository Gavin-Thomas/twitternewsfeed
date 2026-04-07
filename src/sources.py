"""Fetch articles from RSS feeds, HackerNews, and GitHub Trending."""
import logging
import re
from datetime import datetime
from time import mktime
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from src.config import (
    RSS_FEEDS, HN_API_URL, HN_QUERIES, HN_HITS_PER_PAGE, HN_MIN_POINTS,
    GITHUB_TRENDING_URL, REQUEST_TIMEOUT, USER_AGENT,
)
from src.store import Article

logger = logging.getLogger(__name__)


def _clean_html(raw: str) -> str:
    """Strip HTML tags from a string."""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


def fetch_rss_feed(url: str, source_name: str) -> list[Article]:
    """Fetch and parse a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning("Feed error for %s: %s", source_name, getattr(feed, "bozo_exception", "unknown"))
            return []

        articles = []
        for entry in feed.entries:
            pub = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub = datetime.fromtimestamp(mktime(entry.published_parsed))
                except (TypeError, ValueError, OverflowError):
                    pass

            summary_raw = entry.get("summary", "") or entry.get("description", "")
            summary = _clean_html(summary_raw)[:300]

            articles.append(Article(
                url=entry.link,
                title=entry.title.strip(),
                summary=summary,
                source=source_name,
                published=pub,
            ))
        return articles

    except Exception as e:
        logger.error("Failed to fetch RSS %s: %s", source_name, e)
        return []


def fetch_all_rss() -> list[Article]:
    """Fetch all configured RSS feeds."""
    all_articles = []
    for name, url in RSS_FEEDS.items():
        articles = fetch_rss_feed(url, name)
        logger.info("Fetched %d articles from %s", len(articles), name)
        all_articles.extend(articles)
    return all_articles


def fetch_hackernews() -> list[Article]:
    """Fetch AI-related stories from HackerNews Algolia API (recent only)."""
    all_articles = []
    seen_ids: set[str] = set()

    # Only fetch stories from the last 48 hours
    import time
    two_days_ago = int(time.time()) - (48 * 3600)

    for query in HN_QUERIES:
        try:
            resp = requests.get(
                HN_API_URL,
                params={
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": HN_HITS_PER_PAGE,
                    "numericFilters": f"created_at_i>{two_days_ago}",
                },
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
            articles = _parse_hn_response(data, min_points=HN_MIN_POINTS, seen_ids=seen_ids)
            all_articles.extend(articles)
        except Exception as e:
            logger.error("HN query '%s' failed: %s", query, e)

    logger.info("Fetched %d articles from HackerNews", len(all_articles))
    return all_articles


def _parse_hn_response(
    data: dict,
    min_points: int = 50,
    seen_ids: Optional[set] = None,
) -> list[Article]:
    """Parse HN API response into Articles."""
    if seen_ids is None:
        seen_ids = set()

    articles = []
    for hit in data.get("hits", []):
        oid = hit.get("objectID", "")
        if oid in seen_ids:
            continue
        seen_ids.add(oid)

        points = hit.get("points", 0) or 0
        if points < min_points:
            continue

        url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        title = hit.get("title", "").strip()
        if not title:
            continue

        articles.append(Article(
            url=url,
            title=title,
            summary=f"HN: {points} points",
            source="HackerNews",
        ))

    return articles


def fetch_github_trending() -> list[Article]:
    """Fetch GitHub trending repositories page."""
    try:
        resp = requests.get(
            GITHUB_TRENDING_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        articles = _parse_github_html(resp.text)
        logger.info("Fetched %d repos from GitHub Trending", len(articles))
        return articles
    except Exception as e:
        logger.error("GitHub Trending failed: %s", e)
        return []


def _parse_github_html(html: str) -> list[Article]:
    """Parse GitHub trending page HTML into Articles."""
    soup = BeautifulSoup(html, "html.parser")
    articles = []

    for row in soup.select("article.Box-row"):
        h2 = row.select_one("h2 a")
        if not h2:
            continue
        href = h2.get("href", "").strip()
        if not href:
            continue

        repo_url = f"https://github.com{href}"
        repo_name = href.strip("/").replace("/", " / ")

        desc_el = row.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        stars_text = ""
        for span in row.select("span"):
            text = span.get_text(strip=True)
            if "stars today" in text.lower() or "stars this" in text.lower():
                stars_text = text
                break

        summary = description
        if stars_text:
            summary += f" ({stars_text})"

        articles.append(Article(
            url=repo_url,
            title=repo_name,
            summary=summary[:300],
            source="GitHub",
        ))

    return articles


def fetch_all_sources() -> list[Article]:
    """Fetch from all sources and return combined list."""
    articles = []
    articles.extend(fetch_all_rss())
    articles.extend(fetch_hackernews())
    articles.extend(fetch_github_trending())
    return articles
