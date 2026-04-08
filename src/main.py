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
from src.scorer import score_article, categorize, generate_video_hook, _extract_product_name
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


def _generate_quick_outline(article: Article, text: str, video_format: str) -> str:
    """Generate a quick video outline: titles, thumbnails, and description template.

    Uses keyword matching on article title/summary — no LLM calls.
    Returns a formatted string ready to be appended to the breakdown.
    """
    product = _extract_product_name(article.title)
    product_upper = product.upper()

    # --- Classify article type for template selection ---
    is_launch = any(kw in text for kw in [
        "launch", "release", "introducing", "announcing", "just shipped", "now available",
    ])
    is_tutorial = any(kw in text for kw in [
        "tutorial", "how to", "build", "walkthrough", "step by step",
    ])
    is_tool = any(kw in text for kw in [
        "open-source", "open source", "free", "github", "tool", "library", "framework",
    ])
    is_automation = any(kw in text for kw in [
        "agent", "automation", "workflow", "voice agent",
    ])

    # --- YouTube title options (under 60 chars each) ---
    title_pool = []
    if is_launch:
        title_pool.append(f"{product} Just Launched — First Look + Demo")
        title_pool.append(f"I Tested {product} So You Don't Have To")
        title_pool.append(f"{product} Is Here — Everything You Need to Know")
    if is_tutorial:
        title_pool.append(f"How to Use {product} for AI Automation")
        title_pool.append(f"Build This with {product} in 10 Minutes")
        title_pool.append(f"I Automated Everything with {product}")
    if is_tool:
        title_pool.append(f"This Free AI Tool Replaces {product}")
        title_pool.append(f"I Tested {product} So You Don't Have To")
        title_pool.append(f"{product} — Full Setup and Demo")
    if is_automation:
        title_pool.append(f"I Built an AI Agent with {product}")
        title_pool.append(f"How to Use {product} for AI Automation")
        title_pool.append(f"Automate This with {product} (Full Build)")
    # Fallback if nothing matched
    if not title_pool:
        title_pool = [
            f"I Tested {product} So You Don't Have To",
            f"How to Use {product} for AI Automation",
            f"{product} — Full Breakdown + Demo",
        ]

    # Deduplicate while preserving order, then take first 3
    seen_titles: set[str] = set()
    unique_titles: list[str] = []
    for t in title_pool:
        if t not in seen_titles and len(t) <= 60:
            seen_titles.add(t)
            unique_titles.append(t)
    # If some were too long, add truncated fallbacks
    if len(unique_titles) < 3:
        for t in title_pool:
            short = t[:57] + "..." if len(t) > 60 else t
            if short not in seen_titles:
                seen_titles.add(short)
                unique_titles.append(short)
    titles = unique_titles[:3]

    # --- Thumbnail text options (2-4 words, ALL CAPS) ---
    thumb_pool = []
    if is_launch:
        thumb_pool.append(f"{product_upper} IS HERE")
        thumb_pool.append("JUST LAUNCHED")
        thumb_pool.append(f"NEW {product_upper}")
    if is_tutorial:
        thumb_pool.append("I BUILT THIS")
        thumb_pool.append(f"{product_upper} TUTORIAL")
        thumb_pool.append("FULL BUILD")
    if is_tool:
        thumb_pool.append("FREE AI TOOL")
        thumb_pool.append(f"TRY {product_upper}")
        thumb_pool.append("OPEN SOURCE")
    if is_automation:
        thumb_pool.append("AI AUTOMATION")
        thumb_pool.append("I BUILT THIS")
        thumb_pool.append(f"{product_upper} AGENT")
    if not thumb_pool:
        thumb_pool = [
            f"{product_upper} REVIEW",
            "MUST SEE",
            "AI TOOL",
        ]

    # Deduplicate and pick 3, enforce 2-4 words
    seen_thumbs: set[str] = set()
    unique_thumbs: list[str] = []
    for t in thumb_pool:
        word_count = len(t.split())
        if t not in seen_thumbs and 2 <= word_count <= 4:
            seen_thumbs.add(t)
            unique_thumbs.append(t)
    thumbs = unique_thumbs[:3]
    # Pad if needed
    fallbacks = [f"{product_upper} REVIEW", "MUST SEE", "AI TOOL"]
    for fb in fallbacks:
        if len(thumbs) >= 3:
            break
        if fb not in seen_thumbs and 2 <= len(fb.split()) <= 4:
            thumbs.append(fb)
            seen_thumbs.add(fb)

    # --- Determine verb for description based on type ---
    if is_tutorial:
        verb = "build with"
    elif is_launch:
        verb = "review"
    elif is_tool:
        verb = "test"
    elif is_automation:
        verb = "break down"
    else:
        verb = "test"

    # --- Determine main section label for timestamps ---
    if "Tutorial" in video_format:
        main_section = "Full Build"
    elif "First Look" in video_format:
        main_section = "Live Demo"
    elif "Tool Showcase" in video_format:
        main_section = "Setup + Demo"
    elif "Build & Ship" in video_format:
        main_section = "Full Build"
    else:
        main_section = "Deep Dive"

    # --- One-line summary from article title ---
    summary_line = article.title.rstrip(".")

    # --- Build the hashtag from product name (alphanumeric only) ---
    hashtag = re.sub(r'[^A-Za-z0-9]', '', product)

    # --- Assemble the outline ---
    out = []
    out.append("QUICK VIDEO OUTLINE:")
    out.append("")
    out.append("  Title Options:")
    for i, t in enumerate(titles, 1):
        out.append(f"    {i}. {t}")
    out.append("")
    out.append("  Thumbnail Text Options:")
    for i, t in enumerate(thumbs, 1):
        out.append(f"    {i}. {t}")
    out.append("")
    out.append("  YouTube Description Template:")
    out.append(f"    {summary_line}")
    out.append("")
    out.append(f"    In this video, I {verb} {product}.")
    out.append("")
    out.append("    TIMESTAMPS:")
    out.append("    0:00 — Hook")
    out.append("    0:15 — What this is")
    out.append(f"    1:00 — {main_section}")
    out.append("    7:00 — Testing it live")
    out.append("    8:00 — My verdict + what's next")
    out.append("")
    out.append("    LINKS:")
    out.append(f"    {article.url}")
    out.append("")
    out.append("    Subscribe for daily AI automation tutorials.")
    out.append(f"    #AI #Automation #{hashtag}")

    return "\n".join(out)


def _generate_video_breakdown(article: Article, trend: dict = None) -> str:
    """Generate a clean, readable video brief for one article."""
    hook = generate_video_hook(article.title, article.summary, article.score)
    text = f"{article.title} {article.summary}".lower()
    review = _review_article(article)
    details = _extract_specific_details(article)

    # Determine video format
    if any(kw in text for kw in ["tutorial", "how to", "build", "walkthrough", "step by step"]):
        video_format = "Tutorial"
    elif any(kw in text for kw in ["launch", "release", "introducing", "announcing", "just shipped", "now available"]):
        video_format = "First Look"
    elif any(kw in text for kw in ["open-source", "open source", "free", "github"]):
        video_format = "Tool Showcase"
    elif any(kw in text for kw in ["agent", "automation", "workflow", "voice agent"]):
        video_format = "Build Video"
    else:
        video_format = "News Breakdown"

    # Clean the title
    title = article.title
    if ": " in title and "/" in title.split(": ")[0]:
        title = title.split(": ", 1)[1]

    # Clean summary
    summary = article.summary or ""
    if summary.startswith("r/") and ": " in summary[:40]:
        summary = summary.split(": ", 1)[1]
    if summary.startswith("HN: "):
        summary = ""
    if summary.startswith("Release ") and " — " in summary:
        summary = summary.split(" — ", 1)[1]

    # Build the brief
    lines = []

    # Verdict line — the decision
    tier = review["tier"]
    if "STRONG" in tier:
        lines.append("MAKE THIS VIDEO")
    elif "GOOD" in tier:
        lines.append("WORTH COVERING")
    else:
        lines.append("CONSIDER")
    lines.append("")

    # What it is — one clear paragraph
    lines.append(title)
    if summary:
        lines.append(summary[:200])
    lines.append("")
    lines.append(f"Score: {article.score}/10 · {article.source} · {video_format}")
    lines.append(article.url)
    lines.append("")

    # Search demand
    lines.append(format_trend_line(trend))
    lines.append("")

    # Why now — strengths as a readable sentence
    if review["strengths"]:
        why_parts = []
        for s in review["strengths"]:
            # Strip the ALL CAPS prefix, keep the useful part
            if " — " in s:
                why_parts.append(s.split(" — ", 1)[1])
            else:
                why_parts.append(s.lower())
        lines.append(f"Why now: {'; '.join(why_parts[:3])}")
        lines.append("")

    # Risks — only if there are any real ones
    real_risks = [r for r in review["risks"] if "None" not in r]
    if real_risks:
        risk_parts = []
        for r in real_risks:
            if " — " in r:
                risk_parts.append(r.split(" — ", 1)[1])
            else:
                risk_parts.append(r.lower())
        lines.append(f"Watch out: {'; '.join(risk_parts[:2])}")
        lines.append("")

    # Title options
    lines.append("Title options:")
    outline = _generate_quick_outline(article, text, video_format)
    # Extract just the title lines from the outline
    in_titles = False
    title_count = 0
    for oline in outline.split("\n"):
        stripped = oline.strip()
        if "Title Options:" in oline:
            in_titles = True
            continue
        if in_titles and stripped and stripped[0].isdigit():
            lines.append(f"  {stripped}")
            title_count += 1
            if title_count >= 3:
                in_titles = False
        elif in_titles and not stripped:
            in_titles = False
    lines.append("")

    # Thumbnail
    in_thumbs = False
    thumb_count = 0
    for oline in outline.split("\n"):
        stripped = oline.strip()
        if "Thumbnail Text" in oline:
            in_thumbs = True
            continue
        if in_thumbs and stripped and stripped[0].isdigit():
            if thumb_count == 0:
                lines.append(f"Thumbnail: {stripped[3:]}")  # Take first option, skip "1. "
            thumb_count += 1
            if thumb_count >= 1:
                in_thumbs = False
    lines.append("")

    # How to film it — concise structure
    lines.append(f"How to film ({video_format}):")
    if video_format == "First Look":
        lines.append("  0:00 Hook — show the new feature working")
        lines.append("  0:15 What launched and why it matters")
        lines.append("  1:00 Live demo of each new feature")
        lines.append("  7:00 Honest take — hype or legit?")
        lines.append("  8:00 Subscribe + link in description")
    elif video_format == "Tutorial":
        lines.append("  0:00 Hook — show the finished result")
        lines.append("  0:15 What we're building and why")
        lines.append("  1:00 Step-by-step build from scratch")
        lines.append("  7:00 Test it live with real data")
        lines.append("  8:00 How to extend it + subscribe")
    elif video_format == "Tool Showcase":
        lines.append("  0:00 Hook — show the tool running")
        lines.append("  0:15 What it does and what it replaces")
        lines.append("  1:00 Install + build something real")
        lines.append("  7:00 Pros, cons, who it's for")
        lines.append("  8:00 Link in description + subscribe")
    elif video_format == "Build Video":
        lines.append("  0:00 Hook — show the automation running")
        lines.append("  0:15 Business problem this solves")
        lines.append("  1:00 Full build on screen")
        lines.append("  7:00 Test with real data")
        lines.append("  8:00 How to sell this + subscribe")
    else:
        lines.append("  0:00 Hook — why this matters")
        lines.append("  0:15 Show the announcement")
        lines.append("  1:00 Demo the product/tool")
        lines.append("  7:00 What this means for builders")
        lines.append("  8:00 Your take + subscribe")
    lines.append("")

    # Key things to mention — article-specific
    if details:
        lines.append("Key things to mention:")
        for d in details[:4]:
            lines.append(f"  - {d}")
        lines.append("")

    # Pre-record checklist — short
    lines.append("Before recording:")
    lines.append("  - Search YouTube — has someone covered this already?")
    lines.append("  - Open the link — is the info still current?")
    lines.append("  - Can you demo this on screen in under 10 min?")

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
    lines = []

    # Header — reads like a briefing memo
    lines.append(f"Video Ideas — {now_str}")
    lines.append("")
    if len(reviewed) == 1:
        lines.append("1 idea scored 8+ and passed review.")
    else:
        lines.append(f"{len(reviewed)} ideas scored 8+ and passed review.")
    if skipped:
        skip_titles = [a.title[:50] for a, _ in skipped]
        lines.append(f"Filtered out: {', '.join(skip_titles)}")
    lines.append("")

    # Each idea as a clean brief
    for i, (a, _review) in enumerate(reviewed, 1):
        trend = trends_data.get(a.url)
        if i > 1:
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(f"IDEA {i}")
        lines.append("")
        lines.append(_generate_video_breakdown(a, trend=trend))

    message = "\n".join(lines)
    subject = f"Video Ideas — {now_str}"
    if len(reviewed) == 1:
        # Put the top idea in the subject for quick scanning
        top_title = reviewed[0][0].title[:40]
        subject = f"Video Idea: {top_title}"
    if send_email(message, email_to, subject=subject):
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
