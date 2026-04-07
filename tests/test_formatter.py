"""Tests for the digest message formatter."""
import unittest
from datetime import datetime

from src.store import Article
from src.formatter import format_digest, _format_article_line, _truncate


class TestFormatArticleLine(unittest.TestCase):

    def test_top_story_format(self):
        a = Article(
            url="https://example.com/1",
            title="Anthropic Launches Agent SDK",
            summary="Open-source SDK for building Claude-powered agents",
            source="TechCrunch",
            score=9,
            category="AI-AUTO",
        )
        line = _format_article_line(a)
        self.assertIn("[9/10]", line)
        self.assertIn("🔥", line)
        self.assertIn("[AI-AUTO]", line)
        self.assertIn("Anthropic Launches Agent SDK", line)

    def test_notable_story_no_hook(self):
        a = Article(
            url="https://example.com/2",
            title="Minor AI Update",
            summary="Small changes to an AI tool",
            source="Ars Technica",
            score=4,
            category="LLM",
        )
        line = _format_article_line(a, include_hook=False)
        self.assertIn("[4/10]", line)
        self.assertNotIn("📹", line)

    def test_fire_emoji_for_high_score(self):
        a = Article(url="u", title="T", summary="S", source="X", score=8, category="C")
        line = _format_article_line(a, include_hook=False)
        self.assertIn("🔥", line)

    def test_no_fire_for_low_score(self):
        a = Article(url="u", title="T", summary="S", source="X", score=5, category="C")
        line = _format_article_line(a, include_hook=False)
        self.assertNotIn("🔥", line)

    def test_no_category_bracket_when_empty(self):
        a = Article(url="u", title="T", summary="S", source="X", score=5, category="")
        line = _format_article_line(a, include_hook=False)
        self.assertNotIn("[]", line)


class TestTruncate(unittest.TestCase):

    def test_short_string_unchanged(self):
        self.assertEqual(_truncate("hello", 10), "hello")

    def test_long_string_truncated(self):
        result = _truncate("a" * 100, 20)
        self.assertEqual(len(result), 20)
        self.assertTrue(result.endswith("..."))


class TestFormatDigest(unittest.TestCase):

    def test_full_digest(self):
        articles = [
            Article(url="https://a.com/1", title="Top Story", summary="Important news",
                    source="TC", score=9, category="CLAUDE",
                    video_hook='"Testing the new Claude"'),
            Article(url="https://a.com/2", title="Second Story", summary="Also big",
                    source="HN", score=7, category="AI-AUTO"),
            Article(url="https://a.com/3", title="Minor Story", summary="Less important",
                    source="Verge", score=4, category="LLM"),
        ]
        now = datetime(2026, 4, 6, 18, 0)
        digest = format_digest(articles, now=now, min_top=6, min_notable=3)
        self.assertIn("AI DIGEST", digest)
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
                    source="TC", score=9, category="CLAUDE"),
        ]
        digest = format_digest(articles, now=datetime(2026, 4, 6, 18, 0))
        self.assertIn("TOP STORIES", digest)
        self.assertNotIn("ALSO NOTABLE", digest)

    def test_only_notable_stories(self):
        articles = [
            Article(url="https://a.com/1", title="Medium Story", summary="Okay",
                    source="TC", score=4, category="LLM"),
        ]
        digest = format_digest(articles, now=datetime(2026, 4, 6, 18, 0), min_top=6, min_notable=3)
        self.assertNotIn("TOP STORIES", digest)
        self.assertIn("ALSO NOTABLE", digest)


if __name__ == "__main__":
    unittest.main()
