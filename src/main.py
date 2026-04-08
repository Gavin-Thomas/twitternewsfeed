"""Main orchestrator: fetch -> dedup -> score -> format -> send -> export."""
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import (
    DB_PATH, RECIPIENTS, NTFY_TOPIC, FALLBACK_EMAIL, LOG_DIR, RETENTION_DAYS,
    MIN_SCORE_NOTABLE, DELIVERY_MODE,
)
from src.sources import fetch_all_sources
from src.scorer import score_article, categorize, generate_video_hook
from src.store import Article, ArticleStore
from src.formatter import format_digest
from src.notify import send_ntfy_long, send_email
from src.trends import extract_search_terms, check_trend, format_trend_line


def setup_logging() -> None:
    """Configure logging to both file and stderr."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"digest_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def process_articles(raw_articles: list[Article], store: ArticleStore) -> list[Article]:
    """Score, categorize, and deduplicate articles."""
    processed = []
    for article in raw_articles:
        source_type = "github" if article.source in ("GitHub", "GitHub Release") else "rss"

        hn_points = 0
        if article.source == "HackerNews" and article.summary.startswith("HN:"):
            try:
                hn_points = int(article.summary.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass

        reddit_score = 0
        if article.source == "Reddit":
            try:
                # Extract score from "r/sub (123 pts)" format
                match = re.search(r"\((\d+) pts\)", article.summary)
                if match:
                    reddit_score = int(match.group(1))
            except (ValueError, AttributeError):
                pass

        article.score = score_article(
            title=article.title,
            summary=article.summary,
            source_name=article.source,
            source_type=source_type,
            hn_points=hn_points,
            reddit_score=reddit_score,
            published=article.published,
        )

        article.category = categorize(article.title, article.summary)

        if store.add(article):
            processed.append(article)

    return processed


def _send_imessage(message: str, recipients: list[str], logger: logging.Logger) -> bool:
    """Send via iMessage (local Mac only)."""
    from src.imessage import send_imessage
    all_ok = True
    for recipient in recipients:
        logger.info("iMessage -> %s", recipient)
        if not send_imessage(message, recipient):
            logger.error("iMessage failed for %s", recipient)
            all_ok = False
    return all_ok


def _send_ntfy(message: str, topic: str, logger: logging.Logger) -> bool:
    """Send via ntfy.sh (works from anywhere)."""
    now = datetime.now().strftime("%a %b %-d, %-I:%M %p")
    return send_ntfy_long(message, topic, title=f"AI Digest — {now}")


def run_digest(
    db_path: Optional[Path] = None,
    recipients: Optional[list[str]] = None,
    ntfy_topic: Optional[str] = None,
    delivery: Optional[str] = None,
) -> bool:
    """Run the full digest pipeline."""
    logger = logging.getLogger(__name__)

    if db_path is None:
        db_path = DB_PATH
    if recipients is None:
        recipients = RECIPIENTS
    if ntfy_topic is None:
        ntfy_topic = NTFY_TOPIC
    if delivery is None:
        delivery = DELIVERY_MODE

    store = ArticleStore(db_path)

    try:
        # Fetch
        logger.info("Fetching articles from all sources...")
        raw_articles = fetch_all_sources()
        logger.info("Fetched %d raw articles", len(raw_articles))

        # Process
        new_articles = process_articles(raw_articles, store)
        logger.info("After dedup: %d new articles", len(new_articles))

        # Get unsent
        unsent = store.get_unsent(min_score=MIN_SCORE_NOTABLE)
        logger.info("Unsent above threshold: %d", len(unsent))

        # Format digest (clean news only — no video ideas)
        now = datetime.now()
        full_message = format_digest(unsent, now=now)

        logger.info("Full message: %d chars", len(full_message))

        # Deliver — at least one method must succeed
        any_delivered = False

        # Email (works from anywhere — GitHub Actions, local Mac, etc.)
        if delivery in ("email", "both"):
            email_to = FALLBACK_EMAIL
            if email_to:
                logger.info("Sending via email to %s...", email_to)
                now_str = datetime.now().strftime("%a %b %-d")
                if send_email(full_message, email_to, subject=f"AI Digest — {now_str}"):
                    any_delivered = True
                else:
                    logger.warning("Email delivery failed")

        # ntfy (works from anywhere — GitHub Actions, local Mac, etc.)
        if delivery in ("ntfy", "both") and ntfy_topic:
            logger.info("Sending via ntfy...")
            if _send_ntfy(full_message, ntfy_topic, logger):
                any_delivered = True

        # iMessage (local Mac only)
        if delivery in ("imessage", "both") and recipients:
            if os.environ.get("GITHUB_ACTIONS"):
                logger.info("Skipping iMessage (running in GitHub Actions)")
            else:
                logger.info("Sending via iMessage...")
                if _send_imessage(full_message, recipients, logger):
                    any_delivered = True

        success = any_delivered

        if success:
            urls = [a.url for a in unsent]
            store.mark_sent(urls)
            logger.info("Delivered, %d articles marked as sent", len(urls))

            # Export scored articles for the video ideas trigger to consume
            export_path = db_path.parent / "latest_digest.json"
            _export_articles(unsent, export_path, logger)

            # Send video ideas email for high-scoring articles
            _send_video_ideas(unsent, logger)
        else:
            logger.error("Delivery failed — articles NOT marked as sent (will retry)")

        # Cleanup
        removed = store.cleanup(days=RETENTION_DAYS)
        if removed:
            logger.info("Cleaned up %d old articles", removed)

        return success

    except Exception as e:
        logger.exception("Digest pipeline failed: %s", e)
        return False

    finally:
        store.close()


def _export_articles(articles: list[Article], path: Path, logger: logging.Logger) -> None:
    """Export scored articles to JSON for the video ideas trigger."""
    data = [
        {
            "title": a.title,
            "summary": a.summary,
            "source": a.source,
            "score": a.score,
            "category": a.category,
            "url": a.url,
        }
        for a in articles
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    logger.info("Exported %d articles to %s", len(data), path)


def _review_article(article: Article) -> dict:
    """Adversarial review — assess whether an article is actually worth a video.

    Returns a dict with verdict, strengths, risks, and quality tier.
    """
    text = f"{article.title} {article.summary}".lower()

    strengths = []
    risks = []

    # --- Strengths ---
    if any(kw in text for kw in ["launch", "release", "introducing", "announcing", "just shipped", "now available"]):
        strengths.append("NEW RELEASE — time-sensitive, be first to cover it")
    if any(kw in text for kw in ["open-source", "open source", "free"]):
        strengths.append("FREE/OPEN SOURCE — viewers can follow along without paying")
    if any(kw in text for kw in ["tutorial", "how to", "build", "walkthrough"]):
        strengths.append("TUTORIAL ANGLE — high watch time, viewers stay for the full build")
    if any(kw in text for kw in ["api", "sdk", "integration", "mcp", "webhook"]):
        strengths.append("TECHNICAL DEMO — can show real code and real results on screen")
    if any(kw in text for kw in ["agent", "automation", "workflow", "voice agent"]):
        strengths.append("AUTOMATION — your core niche, audience expects this content")
    if any(kw in text for kw in ["money", "revenue", "client", "agency", "saas", "monetize"]):
        strengths.append("BUSINESS ANGLE — viewers love 'how to make money with AI' content")
    if article.source in ("GitHub Release", "Anthropic Blog", "OpenAI News", "LangChain Blog"):
        strengths.append(f"OFFICIAL SOURCE ({article.source}) — authoritative, not secondhand")
    if article.source == "Reddit":
        # Extract upvotes from summary
        pts_match = re.search(r"\((\d+) pts\)", article.summary)
        if pts_match and int(pts_match.group(1)) >= 200:
            strengths.append(f"COMMUNITY VALIDATED — {pts_match.group(1)} upvotes, proven interest")

    # --- Risks / Reasons to skip ---
    if article.source == "Reddit" and not any(kw in text for kw in [
        "launch", "release", "open source", "built", "build", "introducing", "tool", "api"
    ]):
        risks.append("REDDIT DISCUSSION ONLY — may be opinion/meme, not actionable content")
    if not any(kw in text for kw in [
        "build", "demo", "tutorial", "api", "tool", "launch", "release",
        "open source", "code", "install", "setup", "automate"
    ]):
        risks.append("LOW DEMO POTENTIAL — hard to show on screen, may be talking-head only")
    if any(kw in text for kw in ["rumor", "leaked", "reportedly", "might", "may", "could"]):
        risks.append("UNCONFIRMED — speculation, could be wrong by the time you publish")
    if article.score <= 4:
        risks.append("BORDERLINE SCORE — only include if nothing better is available today")
    if not article.url or "redd.it" in article.url:
        risks.append("NO DIRECT LINK — source is an image/video post, hard to reference")

    # Determine tier
    if article.score >= 7 and len(strengths) >= 2 and len(risks) == 0:
        tier = "STRONG — make this video"
    elif article.score >= 5 and len(strengths) >= 1:
        tier = "GOOD — worth covering if you have time"
    elif len(risks) > len(strengths):
        tier = "SKIP — risks outweigh the upside"
    else:
        tier = "MAYBE — only if nothing better today"

    return {
        "tier": tier,
        "strengths": strengths or ["None identified — generic AI content"],
        "risks": risks or ["None — looks solid"],
    }


def _extract_specific_details(article: Article) -> list[str]:
    """Pull out specific details from the article for talking points."""
    text = f"{article.title} {article.summary}"
    points = []

    # Extract product/tool names mentioned
    tools_mentioned = []
    known = ["Claude Code", "Claude", "GPT", "Gemini", "Gemma", "DeepSeek",
             "Vapi", "n8n", "Cursor", "MCP", "Codex", "LangChain", "Ollama"]
    for tool in known:
        if tool.lower() in text.lower():
            tools_mentioned.append(tool)
    if tools_mentioned:
        points.append(f"Tools/products mentioned: {', '.join(tools_mentioned)}")

    # Extract version numbers
    versions = re.findall(r'v\d+[\.\d]*', text)
    if versions:
        points.append(f"Version: {', '.join(set(versions))} — compare to previous version on screen")

    # Extract star counts / points
    stars = re.search(r'(\d+)\s*stars?\s*today', text.lower())
    if stars:
        points.append(f"Trending: {stars.group(1)} GitHub stars today — show the repo live")

    pts = re.search(r'\((\d+)\s*pts\)', text)
    if pts:
        points.append(f"Reddit: {pts.group(1)} upvotes — read top comments for viewer hooks")

    hn_pts = re.search(r'HN:\s*(\d+)\s*points', text)
    if hn_pts:
        points.append(f"HackerNews: {hn_pts.group(1)} points — developer audience validated this")

    # Source-specific suggestions
    if article.source == "GitHub Release":
        points.append("Show the release notes on screen, then demo the new features")
        points.append("Compare: install old version, show limitation, then upgrade and show fix")
    elif article.source == "Reddit":
        points.append("Pull up the Reddit thread — show top comments and reactions")
        points.append("If there's a linked tool/repo, demo it live instead of just discussing")
    elif article.source in ("Anthropic Blog", "OpenAI News", "LangChain Blog"):
        points.append("Show the official blog post on screen, then switch to a live demo")
        points.append("Check if there's a playground, API, or quickstart you can show immediately")
    elif article.source == "X/Twitter":
        points.append("Show the tweet on screen — screengrab the thread and quote-tweets")
        points.append("If the tweet links to a tool/launch, demo THAT instead of just reading the tweet")

    # Content-specific angles
    if any(kw in text.lower() for kw in ["voice agent", "voice ai", "speech", "realtime"]):
        points.append("DEMO IDEA: Call the voice agent live on camera — audiences love live voice demos")
    if any(kw in text.lower() for kw in ["mcp", "mcp server"]):
        points.append("DEMO IDEA: Connect MCP server to Claude Code and show a real workflow")
    if any(kw in text.lower() for kw in ["open-source", "open source"]):
        points.append("DEMO IDEA: Clone the repo, run it locally, show it working in under 5 min")
    if any(kw in text.lower() for kw in ["api", "sdk"]):
        points.append("DEMO IDEA: Write a quick script using the API, show input → output on screen")

    return points


def _generate_video_breakdown(article: Article, trend: dict = None) -> str:
    """Generate a thorough, article-specific video breakdown with adversarial review."""
    hook = generate_video_hook(article.title, article.summary, article.score)
    text = f"{article.title} {article.summary}".lower()
    review = _review_article(article)
    details = _extract_specific_details(article)

    # Determine video format
    if any(kw in text for kw in ["tutorial", "how to", "build", "walkthrough", "step by step"]):
        video_format = "Tutorial / Walkthrough"
        structure = (
            "1. Hook: show the finished result first (15s)\n"
            "2. Why this matters for your audience (30s)\n"
            "3. Setup & prerequisites on screen (1-2 min)\n"
            "4. Full build — every step recorded (5-8 min)\n"
            "5. Test it live with real data (1-2 min)\n"
            "6. How to extend this / monetize it (1 min)\n"
            "7. CTA: link in description, ask to subscribe (15s)"
        )
    elif any(kw in text for kw in ["launch", "release", "introducing", "announcing", "just shipped", "now available"]):
        video_format = "First Look / Review"
        structure = (
            "1. Hook: '[Tool] just dropped — here's what changed' (15s)\n"
            "2. Show the announcement/release notes on screen (30s)\n"
            "3. Live demo: walk through the new features one by one (3-5 min)\n"
            "4. Before vs. after: what's actually different? (1-2 min)\n"
            "5. Who should use this and who should wait (1 min)\n"
            "6. Your honest take — hype or legit? (30s)\n"
            "7. CTA: 'Try it yourself, link below' (15s)"
        )
    elif any(kw in text for kw in ["open-source", "open source", "free", "github"]):
        video_format = "Tool Showcase"
        structure = (
            "1. Hook: show the tool running, state what it replaces (15s)\n"
            "2. What it does and why it exists (30s)\n"
            "3. Install on screen — git clone, setup, first run (2-3 min)\n"
            "4. Build something real with it, not a toy example (4-6 min)\n"
            "5. Honest pros and cons (1 min)\n"
            "6. Who this is for and what to build next (30s)\n"
            "7. CTA: repo link in description (15s)"
        )
    elif any(kw in text for kw in ["agent", "automation", "workflow", "voice agent"]):
        video_format = "Build & Ship"
        structure = (
            "1. Hook: show the finished automation running (15s)\n"
            "2. The business problem this solves + who pays (30s)\n"
            "3. Architecture overview — what connects to what (1 min)\n"
            "4. Full build on screen, explain each step (5-8 min)\n"
            "5. Test with real data, show real output (1-2 min)\n"
            "6. How to package and sell this to clients (1 min)\n"
            "7. CTA: subscribe for more automation builds (15s)"
        )
    else:
        video_format = "News Breakdown"
        structure = (
            "1. Hook: one-sentence summary of why this matters (15s)\n"
            "2. Show the source on screen, walk through key details (1-2 min)\n"
            "3. Live demo or walkthrough of the product/tool (3-5 min)\n"
            "4. What this means for AI builders specifically (1 min)\n"
            "5. What you can build or change in your workflow now (1 min)\n"
            "6. Your take — is this the real deal? (30s)\n"
            "7. CTA: what video should I make next? (15s)"
        )

    # Build the breakdown
    lines = []

    # Header with quality tier
    lines.append(f"VERDICT: {review['tier']}")
    lines.append("")

    # Title options
    lines.append(f"YOUTUBE TITLE: {hook}" if hook else f"YOUTUBE TITLE: \"{article.title}\"")
    lines.append(f"FORMAT: {video_format}")
    lines.append("")

    # Source with full link
    lines.append(f"SOURCE: {article.title}")
    lines.append(f"  {article.source} | Score: {article.score}/10 | {article.category or 'General'}")
    lines.append(f"  {article.url}")
    lines.append("")

    # Google Trends — search demand validation
    lines.append(format_trend_line(trend))
    lines.append("")

    # What it is — full summary
    lines.append("WHAT IT IS:")
    summary = article.summary[:500] if article.summary else "(no summary available)"
    lines.append(f"  {summary}")
    lines.append("")

    # Why cover this NOW
    lines.append("WHY COVER THIS:")
    for s in review["strengths"]:
        lines.append(f"  + {s}")
    lines.append("")

    # Risks / reasons to skip
    lines.append("WATCH OUT FOR:")
    for r in review["risks"]:
        lines.append(f"  ! {r}")
    lines.append("")

    # Video structure
    lines.append("VIDEO STRUCTURE:")
    lines.append(structure)
    lines.append("")

    # Article-specific talking points and demo ideas
    if details:
        lines.append("SPECIFIC TO THIS ARTICLE:")
        for d in details:
            lines.append(f"  - {d}")
        lines.append("")

    # Pre-production checklist
    lines.append("BEFORE YOU RECORD:")
    lines.append("  [ ] Search YouTube: has a bigger creator already covered this?")
    lines.append("  [ ] Can you actually demo this on screen in under 10 minutes?")
    lines.append("  [ ] Open the source link and verify the info is still current")
    if article.source == "Reddit":
        lines.append("  [ ] Read the top Reddit comments — best hooks are often there")
    if any(kw in text for kw in ["launch", "release", "introducing"]):
        lines.append("  [ ] Check the official docs/changelog for details the article missed")
    lines.append("  [ ] Draft thumbnail text (3-5 words max) before recording")

    return "\n".join(lines)


def _send_video_ideas(articles: list[Article], logger: logging.Logger) -> None:
    """Generate and email video ideas with adversarial review.

    Only articles scoring 8+ get video ideas. These are the highest-signal
    items — real launches, trending tools, and validated new releases.
    """
    candidates = [a for a in articles if a.score >= 8]
    if not candidates:
        logger.info("No articles scored 8+ for video ideas")
        return

    email_to = FALLBACK_EMAIL
    if not email_to:
        return

    # Run adversarial review and filter
    reviewed = []
    skipped = []
    for a in candidates:
        review = _review_article(a)
        if "SKIP" in review["tier"]:
            skipped.append((a, review))
        else:
            reviewed.append((a, review))

    if not reviewed:
        logger.info("All %d candidates failed adversarial review", len(candidates))
        return

    # Run Google Trends check on top ideas only (rate-limited to ~15 queries)
    import time as _time
    trends_data: dict[str, dict] = {}
    # Check all reviewed ideas (only 8+ now, so count is small)
    trends_candidates = reviewed[:15]
    if trends_candidates:
        logger.info("Checking Google Trends for %d top ideas...", len(trends_candidates))
        seen_terms: set[str] = set()
        for a, _ in trends_candidates:
            terms = extract_search_terms(a.title, a.summary)
            # Skip if we already checked this term
            term_key = terms[0] if terms else ""
            if not terms or term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            trend = check_trend(terms, geo="US")
            if trend:
                # Apply trend result to all articles with the same term
                for a2, _ in reviewed:
                    t2 = extract_search_terms(a2.title, a2.summary)
                    if t2 and t2[0] == term_key:
                        trends_data[a2.url] = trend
            _time.sleep(3)  # Rate limit: 1 query per 3s to avoid 429s
        logger.info("Google Trends: checked %d unique terms, got data for %d ideas",
                     len(seen_terms), len(trends_data))

    now_str = datetime.now().strftime("%a %b %-d")
    lines = [f"AI VIDEO IDEAS — {now_str}", ""]
    lines.append(f"{len(reviewed)} ideas passed review (out of {len(candidates)} candidates).")
    if skipped:
        lines.append(f"{len(skipped)} filtered out:")
        for a, r in skipped:
            lines.append(f"  SKIP: {a.title[:60]} — {r['risks'][0] if r['risks'] else 'low quality'}")
    lines.append("")
    lines.append("=" * 60)

    for i, (a, _review) in enumerate(reviewed, 1):
        trend = trends_data.get(a.url)
        lines.append("")
        lines.append(f"IDEA #{i}")
        lines.append("-" * 40)
        lines.append(_generate_video_breakdown(a, trend=trend))
        lines.append("")
        lines.append("=" * 60)

    message = "\n".join(lines)
    if send_email(message, email_to, subject=f"AI Video Ideas — {now_str}"):
        logger.info("Video ideas email sent (%d ideas, %d skipped)", len(reviewed), len(skipped))
    else:
        logger.warning("Video ideas email failed")


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== AI Digest starting ===")

    success = run_digest()

    logger.info("=== AI Digest finished (success=%s) ===", success)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
