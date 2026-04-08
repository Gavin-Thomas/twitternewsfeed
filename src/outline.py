"""Keyword-based YouTube video outline generator for AI automation content.

Generates complete video production plans (hook, titles, structure,
description, talking points) from a topic string. No LLM API calls —
all logic is keyword-driven so it runs for free.
"""
import re
from datetime import datetime

from src.config import (
    LAUNCH_KEYWORDS,
    CATEGORIES,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Known product names — shared with scorer.py via the same pattern
_KNOWN_PRODUCTS = [
    "Claude Code", "Claude", "Anthropic", "GPT-5", "GPT-4o", "GPT",
    "Gemini", "Gemma", "DeepSeek", "Cursor", "Windsurf",
    "Vapi", "Voiceflow", "Bland AI", "n8n", "LangChain",
    "CrewAI", "AutoGen", "MCP", "Codex", "NotebookLM",
    "Ollama", "LM Studio", "Hugging Face", "LlamaIndex",
    "Make.com", "Zapier", "Replit", "Bolt", "Lovable", "v0",
]

# Words to skip when extracting a product name from the title
_SKIP_WORDS = {
    "the", "a", "an", "and", "or", "for", "in", "on", "at", "to",
    "is", "new", "with", "its", "my", "i", "we", "you", "how",
    "why", "what", "this", "that", "just", "got", "from", "but",
    "so", "if", "it", "our", "some", "someone", "introducing",
}


def _extract_product_name(title: str) -> str:
    """Extract a likely product/tool name from the title.

    Checks known product names first, then falls back to the first
    two capitalized words that aren't common filler.
    """
    text_lower = title.lower()
    for product in _KNOWN_PRODUCTS:
        if product.lower() in text_lower:
            return product

    words = title.split()
    parts: list[str] = []
    for w in words:
        clean = w.strip(".,!?:;—-\"'()")
        if clean and clean[0:1].isupper() and clean.lower() not in _SKIP_WORDS:
            parts.append(clean)
            if len(parts) >= 2:
                break
    return " ".join(parts) if parts else "this AI tool"


def _detect_video_type(text: str) -> str:
    """Classify a topic into a video type using keyword matching.

    Returns one of: Tutorial, First Look, Tool Showcase, News Breakdown.
    """
    if any(kw in text for kw in [
        "tutorial", "how to", "build", "walkthrough", "step by step",
        "automate", "automation", "workflow", "set up", "setup",
    ]):
        return "Tutorial"

    if any(kw in text for kw in [
        "launch", "release", "introducing", "announcing", "just shipped",
        "now available", "unveiled", "debut", "just dropped",
    ]):
        return "First Look"

    if any(kw in text for kw in [
        "open-source", "open source", "free", "github", "repo",
        "self-host", "self host", "clone",
    ]):
        return "Tool Showcase"

    return "News Breakdown"


def _detect_topic_flags(text: str) -> dict[str, bool]:
    """Detect boolean signals about the topic content."""
    return {
        "is_launch": any(kw in text for kw in LAUNCH_KEYWORDS),
        "is_open_source": any(kw in text for kw in [
            "open-source", "open source", "free", "self-host",
        ]),
        "is_automation": any(kw in text for kw in [
            "automation", "workflow", "n8n", "make.com", "zapier", "agent",
        ]),
        "is_voice": any(kw in text for kw in [
            "voice agent", "voice ai", "vapi", "voiceflow", "bland ai",
        ]),
        "is_mcp": any(kw in text for kw in ["mcp", "mcp server"]),
        "is_model": any(kw in text for kw in [
            "gpt", "claude", "gemini", "llama", "deepseek", "model",
        ]),
        "is_coding_tool": any(kw in text for kw in [
            "cursor", "windsurf", "copilot", "claude code", "codex",
            "bolt", "lovable", "v0", "replit",
        ]),
        "is_business": any(kw in text for kw in [
            "agency", "client", "saas", "revenue", "monetize",
        ]),
    }


def _categorize(text: str) -> str:
    """Assign the best matching category from config.CATEGORIES."""
    best_cat = ""
    best_count = 0
    for cat, keywords in CATEGORIES.items():
        count = sum(1 for kw in keywords if kw.lower() in text)
        if count > best_count:
            best_count = count
            best_cat = cat
    return best_cat


# ---------------------------------------------------------------------------
# Hook generation
# ---------------------------------------------------------------------------

def _generate_hooks(topic: str, product: str, flags: dict, video_type: str) -> list[str]:
    """Generate 2-3 conversational hook options for the opening 15 seconds."""
    hooks: list[str] = []

    if flags["is_voice"]:
        hooks.append(f"Watch what happens when I build a voice agent with {product} from scratch.")
        hooks.append(f"I just built an AI that answers the phone for you — here's the full walkthrough.")

    if flags["is_mcp"]:
        hooks.append(f"Watch what happens when I connect {product} to my entire file system.")
        hooks.append("I gave Claude access to everything on my computer — the results are insane.")

    if flags["is_launch"]:
        hooks.append(f"{product} just dropped — let me show you what it actually does.")
        hooks.append(f"FIRST LOOK: {product} is finally here. I tested it so you don't have to.")

    if flags["is_open_source"]:
        hooks.append("This free tool just replaced a $500/month subscription — let me show you.")
        hooks.append(f"{product} is free, open-source, and you can run it right now.")

    if flags["is_automation"]:
        hooks.append("I built an automation that runs 24/7 and makes money while I sleep.")
        hooks.append(f"This {product} workflow took me 15 minutes to build — here's exactly how.")

    if flags["is_coding_tool"]:
        hooks.append(f"I built a full app with {product} in one sitting — no boilerplate, no setup.")
        hooks.append(f"Watch me build a complete project with {product} in real time.")

    if flags["is_business"]:
        hooks.append(f"I'm selling this AI automation to clients for $2,000 a pop. Here's how.")
        hooks.append("This is the exact AI service I'd start if I had to start over today.")

    if flags["is_model"]:
        hooks.append(f"The new {product} changes everything for automations — let me prove it.")
        hooks.append(f"I tested {product} on real tasks. The results surprised me.")

    # Always ensure at least 2 hooks
    if len(hooks) < 2:
        hooks.append(f"Here's how to use {product} for AI automation — full breakdown.")
        hooks.append(f"I tested {product} so you don't have to. Here's what I found.")

    return hooks[:3]


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

def _generate_titles(topic: str, product: str, flags: dict, video_type: str) -> list[str]:
    """Generate 3 YouTube title options, all under 60 characters."""
    titles: list[str] = []

    if video_type == "Tutorial":
        titles.append(f"How to Build with {product} (Full Tutorial)")
        titles.append(f"I Automated This with {product} in 15 Min")
        titles.append(f"{product} Tutorial: Step-by-Step Guide")

    elif video_type == "First Look":
        titles.append(f"{product} Just Launched — First Look")
        titles.append(f"I Tested {product} So You Don't Have To")
        titles.append(f"What's New in {product} (Hands-On)")

    elif video_type == "Tool Showcase":
        titles.append(f"{product}: The Free AI Tool You Need")
        titles.append(f"I Tested {product} — Free and Open Source")
        titles.append(f"{product} Review: Is This Free Tool Worth It?")

    else:  # News Breakdown
        titles.append(f"{product} Changes Everything for AI")
        titles.append(f"Why {product} Matters for AI Builders")
        titles.append(f"The {product} Update You Need to Know")

    # Overrides for specific niches
    if flags["is_voice"]:
        titles[0] = f"I Built an AI Voice Agent with {product}"
    if flags["is_business"]:
        titles[0] = f"How to Sell {product} to Clients"
    if flags["is_mcp"]:
        titles[0] = f"I Connected {product} to Everything"

    # Enforce 60-char limit — truncate product name if needed
    final: list[str] = []
    for t in titles:
        if len(t) > 60:
            t = t[:57] + "..."
        final.append(t)

    return final[:3]


# ---------------------------------------------------------------------------
# Thumbnail text
# ---------------------------------------------------------------------------

def _generate_thumbnail_texts(product: str, flags: dict, video_type: str) -> list[str]:
    """Generate 3 bold thumbnail overlay text options (2-4 words each)."""
    texts: list[str] = []

    if flags["is_launch"]:
        texts.extend(["JUST DROPPED", f"{product.upper()} IS HERE", "FIRST LOOK"])
    if flags["is_open_source"]:
        texts.extend(["FREE AI TOOL", "OPEN SOURCE", "$0 ALTERNATIVE"])
    if flags["is_automation"]:
        texts.extend(["I BUILT THIS", "FULL AUTOMATION", "RUNS 24/7"])
    if flags["is_voice"]:
        texts.extend(["AI VOICE AGENT", "IT TALKS BACK", "LIVE DEMO"])
    if flags["is_coding_tool"]:
        texts.extend(["BUILT IN MINUTES", "NO CODE NEEDED", "MIND = BLOWN"])
    if flags["is_business"]:
        texts.extend(["$2K PER CLIENT", "SELL THIS NOW", "AI AGENCY"])
    if flags["is_model"]:
        texts.extend(["NEW MODEL DROP", "GAME CHANGER", "I TESTED IT"])

    # Ensure at least 3
    defaults = ["MUST SEE", "I TESTED IT", "FULL BREAKDOWN"]
    while len(texts) < 3:
        texts.append(defaults[len(texts) % len(defaults)])

    return texts[:3]


# ---------------------------------------------------------------------------
# Video structure
# ---------------------------------------------------------------------------

def _generate_structure(
    topic: str, product: str, flags: dict, video_type: str, summary: str,
) -> list[dict]:
    """Generate timestamped video structure with bullet points per section."""

    if video_type == "Tutorial":
        return [
            {
                "timestamp": "0:00-0:15",
                "section": "HOOK",
                "bullets": [
                    "Show the finished result — the working automation/tool on screen",
                    "One sentence: what you built and why the viewer should care",
                ],
            },
            {
                "timestamp": "0:15-1:00",
                "section": "Context",
                "bullets": [
                    f"Explain what {product} is and the problem it solves",
                    "Who this is for — beginners, agency owners, developers",
                    "Quick mention of prerequisites (accounts, API keys, etc.)",
                ],
            },
            {
                "timestamp": "1:00-7:00",
                "section": "Step-by-Step Build",
                "bullets": [
                    f"Walk through setting up {product} from scratch on screen",
                    "Show every click, every config — assume the viewer is following along",
                    "Pause at tricky parts and explain common mistakes",
                ],
            },
            {
                "timestamp": "7:00-8:00",
                "section": "Testing It Live",
                "bullets": [
                    "Run the finished build with real data, not dummy inputs",
                    "Show the actual output — prove it works",
                ],
            },
            {
                "timestamp": "8:00-9:00",
                "section": "Recap + CTA",
                "bullets": [
                    "Summarize what you built in one sentence",
                    "Suggest one extension the viewer can try on their own",
                    "CTA: subscribe, comment what they want to see next",
                ],
            },
        ]

    elif video_type == "First Look":
        return [
            {
                "timestamp": "0:00-0:15",
                "section": "HOOK",
                "bullets": [
                    f"Show {product} running — the headline feature in action",
                    "One sentence: why this launch matters right now",
                ],
            },
            {
                "timestamp": "0:15-1:00",
                "section": "Context",
                "bullets": [
                    f"What {product} is and what just changed",
                    "Show the announcement or release notes on screen",
                    "Compare briefly to what existed before",
                ],
            },
            {
                "timestamp": "1:00-7:00",
                "section": "Hands-On Demo",
                "bullets": [
                    f"Walk through the key new features of {product} one by one",
                    "Show real use cases — not just the docs, actual usage",
                    "Point out what works well and what feels rough",
                ],
            },
            {
                "timestamp": "7:00-8:00",
                "section": "Verdict",
                "bullets": [
                    "Honest take: hype or legit?",
                    "Who should try this now vs. who should wait",
                ],
            },
            {
                "timestamp": "8:00-9:00",
                "section": "Recap + CTA",
                "bullets": [
                    "One-sentence summary of the launch",
                    "Link in description to try it yourself",
                    "CTA: subscribe for first-look coverage of AI tools",
                ],
            },
        ]

    elif video_type == "Tool Showcase":
        return [
            {
                "timestamp": "0:00-0:15",
                "section": "HOOK",
                "bullets": [
                    f"Show {product} running — state what expensive tool it replaces",
                    "One line: 'This is free, open-source, and you can run it right now'",
                ],
            },
            {
                "timestamp": "0:15-1:00",
                "section": "Context",
                "bullets": [
                    f"What {product} does and why it exists",
                    "How it compares to paid alternatives",
                    "GitHub stars, community size — social proof",
                ],
            },
            {
                "timestamp": "1:00-7:00",
                "section": "Install + Build",
                "bullets": [
                    f"Clone the repo, install dependencies, first run — all on screen",
                    f"Build something real with {product}, not a toy example",
                    "Show gotchas and workarounds you discovered",
                ],
            },
            {
                "timestamp": "7:00-8:00",
                "section": "Pros and Cons",
                "bullets": [
                    "Honest assessment: what it does well, where it falls short",
                    "When to use this vs. the paid alternative",
                ],
            },
            {
                "timestamp": "8:00-9:00",
                "section": "Recap + CTA",
                "bullets": [
                    "Summarize: what it is, who it's for, and where to get it",
                    "Repo link in description",
                    "CTA: subscribe for more open-source AI tool reviews",
                ],
            },
        ]

    else:  # News Breakdown
        return [
            {
                "timestamp": "0:00-0:15",
                "section": "HOOK",
                "bullets": [
                    f"One-sentence summary: why {product} matters today",
                    "Show the source headline or tweet on screen",
                ],
            },
            {
                "timestamp": "0:15-1:00",
                "section": "Context",
                "bullets": [
                    "What happened — walk through the source material on screen",
                    f"Why this is relevant to AI builders and {product} users",
                    "Quick timeline if this is part of a bigger story",
                ],
            },
            {
                "timestamp": "1:00-7:00",
                "section": "Deep Dive",
                "bullets": [
                    f"Break down the key details of the {product} news",
                    "Show demos, screenshots, or live examples where possible",
                    "Connect this to what viewers can actually do differently now",
                ],
            },
            {
                "timestamp": "7:00-8:00",
                "section": "Your Take",
                "bullets": [
                    "Is this the real deal or overhyped?",
                    "What this means for the AI automation space specifically",
                ],
            },
            {
                "timestamp": "8:00-9:00",
                "section": "Recap + CTA",
                "bullets": [
                    "One-sentence recap of the most important takeaway",
                    "Ask viewers: what video should I make about this?",
                    "CTA: subscribe for daily AI automation news",
                ],
            },
        ]


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------

def _generate_description(
    topic: str,
    product: str,
    structure: list[dict],
    source_url: str,
    video_type: str,
) -> str:
    """Generate a YouTube description with summary, timestamps, links, and tags."""
    lines: list[str] = []

    # One-line summary
    lines.append(f"In this video I break down {product} — full {video_type.lower()} with live demo.")
    lines.append("")

    # Timestamps
    lines.append("TIMESTAMPS:")
    for section in structure:
        lines.append(f"{section['timestamp']} {section['section']}")
    lines.append("")

    # Links
    lines.append("LINKS:")
    if source_url:
        lines.append(f"Source: {source_url}")
    lines.append("My AI automation toolkit: (link)")
    lines.append("Join the community: (link)")
    lines.append("")

    # CTA
    lines.append("Subscribe for daily AI automation tutorials.")
    lines.append("")

    # Tags
    tags = ["#AI", "#AIautomation", "#AItools"]
    if product and product != "this AI tool":
        tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", product)
        tags.insert(0, tag)
    lines.append(" ".join(tags))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Talking points
# ---------------------------------------------------------------------------

def _generate_talking_points(
    topic: str, summary: str, product: str, flags: dict, video_type: str,
) -> list[str]:
    """Generate 5-7 topic-specific talking points to mention during the video."""
    text = f"{topic} {summary}".lower()
    points: list[str] = []

    # Extract every known tool mentioned
    tools_mentioned = [p for p in _KNOWN_PRODUCTS if p.lower() in text]
    if tools_mentioned:
        points.append(
            f"Mention tools by name: {', '.join(tools_mentioned)} "
            "— viewers search for these exact terms."
        )

    # Version numbers
    versions = re.findall(r'v\d+[\.\d]*', text)
    if versions:
        points.append(
            f"Call out the version ({', '.join(set(versions))}) "
            "— compare to the previous release on screen."
        )

    # Pricing / cost signals
    if any(kw in text for kw in ["free", "$", "pricing", "cost", "subscription", "plan"]):
        points.append(
            "State the pricing clearly — viewers always want to know 'is this free?' upfront."
        )

    # Open-source specifics
    if flags["is_open_source"]:
        points.append(
            "Show the GitHub repo: star count, last commit date, contributor count "
            "— this builds trust."
        )

    # API / integration specifics
    if any(kw in text for kw in ["api", "sdk", "webhook", "integration"]):
        points.append(
            "Show a real API call: request in, response out. "
            "Viewers want to see actual JSON, not slides."
        )

    # MCP specifics
    if flags["is_mcp"]:
        points.append(
            "Explain what MCP is in one sentence for new viewers, "
            "then show the server config and a live tool call."
        )

    # Voice AI specifics
    if flags["is_voice"]:
        points.append(
            "Do a live call demo on camera — voice AI videos with real audio "
            "get significantly more watch time."
        )

    # Automation specifics
    if flags["is_automation"]:
        points.append(
            "Show the full workflow: trigger, steps, output. "
            "Draw the architecture before you build it."
        )

    # Business angle
    if flags["is_business"]:
        points.append(
            "Name a specific price point you'd charge a client for this. "
            "Concrete numbers drive engagement."
        )

    # Model comparison
    if flags["is_model"]:
        points.append(
            "Run the same prompt on the old and new model side by side — "
            "show the difference, don't just talk about it."
        )

    # Coding tools
    if flags["is_coding_tool"]:
        points.append(
            "Show your actual project structure and the code it generated. "
            "Viewers want to assess real output quality."
        )

    # Generic high-value points if we're still short
    generic = [
        f"Reference the source material ({product}) on screen — "
        "builds credibility and gives viewers context.",
        "Ask a question to the audience mid-video: "
        "'Have you tried this? Drop your experience in the comments.'",
        "Mention one limitation or downside honestly — "
        "balanced takes get more trust and longer watch time.",
        "End with a specific next-step: 'Try this yourself with the link below, "
        "then tell me what happened.'",
    ]

    for g in generic:
        if len(points) >= 7:
            break
        points.append(g)

    return points[:7]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_outline(
    topic: str,
    summary: str = "",
    source_url: str = "",
    score: int = 0,
) -> dict:
    """Generate a complete YouTube video production plan from a topic string.

    Uses keyword matching to determine video type, hooks, structure, and
    talking points. No LLM API calls required.

    Args:
        topic: Article title or video idea (the main input).
        summary: Optional article summary for richer keyword extraction.
        source_url: Optional link to the source material.
        score: Optional relevance score (0-10) from the scoring pipeline.

    Returns:
        A dict with keys: hook, youtube_titles, thumbnail_texts,
        video_structure, description, talking_points, and metadata.
    """
    text = f"{topic} {summary}".lower()
    product = _extract_product_name(topic)
    video_type = _detect_video_type(text)
    flags = _detect_topic_flags(text)
    category = _categorize(text)

    hooks = _generate_hooks(topic, product, flags, video_type)
    titles = _generate_titles(topic, product, flags, video_type)
    thumbnails = _generate_thumbnail_texts(product, flags, video_type)
    structure = _generate_structure(topic, product, flags, video_type, summary)
    description = _generate_description(topic, product, structure, source_url, video_type)
    talking_points = _generate_talking_points(topic, summary, product, flags, video_type)

    return {
        "hook": hooks,
        "youtube_titles": titles,
        "thumbnail_texts": thumbnails,
        "video_structure": structure,
        "description": description,
        "talking_points": talking_points,
        "metadata": {
            "topic": topic,
            "product": product,
            "video_type": video_type,
            "category": category,
            "score": score,
            "source_url": source_url,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }


def format_outline_markdown(outline: dict) -> str:
    """Format an outline dict into clean Markdown for Obsidian or terminal display.

    Args:
        outline: The dict returned by generate_outline().

    Returns:
        A Markdown-formatted string.
    """
    meta = outline["metadata"]
    lines: list[str] = []

    # Header
    lines.append(f"# Video Outline: {meta['topic']}")
    lines.append("")
    lines.append(f"**Type:** {meta['video_type']}  ")
    lines.append(f"**Product:** {meta['product']}  ")
    if meta["category"]:
        lines.append(f"**Category:** {meta['category']}  ")
    if meta["score"]:
        lines.append(f"**Score:** {meta['score']}/10  ")
    if meta["source_url"]:
        lines.append(f"**Source:** {meta['source_url']}  ")
    lines.append(f"**Generated:** {meta['generated_at']}  ")
    lines.append("")

    # Hooks
    lines.append("## Hook Options (0:00-0:15)")
    lines.append("")
    for i, hook in enumerate(outline["hook"], 1):
        lines.append(f"{i}. \"{hook}\"")
    lines.append("")

    # YouTube Titles
    lines.append("## YouTube Title Options")
    lines.append("")
    for i, title in enumerate(outline["youtube_titles"], 1):
        char_count = len(title)
        lines.append(f"{i}. {title} ({char_count} chars)")
    lines.append("")

    # Thumbnail Text
    lines.append("## Thumbnail Text Options")
    lines.append("")
    for i, thumb in enumerate(outline["thumbnail_texts"], 1):
        lines.append(f"{i}. **{thumb}**")
    lines.append("")

    # Video Structure
    lines.append("## Video Structure")
    lines.append("")
    for section in outline["video_structure"]:
        lines.append(f"### {section['timestamp']} — {section['section']}")
        for bullet in section["bullets"]:
            lines.append(f"- {bullet}")
        lines.append("")

    # Talking Points
    lines.append("## Talking Points")
    lines.append("")
    for i, point in enumerate(outline["talking_points"], 1):
        lines.append(f"{i}. {point}")
    lines.append("")

    # Description
    lines.append("## YouTube Description")
    lines.append("")
    lines.append("```")
    lines.append(outline["description"])
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def format_outline_email(outline: dict) -> str:
    """Format an outline dict into a plain-text email body.

    Args:
        outline: The dict returned by generate_outline().

    Returns:
        A plain-text string suitable for email delivery.
    """
    meta = outline["metadata"]
    lines: list[str] = []

    # Header
    lines.append(f"VIDEO OUTLINE: {meta['topic']}")
    lines.append("=" * 60)
    lines.append(f"Type: {meta['video_type']} | Product: {meta['product']}")
    if meta["category"]:
        lines.append(f"Category: {meta['category']}")
    if meta["score"]:
        lines.append(f"Score: {meta['score']}/10")
    if meta["source_url"]:
        lines.append(f"Source: {meta['source_url']}")
    lines.append("")

    # Hooks
    lines.append("HOOK OPTIONS (pick one for the first 15 seconds):")
    lines.append("-" * 40)
    for i, hook in enumerate(outline["hook"], 1):
        lines.append(f"  {i}. \"{hook}\"")
    lines.append("")

    # YouTube Titles
    lines.append("YOUTUBE TITLES (pick one, all under 60 chars):")
    lines.append("-" * 40)
    for i, title in enumerate(outline["youtube_titles"], 1):
        lines.append(f"  {i}. {title} ({len(title)} chars)")
    lines.append("")

    # Thumbnail Text
    lines.append("THUMBNAIL TEXT (bold overlay, 2-4 words):")
    lines.append("-" * 40)
    for i, thumb in enumerate(outline["thumbnail_texts"], 1):
        lines.append(f"  {i}. {thumb}")
    lines.append("")

    # Video Structure
    lines.append("VIDEO STRUCTURE:")
    lines.append("-" * 40)
    for section in outline["video_structure"]:
        lines.append(f"  {section['timestamp']} {section['section']}")
        for bullet in section["bullets"]:
            lines.append(f"    - {bullet}")
    lines.append("")

    # Talking Points
    lines.append("TALKING POINTS (mention these during the video):")
    lines.append("-" * 40)
    for i, point in enumerate(outline["talking_points"], 1):
        lines.append(f"  {i}. {point}")
    lines.append("")

    # Description
    lines.append("YOUTUBE DESCRIPTION (copy-paste):")
    lines.append("-" * 40)
    for line in outline["description"].split("\n"):
        lines.append(f"  {line}")
    lines.append("")

    return "\n".join(lines)
