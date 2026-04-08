"""Tests for the main orchestrator."""
import unittest
from unittest.mock import patch
import tempfile
import os
from pathlib import Path

from src.store import Article, ArticleStore
from src.main import process_articles, run_digest


class TestProcessArticles(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        self.store = ArticleStore(self.db_path)

    def tearDown(self):
        self.store.close()
        os.unlink(self.db_path)

    def test_processes_and_deduplicates(self):
        raw = [
            Article(url="https://a.com/1", title="Anthropic Launches Agent SDK",
                    summary="Open-source SDK for agents", source="Anthropic Blog"),
            Article(url="https://b.com/1", title="Anthropic Launches Agent SDK Today",
                    summary="Same story different source", source="Simon Willison"),
            Article(url="https://c.com/1", title="Local Weather Update",
                    summary="Rain expected", source="Other"),
        ]
        processed = process_articles(raw, self.store)
        self.assertEqual(len(processed), 2)
        anthropic_article = [a for a in processed if "Anthropic" in a.title][0]
        self.assertGreater(anthropic_article.score, 0)
        self.assertNotEqual(anthropic_article.category, "")

    def test_empty_input(self):
        processed = process_articles([], self.store)
        self.assertEqual(processed, [])

    def test_hn_points_extracted(self):
        raw = [
            Article(url="https://hn.com/1", title="AI Code Editor",
                    summary="HN: 500 points", source="HackerNews"),
        ]
        processed = process_articles(raw, self.store)
        self.assertEqual(len(processed), 1)
        self.assertGreater(processed[0].score, 0)

    def test_reddit_score_extracted(self):
        raw = [
            Article(url="https://reddit.com/1", title="New MCP Server launches",
                    summary="r/ClaudeAI (350 pts): Amazing new tool", source="Reddit"),
        ]
        processed = process_articles(raw, self.store)
        self.assertEqual(len(processed), 1)
        self.assertGreater(processed[0].score, 0)


class TestRunDigest(unittest.TestCase):

    @patch("src.main.send_ntfy_long")
    @patch("src.main.fetch_all_sources")
    def test_ntfy_delivery(self, mock_fetch, mock_ntfy):
        mock_fetch.return_value = [
            Article(url="https://a.com/1", title="New MCP Server for Claude Code",
                    summary="Build automations with Claude", source="Anthropic Blog"),
        ]
        mock_ntfy.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            result = run_digest(
                db_path=db_path,
                recipients=[],
                ntfy_topic="test-topic",
                delivery="ntfy",
            )
            self.assertTrue(result)
            mock_ntfy.assert_called_once()
            sent_msg = mock_ntfy.call_args[0][0]
            self.assertIn("AI Digest", sent_msg)
        finally:
            os.unlink(db_path)

    @patch("src.main.send_ntfy_long")
    @patch("src.main.fetch_all_sources")
    def test_no_stories_still_sends(self, mock_fetch, mock_ntfy):
        mock_fetch.return_value = []
        mock_ntfy.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            result = run_digest(
                db_path=db_path,
                ntfy_topic="test-topic",
                delivery="ntfy",
            )
            self.assertTrue(result)
            sent_msg = mock_ntfy.call_args[0][0]
            self.assertIn("No notable stories", sent_msg)
        finally:
            os.unlink(db_path)

    @patch("src.main.send_ntfy_long")
    @patch("src.main.fetch_all_sources")
    def test_no_video_scripts_in_digest(self, mock_fetch, mock_ntfy):
        mock_fetch.return_value = [
            Article(url="https://a.com/1", title="New MCP Server for Claude Code Automation",
                    summary="Build AI automations with this open-source MCP tool",
                    source="LangChain Blog"),
        ]
        mock_ntfy.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            run_digest(
                db_path=db_path,
                ntfy_topic="test-topic",
                delivery="ntfy",
            )
            sent_msg = mock_ntfy.call_args[0][0]
            # Digest should NOT contain video scripts
            self.assertNotIn("VIDEO SCRIPTS", sent_msg)
            self.assertNotIn("HOOK", sent_msg)
            # But should still have the digest header
            self.assertIn("AI Digest", sent_msg)
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
