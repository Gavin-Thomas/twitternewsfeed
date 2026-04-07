"""Tests for the scoring and categorization engine."""
import unittest

from src.scorer import score_article, categorize, generate_video_hook


class TestScoreArticle(unittest.TestCase):

    def test_high_impact_automation_story(self):
        score = score_article(
            title="New MCP Server Lets Claude Code Connect to n8n Workflows",
            summary="Build AI automations with this open-source MCP integration",
        )
        self.assertGreaterEqual(score, 7)

    def test_low_relevance_story(self):
        score = score_article(
            title="Local weather update for Tuesday",
            summary="Expect rain in the afternoon",
        )
        self.assertLessEqual(score, 2)

    def test_model_release(self):
        score = score_article(
            title="GPT-5 Released by OpenAI",
            summary="OpenAI releases GPT-5 with new API capabilities",
        )
        self.assertGreaterEqual(score, 4)

    def test_score_capped_at_max(self):
        score = score_article(
            title="Launch: Claude Code MCP n8n Vapi Voice Agent Automation Tool",
            summary="Open-source SDK API workflow chatbot integration",
        )
        self.assertLessEqual(score, 10)

    def test_score_minimum_zero(self):
        score = score_article(title="", summary="")
        self.assertGreaterEqual(score, 0)

    def test_github_repo_bonus(self):
        base = score_article(title="cool-ai-tool", summary="An agent framework")
        with_gh = score_article(title="cool-ai-tool", summary="An agent framework", source_type="github")
        self.assertGreater(with_gh, base)

    def test_hn_high_points_boost(self):
        score_low = score_article(title="Some AI Thing", summary="Details", hn_points=10)
        score_high = score_article(title="Some AI Thing", summary="Details", hn_points=500)
        self.assertGreater(score_high, score_low)

    def test_voice_agent_scores_high(self):
        score = score_article(
            title="Build a Vapi Voice Agent for Client Intake",
            summary="Step by step tutorial for building voice AI automation",
        )
        self.assertGreaterEqual(score, 6)


class TestCategorize(unittest.TestCase):

    def test_claude_category(self):
        cat = categorize("Anthropic releases Claude 4", "New Claude model with improved capabilities")
        self.assertEqual(cat, "CLAUDE")

    def test_health_category(self):
        cat = categorize("AlphaFold Drug Discovery", "FDA approves AI clinical trial tool")
        self.assertEqual(cat, "HEALTH")

    def test_build_category(self):
        cat = categorize("New AI Workflow Tool", "Automate your workflow with this agent SDK")
        self.assertEqual(cat, "BUILD")

    def test_no_category(self):
        cat = categorize("Random News About Nothing", "This is unrelated content")
        self.assertEqual(cat, "")

    def test_tools_category(self):
        cat = categorize("Cursor Gets AI Code Completion", "NotebookLM integration for developers")
        self.assertEqual(cat, "TOOLS")

    def test_biz_category(self):
        cat = categorize("How to Start an AI Agency", "Client acquisition and pricing strategies")
        self.assertEqual(cat, "BIZ")


class TestVideoHook(unittest.TestCase):

    def test_launch_hook(self):
        hook = generate_video_hook("Anthropic Launches Agent SDK", "Open-source SDK for building agents")
        self.assertIsInstance(hook, str)
        self.assertGreater(len(hook), 0)

    def test_no_hook_for_low_score(self):
        hook = generate_video_hook("Boring Update", "Minor patch notes", score=2)
        self.assertEqual(hook, "")

    def test_automation_hook(self):
        hook = generate_video_hook("New n8n AI Automation Template", "Workflow for lead gen")
        self.assertIn("automation", hook.lower())

    def test_voice_agent_hook(self):
        hook = generate_video_hook("Vapi Voice Agent Tutorial", "Build a voice AI for clients")
        self.assertIn("voice agent", hook.lower())

    def test_mcp_hook(self):
        hook = generate_video_hook("New MCP Server for Databases", "Connect Claude Code to SQL")
        self.assertIn("connected", hook.lower())


if __name__ == "__main__":
    unittest.main()
