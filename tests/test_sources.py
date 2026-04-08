"""Tests for news source fetchers. Uses mocked HTTP responses."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src.sources import (
    fetch_rss_feed,
    fetch_hackernews,
    fetch_github_trending,
    fetch_all_sources,
    _parse_hn_response,
    _parse_github_html,
    _parse_reddit_response,
    _parse_github_releases,
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

SAMPLE_REDDIT_JSON = {
    "data": {
        "children": [
            {
                "data": {
                    "id": "abc123",
                    "title": "Claude Code just got MCP support",
                    "url": "https://example.com/claude-mcp",
                    "score": 450,
                    "upvote_ratio": 0.95,
                    "stickied": False,
                    "subreddit": "ClaudeAI",
                    "selftext": "This is amazing - full MCP integration",
                    "permalink": "/r/ClaudeAI/comments/abc123/",
                    "created_utc": 1712400000,
                }
            },
            {
                "data": {
                    "id": "def456",
                    "title": "Low score post",
                    "url": "https://example.com/low",
                    "score": 10,
                    "upvote_ratio": 0.5,
                    "stickied": False,
                    "subreddit": "ClaudeAI",
                    "selftext": "",
                    "permalink": "/r/ClaudeAI/comments/def456/",
                    "created_utc": 1712400000,
                }
            },
            {
                "data": {
                    "id": "ghi789",
                    "title": "Pinned announcement",
                    "url": "https://reddit.com/r/ClaudeAI/pinned",
                    "score": 500,
                    "upvote_ratio": 0.9,
                    "stickied": True,
                    "subreddit": "ClaudeAI",
                    "selftext": "",
                    "permalink": "/r/ClaudeAI/comments/ghi789/",
                    "created_utc": 1712400000,
                }
            },
        ]
    }
}

SAMPLE_GITHUB_RELEASES = [
    {
        "tag_name": "v1.5.0",
        "name": "v1.5.0 — MCP Support",
        "body": "## What's New\n- Full MCP server support\n- Bug fixes",
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.5.0",
        "published_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "tag_name": "v1.4.0",
        "name": "v1.4.0",
        "body": "Minor improvements",
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.4.0",
        "published_at": "2020-01-01T00:00:00Z",  # Very old, should be filtered
    },
]


class TestFetchRSS(unittest.TestCase):

    @patch("src.sources.feedparser.parse")
    def test_parse_rss_entries(self, mock_parse):
        entry1 = MagicMock()
        entry1.title = "Anthropic Releases Claude 4"
        entry1.link = "https://anthropic.com/claude-4"
        entry1.get = lambda k, d="": {"summary": "Claude 4 with improved reasoning."}.get(k, d)
        entry1.published_parsed = (2026, 4, 6, 12, 0, 0, 0, 96, 0)

        entry2 = MagicMock()
        entry2.title = "Google Updates Gemini"
        entry2.link = "https://blog.google/gemini-update"
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
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=100)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "Show HN: AI Code Editor")
        self.assertEqual(articles[0].source, "HackerNews")

    def test_self_post_gets_hn_url(self):
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=100)
        hn_article = [a for a in articles if "Benchmarks" in a.title][0]
        self.assertIn("news.ycombinator.com", hn_article.url)

    def test_filters_low_points(self):
        articles = _parse_hn_response(SAMPLE_HN_JSON, min_points=100)
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


class TestParseReddit(unittest.TestCase):

    def test_parse_reddit_response(self):
        articles = _parse_reddit_response(SAMPLE_REDDIT_JSON)
        # Should include high-score post, exclude low-score and stickied
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Claude Code just got MCP support")
        self.assertEqual(articles[0].source, "Reddit")
        self.assertIn("r/ClaudeAI", articles[0].summary)

    def test_filters_low_score(self):
        articles = _parse_reddit_response(SAMPLE_REDDIT_JSON)
        titles = [a.title for a in articles]
        self.assertNotIn("Low score post", titles)

    def test_filters_stickied(self):
        articles = _parse_reddit_response(SAMPLE_REDDIT_JSON)
        titles = [a.title for a in articles]
        self.assertNotIn("Pinned announcement", titles)

    def test_empty_response(self):
        articles = _parse_reddit_response({"data": {"children": []}})
        self.assertEqual(articles, [])


class TestParseGitHubReleases(unittest.TestCase):

    def test_parse_recent_releases(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        articles = _parse_github_releases(SAMPLE_GITHUB_RELEASES, "anthropics/claude-code", cutoff)
        # Only the recent release should be included
        self.assertEqual(len(articles), 1)
        self.assertIn("v1.5.0", articles[0].title)
        self.assertEqual(articles[0].source, "GitHub Release")

    def test_filters_old_releases(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        articles = _parse_github_releases(SAMPLE_GITHUB_RELEASES, "anthropics/claude-code", cutoff)
        titles = [a.title for a in articles]
        self.assertFalse(any("v1.4.0" in t for t in titles))

    def test_empty_releases(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        articles = _parse_github_releases([], "some/repo", cutoff)
        self.assertEqual(articles, [])


class TestFetchAll(unittest.TestCase):

    @patch("src.sources.fetch_x_posts")
    @patch("src.sources.fetch_github_releases")
    @patch("src.sources.fetch_reddit")
    @patch("src.sources.fetch_github_trending")
    @patch("src.sources.fetch_hackernews")
    @patch("src.sources.fetch_all_rss")
    def test_aggregates_all_sources(self, mock_rss, mock_hn, mock_gh, mock_reddit, mock_releases, mock_x):
        mock_rss.return_value = [
            Article(url="https://tc.com/1", title="RSS Story", summary="S", source="TC")
        ]
        mock_hn.return_value = [
            Article(url="https://hn.com/1", title="HN Story", summary="S", source="HN")
        ]
        mock_gh.return_value = [
            Article(url="https://gh.com/1", title="GH Story", summary="S", source="GH")
        ]
        mock_reddit.return_value = [
            Article(url="https://reddit.com/1", title="Reddit Story", summary="S", source="Reddit")
        ]
        mock_releases.return_value = [
            Article(url="https://gh.com/rel/1", title="Release", summary="S", source="GitHub Release")
        ]
        mock_x.return_value = [
            Article(url="https://x.com/1", title="X Post", summary="S", source="X/Twitter")
        ]
        all_articles = fetch_all_sources()
        self.assertEqual(len(all_articles), 6)


if __name__ == "__main__":
    unittest.main()
