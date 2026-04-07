"""Tests for src/store.py — Article dataclass, ArticleStore, and title_similarity."""

from datetime import datetime, timedelta, timezone

import pytest

from src.store import Article, ArticleStore, title_similarity


# ── 1. Article dataclass creation with all fields ──────────────────────────

def test_article_all_fields():
    now = datetime.now(timezone.utc)
    a = Article(
        url="https://example.com/post",
        title="Big AI Launch",
        summary="Summary text here",
        source="TechCrunch",
        score=8,
        category="AI-AUTO",
        published=now,
        video_hook="Check this out!",
    )
    assert a.url == "https://example.com/post"
    assert a.title == "Big AI Launch"
    assert a.summary == "Summary text here"
    assert a.source == "TechCrunch"
    assert a.score == 8
    assert a.category == "AI-AUTO"
    assert a.published == now
    assert a.video_hook == "Check this out!"


# ── 2. Article defaults ────────────────────────────────────────────────────

def test_article_defaults():
    a = Article(url="https://x.com", title="T", summary="S", source="src")
    assert a.score == 0
    assert a.category == ""
    assert a.published is None
    assert a.video_hook is None


# ── 3. ArticleStore table creation ─────────────────────────────────────────

def test_table_creation(tmp_path):
    db = tmp_path / "test.db"
    store = ArticleStore(db)
    cur = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
    )
    assert cur.fetchone() is not None
    store.close()


# ── 4. Add and retrieve (is_seen_url) ─────────────────────────────────────

def test_add_and_is_seen_url(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    art = Article(url="https://example.com/1", title="Title One", summary="s", source="src")
    assert store.add(art) is True
    assert store.is_seen_url("https://example.com/1") is True
    assert store.is_seen_url("https://example.com/unknown") is False
    store.close()


# ── 5. Duplicate URL rejected ─────────────────────────────────────────────

def test_duplicate_url_rejected(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    art = Article(url="https://example.com/1", title="Title", summary="s", source="src")
    assert store.add(art) is True
    assert store.add(art) is False
    store.close()


# ── 6. Fuzzy title dedup ──────────────────────────────────────────────────

def test_fuzzy_title_dedup(tmp_path):
    store = ArticleStore(tmp_path / "test.db", similarity_threshold=0.6)
    a1 = Article(
        url="https://a.com/1",
        title="OpenAI Launches New GPT-5 Model Today",
        summary="s",
        source="src",
    )
    a2 = Article(
        url="https://b.com/2",
        title="OpenAI Launches New GPT-5 Model",
        summary="s",
        source="src",
    )
    assert store.add(a1) is True
    assert store.add(a2) is False  # near-duplicate title
    store.close()


# ── 7. Different titles accepted ──────────────────────────────────────────

def test_different_titles_accepted(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    a1 = Article(url="https://a.com/1", title="Apple releases new iPhone", summary="s", source="src")
    a2 = Article(url="https://b.com/2", title="SpaceX Starship reaches orbit", summary="s", source="src")
    assert store.add(a1) is True
    assert store.add(a2) is True
    store.close()


# ── 8. get_unsent ordering ────────────────────────────────────────────────

def test_get_unsent_ordering(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    store.add(Article(url="https://a.com/lo", title="Low Score", summary="s", source="src", score=2))
    store.add(Article(url="https://a.com/hi", title="High Score", summary="s", source="src", score=9))
    store.add(Article(url="https://a.com/mid", title="Mid Score", summary="s", source="src", score=5))

    unsent = store.get_unsent()
    assert len(unsent) == 3
    assert unsent[0].score == 9
    assert unsent[1].score == 5
    assert unsent[2].score == 2
    store.close()


# ── 9. mark_sent ──────────────────────────────────────────────────────────

def test_mark_sent(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    store.add(Article(url="https://a.com/1", title="Title A", summary="s", source="src", score=5))
    store.add(Article(url="https://a.com/2", title="Title B", summary="s", source="src", score=3))

    store.mark_sent(["https://a.com/1"])

    unsent = store.get_unsent()
    assert len(unsent) == 1
    assert unsent[0].url == "https://a.com/2"
    store.close()


# ── 10. cleanup_old ───────────────────────────────────────────────────────

def test_cleanup_old(tmp_path):
    store = ArticleStore(tmp_path / "test.db")
    store.add(Article(url="https://a.com/old", title="Old Article", summary="s", source="src"))
    store.add(Article(url="https://a.com/new", title="New Article", summary="s", source="src"))

    # Backdate the first article to 31 days ago
    old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    url_hash = ArticleStore._url_hash("https://a.com/old")
    store._conn.execute(
        "UPDATE articles SET first_seen = ? WHERE url_hash = ?",
        (old_date, url_hash),
    )
    store._conn.commit()

    removed = store.cleanup(days=30)
    assert removed == 1

    # The new article should still be there
    assert store.is_seen_url("https://a.com/new") is True
    assert store.is_seen_url("https://a.com/old") is False
    store.close()


# ── 11. title_similarity function ─────────────────────────────────────────

class TestTitleSimilarity:
    def test_identical(self):
        assert title_similarity("Hello World", "Hello World") == 1.0

    def test_completely_different(self):
        assert title_similarity("apple banana cherry", "dog elephant fox") == 0.0

    def test_partial_overlap_above_threshold(self):
        sim = title_similarity(
            "OpenAI Launches New GPT-5 Model",
            "OpenAI Launches GPT-5 Model Today",
        )
        assert sim > 0.6

    def test_case_insensitive(self):
        assert title_similarity("Hello World", "hello world") == 1.0
