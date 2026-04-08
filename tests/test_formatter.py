"""Tests for the digest message formatter."""
import unittest
from datetime import datetime, timedelta, timezone

from src.store import Article
from src.formatter import format_digest, _format_article, _truncate, _freshness_label


class TestFormatArticle(unittest.TestCase):

    def test_launch_gets_new_tag(self):
        a = Article(
            url="https://example.com/1",
            title="Anthropic Launches Agent SDK",
            summary="Now available: open-source SDK for building Claude-powered agents",
            source="Anthropic Blog",
            score=9,
            category="CLAUDE",
        )
        line = _format_article(a, 1)
        self.assertIn("1.", line)
        self.assertIn("NEW", line)
        self.assertIn("Anthropic Launches Agent SDK", line)
        self.assertIn("https://example.com/1", line)

    def test_non_launch_no_new_tag(self):
        a = Article(
            url="https://example.com/2",
            title="Minor AI Update",
            summary="Small changes to an AI tool",
            source="Simon Willison",
            score=4,
            category="BUILD",
        )
        line = _format_article(a, 1)
        self.assertIn("1.", line)
        self.assertNotIn("NEW", line)

    def test_includes_source(self):
        a = Article(url="u", title="T", summary="S", source="Reddit", score=5, category="BUILD")
        line = _format_article(a, 1)
        self.assertIn("Reddit", line)

    def test_freshness_shown(self):
        a = Article(
            url="u", title="T", summary="S", source="X", score=5, category="BUILD",
            published=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        line = _format_article(a, 1)
        self.assertIn("3h ago", line)


class TestFreshnessLabel(unittest.TestCase):

    def test_minutes_ago(self):
        pub = datetime.now(timezone.utc) - timedelta(minutes=15)
        self.assertIn("m ago", _freshness_label(pub))

    def test_hours_ago(self):
        pub = datetime.now(timezone.utc) - timedelta(hours=5)
        self.assertEqual("5h ago", _freshness_label(pub))

    def test_yesterday(self):
        pub = datetime.now(timezone.utc) - timedelta(hours=30)
        self.assertEqual("yesterday", _freshness_label(pub))

    def test_days_ago(self):
        pub = datetime.now(timezone.utc) - timedelta(days=3)
        self.assertEqual("3d ago", _freshness_label(pub))

    def test_none_returns_empty(self):
        self.assertEqual("", _freshness_label(None))


class TestTruncate(unittest.TestCase):

    def test_short_string_unchanged(self):
        self.assertEqual(_truncate("hello", 10), "hello")

    def test_long_string_truncated(self):
        result = _truncate("a" * 200, 20)
        self.assertLessEqual(len(result), 23)  # truncate at max_len-1 + "..."
        self.assertTrue(result.endswith("..."))


class TestFormatDigest(unittest.TestCase):

    def test_full_digest(self):
        articles = [
            Article(url="https://a.com/1", title="Top Story", summary="Important news",
                    source="Anthropic Blog", score=9, category="CLAUDE"),
            Article(url="https://a.com/2", title="Second Story", summary="Also big",
                    source="HackerNews", score=7, category="BUILD"),
            Article(url="https://a.com/3", title="Minor Story", summary="Less important",
                    source="Simon Willison", score=4, category="TOOLS"),
        ]
        now = datetime(2026, 4, 6, 18, 0)
        digest = format_digest(articles, now=now, min_top=6, min_notable=3)
        self.assertIn("AI Digest", digest)
        self.assertIn("TOP STORIES", digest)
        self.assertIn("ALSO NOTABLE", digest)
        self.assertIn("Top Story", digest)
        self.assertIn("Minor Story", digest)

    def test_empty_digest(self):
        digest = format_digest([], now=datetime(2026, 4, 6, 8, 0))
        self.assertIn("No notable stories", digest)

    def test_only_top_stories(self):
        articles = [
            Article(url="https://a.com/1", title="Big Story", summary="Important",
                    source="Anthropic Blog", score=9, category="CLAUDE"),
        ]
        digest = format_digest(articles, now=datetime(2026, 4, 6, 18, 0))
        self.assertIn("TOP STORIES", digest)
        self.assertNotIn("ALSO NOTABLE", digest)

    def test_only_notable_stories(self):
        articles = [
            Article(url="https://a.com/1", title="Medium Story", summary="Okay",
                    source="Simon Willison", score=4, category="BUILD"),
        ]
        digest = format_digest(articles, now=datetime(2026, 4, 6, 18, 0), min_top=6, min_notable=3)
        self.assertNotIn("TOP STORIES", digest)
        self.assertIn("ALSO NOTABLE", digest)

    def test_video_pick_for_high_score(self):
        articles = [
            Article(url="https://a.com/1", title="Claude Code Released", summary="New version",
                    source="GitHub Release", score=9, category="CLAUDE"),
        ]
        digest = format_digest(articles, now=datetime(2026, 4, 6, 18, 0))
        self.assertIn("video pick", digest.lower())


if __name__ == "__main__":
    unittest.main()
