"""Tests for the scoring and categorization engine."""
import unittest
from datetime import datetime, timedelta, timezone

from src.scorer import score_article, categorize, generate_video_hook


class TestScoreArticle(unittest.TestCase):

    def test_new_launch_scores_high(self):
        """An actual product launch should score high."""
        score = score_article(
            title="Anthropic Introduces New MCP Server Framework",
            summary="Now available: open-source MCP integration for Claude Code",
            source_name="Anthropic Blog",
            published=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        self.assertGreaterEqual(score, 7)

    def test_bug_complaint_scores_low(self):
        """A bug report / complaint should score low despite mentioning key tools."""
        score = score_article(
            title="Claude Code is locking people out for hours",
            summary="Users report being locked out, bug causes crashes",
            source_name="HackerNews",
            hn_points=150,
        )
        self.assertLessEqual(score, 3)

    def test_devto_tutorial_existing_tool_scores_moderate(self):
        """A tutorial about an existing tool shouldn't score as high as a launch."""
        tutorial = score_article(
            title="How to Build a Vapi Voice Agent for Client Intake",
            summary="Step by step tutorial for building voice AI automation",
        )
        launch = score_article(
            title="Vapi Announces Voice Agent v2.0",
            summary="Just released: new voice agent platform now available",
            source_name="LangChain Blog",
            published=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        self.assertGreater(launch, tutorial)

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
            source_name="OpenAI News",
            published=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        self.assertGreaterEqual(score, 4)

    def test_score_capped_at_max(self):
        score = score_article(
            title="Introducing: Claude Code MCP Vapi Voice Agent Launches Now Available",
            summary="Just shipped open-source SDK API workflow chatbot integration",
            source_name="Anthropic Blog",
            published=datetime.now(timezone.utc),
        )
        self.assertLessEqual(score, 10)

    def test_score_minimum_zero(self):
        score = score_article(title="", summary="")
        self.assertGreaterEqual(score, 0)

    def test_github_repo_bonus(self):
        base = score_article(title="cool-ai-tool", summary="An agent framework")
        with_gh = score_article(title="cool-ai-tool", summary="An agent framework", source_type="github")
        self.assertGreaterEqual(with_gh, base)

    def test_hn_high_points_boost(self):
        score_low = score_article(title="AI agent launches", summary="Details", source_name="HackerNews", hn_points=10)
        score_high = score_article(title="AI agent launches", summary="Details", source_name="HackerNews", hn_points=500)
        self.assertGreater(score_high, score_low)

    def test_freshness_boost(self):
        """Recent articles should score higher than old ones."""
        recent = score_article(
            title="New MCP Server Launches",
            summary="Open source integration",
            published=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        old = score_article(
            title="New MCP Server Launches",
            summary="Open source integration",
            published=datetime.now(timezone.utc) - timedelta(days=10),
        )
        self.assertGreater(recent, old)

    def test_opinion_penalized(self):
        """Opinion pieces should score lower than factual reporting."""
        opinion = score_article(
            title="My thoughts on why I think Claude Code is overrated",
            summary="Unpopular opinion: the debate around AI agents",
        )
        factual = score_article(
            title="Claude Code Launches Agent SDK",
            summary="Now available: new open-source SDK for building agents",
        )
        self.assertGreater(factual, opinion)

    def test_reddit_high_score_boost(self):
        low = score_article(title="AI agent tool", summary="Check this out", reddit_score=30)
        high = score_article(title="AI agent tool", summary="Check this out", reddit_score=500)
        self.assertGreater(high, low)

    def test_source_authority(self):
        """Official blog should score higher than unknown source."""
        official = score_article(
            title="Introducing new Claude features",
            summary="Now available in Claude Code",
            source_name="Anthropic Blog",
        )
        unknown = score_article(
            title="Introducing new Claude features",
            summary="Now available in Claude Code",
            source_name="Random Blog",
        )
        self.assertGreater(official, unknown)


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

    def test_first_look_hook_for_launches(self):
        hook = generate_video_hook("Acme AI Introducing New Tool", "Just shipped today")
        self.assertIn("FIRST LOOK", hook)


if __name__ == "__main__":
    unittest.main()
