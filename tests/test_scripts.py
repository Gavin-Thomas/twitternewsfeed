"""Tests for the video script generator."""
import unittest

from src.store import Article
from src.scripts import generate_script, generate_scripts_for_digest


class TestGenerateScript(unittest.TestCase):

    def test_mcp_script(self):
        a = Article(
            url="https://example.com/1",
            title="New MCP Server for Databases",
            summary="Connect Claude Code to any SQL database",
            source="HuggingFace", score=8, category="BUILD",
        )
        script = generate_script(a)
        self.assertIn("VIDEO:", script)
        self.assertIn("HOOK", script)
        self.assertIn("DEMO", script)
        self.assertIn("TAKEAWAY", script)
        self.assertIn("Claude Code", script)

    def test_voice_agent_script(self):
        a = Article(
            url="https://example.com/2",
            title="Build a Vapi Voice Agent",
            summary="Step by step voice AI tutorial",
            source="Dev.to", score=7, category="BUILD",
        )
        script = generate_script(a)
        self.assertIn("voice agent", script.lower())

    def test_automation_script(self):
        a = Article(
            url="https://example.com/3",
            title="Automate Lead Gen with AI",
            summary="Full automation workflow tutorial",
            source="LangChain", score=6, category="BUILD",
        )
        script = generate_script(a)
        self.assertIn("autopilot", script.lower())

    def test_includes_demo_steps(self):
        a = Article(
            url="https://example.com/4",
            title="Cursor AI Coding Tutorial",
            summary="Build a full app with Cursor",
            source="Dev.to", score=7, category="TOOLS",
        )
        script = generate_script(a)
        # Should have numbered demo steps
        self.assertIn("1.", script)
        self.assertIn("2.", script)


class TestGenerateScriptsForDigest(unittest.TestCase):

    def test_generates_for_top_stories(self):
        articles = [
            Article(url="https://a.com/1", title="MCP Server Launch", summary="S",
                    source="TC", score=8, category="BUILD"),
            Article(url="https://a.com/2", title="Low Score", summary="S",
                    source="TC", score=2, category=""),
        ]
        result = generate_scripts_for_digest(articles, max_scripts=3)
        self.assertIn("VIDEO SCRIPTS", result)
        self.assertIn("MCP Server Launch", result)
        self.assertNotIn("Low Score", result)

    def test_empty_when_no_top_stories(self):
        articles = [
            Article(url="https://a.com/1", title="Low", summary="S",
                    source="TC", score=2, category=""),
        ]
        result = generate_scripts_for_digest(articles, max_scripts=3)
        self.assertEqual(result, "")

    def test_respects_max_scripts(self):
        articles = [
            Article(url=f"https://a.com/{i}", title=f"Story {i}", summary="S",
                    source="TC", score=8, category="BUILD")
            for i in range(10)
        ]
        result = generate_scripts_for_digest(articles, max_scripts=2)
        self.assertEqual(result.count("📹 VIDEO:"), 2)


if __name__ == "__main__":
    unittest.main()
