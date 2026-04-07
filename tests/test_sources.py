"""Tests for news source fetchers. Uses mocked HTTP responses."""
import unittest
from unittest.mock import patch, MagicMock

from src.sources import (
    fetch_rss_feed,
    fetch_hackernews,
    fetch_github_trending,
    fetch_all_sources,
    _parse_hn_response,
    _parse_github_html,
)
from src.store import Article


SAMPLE_HN_JSON = {
    "hits": [
        {
            "title": "Show HN: AI Code Editor",
            "url": "https://example.com/ai-editor",
            "points": 250,
            "objectID": "123456",
            "created_at": "2026-04-06T12:00:00.000Z",
        },
        {
            "title": "LLM Benchmarks Are Broken",
            "url": None,
            "points": 180,
            "objectID": "123457",
            "created_at": "2026-04-06T10:00:00.000Z",
        },
        {
            "title": "Low points story",
            "url": "https://example.com/low",
            "points": 5,
            "objectID": "123458",
            "created_at": "2026-04-06T08:00:00.000Z",
        },
    ]
}

SAMPLE_GITHUB_HTML = """
<html><body>
<article class="Box-row">
    <h2 class="h3 lh-condensed">
        <a href="/anthropics/claude-agent-sdk">
            anthropics / <span>claude-agent-sdk</span>
        </a>
    </h2>
    <p class="col-9 color-fg-muted my-1 pr-4">
        Build AI agents with Claude
    </p>
    <span class="d-inline-block float-sm-right">523 stars today</span>
</article>
<article class="Box-row">
    <h2 class="h3 lh-condensed">
        <a href="/openai/swarm">
            openai / <span>swarm</span>
        </a>
    </h2>
    <p class="col-9 color-fg-muted my-1 pr-4">
        Multi-agent orchestration framework
    </p>
    <span class="d-inline-block float-sm-right">312 stars today</span>
</article>
</body></html>
"""


class TestFetchRSS(unittest.TestCase):

    @patch("src.sources.feedparser.parse")
    def test_parse_rss_entries(self, mock_parse):
        entry1 = MagicMock()
        entry1.title = "Anthropic Releases Claude 4"
        entry1.link = "https://techcrunch.com/anthropic-claude-4"
        entry1.get = lambda k, d="": {"summary": "Claude 4 with improved reasoning."}.get(k, d)
        entry1.published_parsed = (2026, 4, 6, 12, 0, 0, 0, 96, 0)

        entry2 = MagicMock()
        entry2.title = "Google Updates Gemini"
        entry2.link = "https://techcrunch.com/google-gemini-update"
        entry2.get = lambda k, d="": {"summary": "Gemini gets new features."}.get(k, d)
        entry2.published_parsed = (2026, 4, 6, 10, 0, 0, 0, 96, 0)

        mock_parse.return_value = MagicMock(entries=[entry1, entry2], bozo=False)
        articles = fetch_rss_feed("https://example.com/feed", "TestFeed")
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "Anthropic Releases Claude 4")
        self.assertEqual(articles[0].source, "TestFeed")

    @patch("src.sources.feedparser.parse")
    def test_handles_feed_error(self, mock_parse):
        mock_parse.return_value = MagicMock(entries=[], bozo=True)
        articles = fetch_rss_feed("https://bad.url/feed", "Bad")
        self.assertEqual(articles, [])


class TestParseHN(unittest.TestCase):

    def test_parse_hn_response(self):
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=50)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "Show HN: AI Code Editor")
        self.assertEqual(articles[0].source, "HackerNews")

    def test_self_post_gets_hn_url(self):
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=50)
        hn_article = [a for a in articles if "Benchmarks" in a.title][0]
        self.assertIn("news.ycombinator.com", hn_article.url)

    def test_filters_low_points(self):
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=50)
        titles = [a.title for a in articles]
        self.assertNotIn("Low points story", titles)


class TestParseGitHub(unittest.TestCase):

    def test_parse_trending_html(self):
        articles = _parse_github_html(SAMPLE_GITHUB_HTML)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].source, "GitHub")
        self.assertIn("claude-agent-sdk", articles[0].url)
        self.assertIn("Build AI agents", articles[0].summary)

    def test_empty_html(self):
        articles = _parse_github_html("<html><body></body></html>")
        self.assertEqual(articles, [])


class TestFetchAll(unittest.TestCase):

    @patch("src.sources.fetch_github_trending")
    @patch("src.sources.fetch_hackernews")
    @patch("src.sources.fetch_all_rss")
    def test_aggregates_all_sources(self, mock_rss, mock_hn, mock_gh):
        mock_rss.return_value = [
            Article(url="https://tc.com/1", title="RSS Story", summary="S", source="TC")
        ]
        mock_hn.return_value = [
            Article(url="https://hn.com/1", title="HN Story", summary="S", source="HN")
        ]
        mock_gh.return_value = [
            Article(url="https://gh.com/1", title="GH Story", summary="S", source="GH")
        ]
        all_articles = fetch_all_sources()
        self.assertEqual(len(all_articles), 3)


if __name__ == "__main__":
    unittest.main()
