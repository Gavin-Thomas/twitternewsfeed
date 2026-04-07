"""SQLite-backed article store with URL dedup and fuzzy title matching."""

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Article:
    """A single news article."""

    url: str
    title: str
    summary: str
    source: str
    score: int = 0
    category: str = ""
    published: Optional[datetime] = None
    video_hook: Optional[str] = None


def title_similarity(a: str, b: str) -> float:
    """Jaccard word-overlap similarity, case-insensitive."""
    words_a = set(re.findall(r"\w+", a.lower()))
    words_b = set(re.findall(r"\w+", b.lower()))
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class ArticleStore:
    """Persistent article storage with deduplication."""

    def __init__(self, db_path: Path, similarity_threshold: float = 0.6) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._similarity_threshold = similarity_threshold
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS articles (
                url_hash    TEXT PRIMARY KEY,
                title_hash  TEXT,
                url         TEXT,
                title       TEXT,
                summary     TEXT,
                source      TEXT,
                score       INTEGER,
                category    TEXT,
                published   TEXT,
                video_hook  TEXT,
                first_seen  TEXT,
                sent        INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_articles_sent ON articles(sent);
            CREATE INDEX IF NOT EXISTS idx_articles_first_seen ON articles(first_seen);
            """
        )

    # ── Hashing helpers ────────────────────────────────────────────────

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @staticmethod
    def _title_hash(title: str) -> str:
        return hashlib.sha256(title.lower().strip().encode()).hexdigest()[:16]

    # ── Dedup queries ──────────────────────────────────────────────────

    def is_seen_url(self, url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM articles WHERE url_hash = ?",
            (self._url_hash(url),),
        ).fetchone()
        return row is not None

    def _is_fuzzy_duplicate(self, title: str) -> bool:
        # Exact title hash match first (fast path).
        th = self._title_hash(title)
        exact = self._conn.execute(
            "SELECT 1 FROM articles WHERE title_hash = ?", (th,)
        ).fetchone()
        if exact:
            return True

        # Fuzzy match against recent titles (7-day window).
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rows = self._conn.execute(
            "SELECT title FROM articles WHERE first_seen >= ?", (cutoff,)
        ).fetchall()
        for row in rows:
            if title_similarity(title, row["title"]) >= self._similarity_threshold:
                return True
        return False

    # ── CRUD ───────────────────────────────────────────────────────────

    def add(self, article: Article) -> bool:
        """Add an article. Returns True if added, False if duplicate."""
        if self.is_seen_url(article.url):
            return False
        if self._is_fuzzy_duplicate(article.title):
            return False

        self._conn.execute(
            """
            INSERT INTO articles
                (url_hash, title_hash, url, title, summary, source,
                 score, category, published, video_hook, first_seen, sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                self._url_hash(article.url),
                self._title_hash(article.title),
                article.url,
                article.title,
                article.summary,
                article.source,
                article.score,
                article.category,
                article.published.isoformat() if article.published else None,
                article.video_hook,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return True

    def get_unsent(self, min_score: int = 0) -> list[Article]:
        """Return unsent articles with score >= min_score, ordered by score DESC."""
        rows = self._conn.execute(
            "SELECT * FROM articles WHERE sent = 0 AND score >= ? ORDER BY score DESC",
            (min_score,),
        ).fetchall()
        return [self._row_to_article(r) for r in rows]

    def mark_sent(self, urls: list[str]) -> None:
        """Mark the given URLs as sent."""
        hashes = [self._url_hash(u) for u in urls]
        placeholders = ",".join("?" for _ in hashes)
        self._conn.execute(
            f"UPDATE articles SET sent = 1 WHERE url_hash IN ({placeholders})",
            hashes,
        )
        self._conn.commit()

    def cleanup(self, days: int = 30) -> int:
        """Delete articles older than *days*. Returns count removed."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur = self._conn.execute(
            "DELETE FROM articles WHERE first_seen < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()

    # ── Internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> Article:
        published = None
        if row["published"]:
            published = datetime.fromisoformat(row["published"])
        return Article(
            url=row["url"],
            title=row["title"],
            summary=row["summary"],
            source=row["source"],
            score=row["score"],
            category=row["category"],
            published=published,
            video_hook=row["video_hook"],
        )
