"""Tests for the iMessage sender. Uses mocked subprocess."""
import unittest
from unittest.mock import patch, MagicMock

from src.imessage import send_imessage, _build_applescript, _chunk_message


class TestBuildAppleScript(unittest.TestCase):

    def test_basic_script(self):
        script = _build_applescript("Hello world", "+15551234567")
        self.assertIn("send", script)
        self.assertIn("+15551234567", script)
        self.assertIn("Hello world", script)
        self.assertIn("iMessage", script)

    def test_escapes_quotes(self):
        script = _build_applescript('He said "hello"', "+15551234567")
        self.assertIn('\\"', script)

    def test_escapes_backslashes(self):
        script = _build_applescript("path\\to\\file", "+15551234567")
        self.assertIn("\\\\", script)


class TestChunkMessage(unittest.TestCase):

    def test_short_message_single_chunk(self):
        chunks = _chunk_message("Hello", max_len=1000)
        self.assertEqual(len(chunks), 1)

    def test_long_message_split(self):
        msg = "Line\n" * 200
        chunks = _chunk_message(msg, max_len=500)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 500)

    def test_split_on_newline(self):
        msg = "AAA\nBBB\nCCC\nDDD"
        chunks = _chunk_message(msg, max_len=10)
        for chunk in chunks:
            self.assertFalse(chunk.startswith("\n"))


class TestSendIMessage(unittest.TestCase):

    @patch("src.imessage.subprocess.run")
    def test_successful_send(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = send_imessage("Test message", "+15551234567")
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch("src.imessage.subprocess.run")
    def test_failed_send(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="execution error")
        result = send_imessage("Test message", "+15551234567", retry=0)
        self.assertFalse(result)

    @patch("src.imessage.subprocess.run")
    @patch("src.imessage.time.sleep")
    def test_long_message_sends_multiple_chunks(self, mock_sleep, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        long_msg = "Line number whatever\n" * 200
        result = send_imessage(long_msg, "+15551234567", max_chunk=500)
        self.assertTrue(result)
        self.assertGreater(mock_run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
