"""Tests for the scoring and categorization engine."""
import unittest

from src.scorer import score_article, categorize, generate_video_hook


class TestScoreArticle(unittest.TestCase):

    def test_high_impact_story(self):
        score = score_article(
            title="Anthropic Launches Open-Source Agent SDK",
            summary="New SDK enables developers to build Claude-powered agents with full API access",
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
            summary="OpenAI releases GPT-5 with breakthrough reasoning capabilities",
        )
        self.assertGreaterEqual(score, 5)

    def test_score_capped_at_max(self):
        score = score_article(
            title="OpenAI Launches GPT-5 Open-Source Breakthrough API SDK Agent Tool",
            summary="Billion dollar funding breakthrough releases automation workflow",
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


class TestCategorize(unittest.TestCase):

    def test_claude_category(self):
        cat = categorize("Anthropic releases Claude 4", "New Claude model with improved capabilities")
        self.assertEqual(cat, "CLAUDE")

    def test_health_category(self):
        cat = categorize("AlphaFold Drug Discovery", "FDA approves AI clinical trial tool")
        self.assertEqual(cat, "HEALTH")

    def test_automation_category(self):
        cat = categorize("New AI Workflow Tool", "Automate your workflow with this agent SDK")
        self.assertEqual(cat, "AI-AUTO")

    def test_no_category(self):
        cat = categorize("Random News About Nothing", "This is unrelated content")
        self.assertEqual(cat, "")

    def test_first_match_priority(self):
        cat = categorize(
            "Claude Code Agent Automation",
            "Anthropic workflow tool for developers",
        )
        self.assertIn(cat, ["CLAUDE", "AI-AUTO"])


class TestVideoHook(unittest.TestCase):

    def test_launch_hook(self):
        hook = generate_video_hook("Anthropic Launches Agent SDK", "Open-source SDK for building agents")
        self.assertIsInstance(hook, str)
        self.assertGreater(len(hook), 0)

    def test_no_hook_for_low_score(self):
        hook = generate_video_hook("Boring Update", "Minor patch notes", score=2)
        self.assertEqual(hook, "")

    def test_tool_hook(self):
        hook = generate_video_hook("New AI Framework Drops", "Build agents with this SDK")
        self.assertIn("built something", hook)

    def test_model_hook(self):
        hook = generate_video_hook("Claude Gets Major Update", "New capabilities")
        self.assertIn("model", hook)


if __name__ == "__main__":
    unittest.main()
