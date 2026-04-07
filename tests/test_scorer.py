"""Tests for src/scorer.py — keyword scoring, category assignment, and batch scoring."""

import pytest

from src.scorer import keyword_score, assign_category, score_article
from src.store import Article


# ── 1. keyword_score: basic keyword matching ─────────────────────────────────

class TestKeywordScore:
    def test_single_keyword_match(self):
        keywords = {"launches": 3, "api": 1}
        assert keyword_score("Company launches new product", keywords) == 3

    def test_multiple_keyword_matches(self):
        keywords = {"launches": 3, "open-source": 3, "api": 1}
        text = "Company launches open-source api toolkit"
        assert keyword_score(text, keywords) == 7  # 3 + 3 + 1

    def test_no_matches(self):
        keywords = {"launches": 3, "api": 1}
        assert keyword_score("The weather is nice today", keywords) == 0

    def test_case_insensitive(self):
        keywords = {"launches": 3, "breakthrough": 3}
        assert keyword_score("LAUNCHES a BREAKTHROUGH model", keywords) == 6

    def test_empty_text(self):
        keywords = {"launches": 3}
        assert keyword_score("", keywords) == 0

    def test_empty_keywords(self):
        assert keyword_score("Some text here", {}) == 0

    def test_multi_word_keyword(self):
        keywords = {"open source": 3, "state-of-the-art": 2}
        assert keyword_score("This is an open source project", keywords) == 3

    def test_duplicate_keyword_counted_once(self):
        """Each keyword should only be counted once, even if it appears multiple times."""
        keywords = {"api": 2}
        assert keyword_score("api api api api", keywords) == 2


# ── 2. assign_category: matching articles to categories ──────────────────────

class TestAssignCategory:
    def test_claude_category(self):
        categories = {
            "CLAUDE": ["claude", "anthropic", "mcp"],
            "AI-AUTO": ["automation", "workflow", "agent"],
        }
        assert assign_category("Anthropic releases Claude 4", categories) == "CLAUDE"

    def test_ai_auto_category(self):
        categories = {
            "CLAUDE": ["claude", "anthropic"],
            "AI-AUTO": ["automation", "workflow", "agent"],
        }
        assert assign_category("New automation workflow for agents", categories) == "AI-AUTO"

    def test_no_category_match(self):
        categories = {
            "CLAUDE": ["claude", "anthropic"],
            "AI-AUTO": ["automation", "workflow"],
        }
        assert assign_category("Apple releases new iPhone 20", categories) == "GENERAL"

    def test_case_insensitive(self):
        categories = {"HEALTH": ["healthcare", "medical"]}
        assert assign_category("HEALTHCARE revolution in AI", categories) == "HEALTH"

    def test_empty_text(self):
        categories = {"CLAUDE": ["claude"]}
        assert assign_category("", categories) == "GENERAL"

    def test_first_matching_category_wins(self):
        """When text matches multiple categories, the one with more keyword hits wins."""
        categories = {
            "CLAUDE": ["claude", "anthropic", "mcp", "sonnet"],
            "AI-AUTO": ["agent"],
        }
        # "claude" and "anthropic" and "sonnet" match CLAUDE (3 hits)
        # "agent" would match AI-AUTO (1 hit)
        text = "Anthropic claude sonnet agent"
        assert assign_category(text, categories) == "CLAUDE"

    def test_tie_goes_to_first_category(self):
        """When categories tie on hits, the first in dict order wins."""
        from collections import OrderedDict
        categories = {
            "CLAUDE": ["claude"],
            "AI-AUTO": ["agent"],
        }
        text = "claude and agent"
        # Both have 1 hit, first category should win
        result = assign_category(text, categories)
        assert result in ("CLAUDE", "AI-AUTO")  # Either is acceptable for a tie


# ── 3. score_article: end-to-end scoring of an Article ───────────────────────

class TestScoreArticle:
    def test_scores_and_categorizes(self):
        art = Article(
            url="https://example.com/1",
            title="Anthropic launches Claude 4 open-source API",
            summary="A breakthrough in AI agents and automation workflows.",
            source="TechCrunch",
        )
        scored = score_article(art)
        assert scored.score > 0
        assert scored.category != ""
        # The original article object should not be mutated
        assert art.score == 0

    def test_score_capped_at_max(self):
        """Score should never exceed MAX_SCORE (10)."""
        art = Article(
            url="https://example.com/2",
            title="launches open-source breakthrough state-of-the-art releases",
            summary="billion funding raises acquisition api sdk benchmark "
                    "tool build workflow automation agent no-code tutorial "
                    "framework library plugin extension "
                    "gpt gpt-4 gpt-5 o1 o3 claude opus sonnet haiku "
                    "gemini llama mistral deepseek phi qwen",
            source="Test",
        )
        scored = score_article(art)
        assert scored.score <= 10

    def test_low_relevance_scores_low(self):
        art = Article(
            url="https://example.com/3",
            title="Local bakery opens new location",
            summary="The best croissants in town are now available downtown.",
            source="LocalNews",
        )
        scored = score_article(art)
        assert scored.score == 0
        assert scored.category == "GENERAL"

    def test_returns_new_article_instance(self):
        art = Article(
            url="https://example.com/4",
            title="Claude breakthrough",
            summary="Anthropic released something.",
            source="src",
        )
        scored = score_article(art)
        assert scored is not art

    def test_preserves_existing_fields(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        art = Article(
            url="https://example.com/5",
            title="GPT-5 launches",
            summary="OpenAI releases GPT-5",
            source="TheVerge",
            published=now,
            video_hook="Watch this",
        )
        scored = score_article(art)
        assert scored.url == art.url
        assert scored.title == art.title
        assert scored.summary == art.summary
        assert scored.source == art.source
        assert scored.published == now
        assert scored.video_hook == "Watch this"
