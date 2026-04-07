"""Tests for ntfy.sh notification delivery."""
import unittest
from unittest.mock import patch, MagicMock

from src.notify import send_ntfy, send_ntfy_long


class TestSendNtfy(unittest.TestCase):

    @patch("src.notify.requests.post")
    def test_successful_send(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        result = send_ntfy("Hello", "test-topic")
        self.assertTrue(result)
        mock_post.assert_called_once()
        self.assertIn("test-topic", mock_post.call_args[0][0])

    @patch("src.notify.requests.post")
    def test_failed_send(self, mock_post):
        mock_post.side_effect = Exception("Connection failed")
        result = send_ntfy("Hello", "test-topic")
        self.assertFalse(result)

    def test_empty_topic_fails(self):
        result = send_ntfy("Hello", "")
        self.assertFalse(result)


class TestSendNtfyLong(unittest.TestCase):

    @patch("src.notify.send_ntfy")
    def test_short_message_single_send(self, mock_send):
        mock_send.return_value = True
        result = send_ntfy_long("Short message", "topic")
        self.assertTrue(result)
        self.assertEqual(mock_send.call_count, 1)

    @patch("src.notify.send_ntfy")
    def test_long_message_splits(self, mock_send):
        mock_send.return_value = True
        long_msg = "Line\n" * 2000
        result = send_ntfy_long(long_msg, "topic", chunk_size=500)
        self.assertTrue(result)
        self.assertGreater(mock_send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
