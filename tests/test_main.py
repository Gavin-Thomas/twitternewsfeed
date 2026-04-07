"""Tests for the main orchestrator."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
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
                    summary="Open-source SDK for agents", source="TC"),
            Article(url="https://b.com/1", title="Anthropic Launches Agent SDK Today",
                    summary="Same story different source", source="Verge"),
            Article(url="https://c.com/1", title="Local Weather Update",
                    summary="Rain expected", source="Other"),
        ]
        processed = process_articles(raw, self.store)
        # Fuzzy dedup should catch the near-duplicate
        self.assertEqual(len(processed), 2)
        # First article should be scored
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
        # HN points bonus should boost the score
        self.assertGreater(processed[0].score, 0)


class TestRunDigest(unittest.TestCase):

    @patch("src.main.send_imessage")
    @patch("src.main.fetch_all_sources")
    def test_full_flow(self, mock_fetch, mock_send):
        mock_fetch.return_value = [
            Article(url="https://a.com/1", title="Anthropic Launches New SDK",
                    summary="Open-source agent SDK", source="TC"),
        ]
        mock_send.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            result = run_digest(db_path=db_path, phone="+15551234567")
            self.assertTrue(result)
            mock_send.assert_called_once()
            sent_msg = mock_send.call_args[0][0]
            self.assertIn("AI DIGEST", sent_msg)
        finally:
            os.unlink(db_path)

    @patch("src.main.send_imessage")
    @patch("src.main.fetch_all_sources")
    def test_no_stories_still_sends(self, mock_fetch, mock_send):
        mock_fetch.return_value = []
        mock_send.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            result = run_digest(db_path=db_path, phone="+15551234567")
            self.assertTrue(result)
            sent_msg = mock_send.call_args[0][0]
            self.assertIn("No notable stories", sent_msg)
        finally:
            os.unlink(db_path)

    @patch("src.main.send_imessage")
    @patch("src.main.fetch_all_sources")
    def test_send_failure(self, mock_fetch, mock_send):
        mock_fetch.return_value = [
            Article(url="https://a.com/1", title="Story", summary="S", source="TC"),
        ]
        mock_send.return_value = False

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            result = run_digest(db_path=db_path, phone="+15551234567")
            self.assertFalse(result)
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
