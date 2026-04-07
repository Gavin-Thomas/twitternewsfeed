"""Generate Nate Herk style video scripts — no BS, practical, show-don't-tell."""
from src.store import Article


def generate_script(article: Article) -> str:
    """Generate a short video script outline for a high-scoring article.

    Style: Nate Herk — direct, practical, screen-recording focused.
    No fluff intros, no "what's up guys", just straight to the value.
    """
    title = article.title
    summary = article.summary
    cat = article.category
    text = f"{title} {summary}".lower()

    hook = _generate_hook(title, text)
    what_it_is = _generate_context(title, summary, cat)
    demo_steps = _generate_demo_steps(title, text, cat)
    takeaway = _generate_takeaway(title, text, cat)

    lines = [
        f"📹 VIDEO: {title}",
        f"⏱ ~5-8 min | 🏷 {cat or 'GENERAL'}",
        "",
        f"HOOK (0:00):",
        f'"{hook}"',
        "",
        f"WHAT IT IS (0:15):",
        what_it_is,
        "",
        f"DEMO (1:00):",
    ]

    for i, step in enumerate(demo_steps, 1):
        lines.append(f"  {i}. {step}")

    lines.extend([
        "",
        f"TAKEAWAY:",
        takeaway,
        "",
        'CTA: "Try this yourself — link in description"',
    ])

    return "\n".join(lines)


def _generate_hook(title: str, text: str) -> str:
    """Generate the opening hook — first 15 seconds."""
    if any(kw in text for kw in ["mcp", "claude code"]):
        return f"This just dropped and it changes how you use Claude Code. Let me show you."

    if any(kw in text for kw in ["vapi", "voice agent", "voice ai", "bland ai"]):
        return "I just built a voice agent that handles calls 24/7. Here's exactly how."

    if any(kw in text for kw in ["automat", "workflow", "pipeline"]):
        return f"This automation took me 10 minutes to build and it runs on autopilot. Watch this."

    if any(kw in text for kw in ["launch", "release", "new", "announce"]):
        return f"{title.split()[0]} just shipped something big. Here's why you should care."

    if any(kw in text for kw in ["open-source", "open source", "free"]):
        return "This is free, it's open source, and it replaces tools people pay hundreds for."

    if any(kw in text for kw in ["cursor", "codex", "copilot", "windsurf"]):
        return "I built this entire thing with AI in one sitting. Let me show you the workflow."

    if any(kw in text for kw in ["agent", "chatbot"]):
        return "I'm going to show you how to build an AI agent from scratch. No fluff, just the build."

    if any(kw in text for kw in ["api", "sdk", "integration"]):
        return f"New API just dropped. Here's how to actually use it."

    return f"Let me show you something. {title}. Here's what you need to know."


def _generate_context(title: str, summary: str, cat: str) -> str:
    """Generate the 'what it is' section — 30 seconds of context."""
    if summary:
        clean = summary[:200].rstrip(".")
        return f"{clean}. Here's what that means in practice."
    return f"{title} — and I'm going to break down exactly what this means for builders."


def _generate_demo_steps(title: str, text: str, cat: str) -> list[str]:
    """Generate the demo outline — what to show on screen."""
    steps = []

    if any(kw in text for kw in ["mcp", "claude code"]):
        steps = [
            "Open Claude Code, show the current setup",
            "Install/configure the new feature",
            "Run a real task to demo the capability",
            "Show the output — what you actually get",
        ]
    elif any(kw in text for kw in ["vapi", "voice", "bland"]):
        steps = [
            "Create the voice agent (show the config)",
            "Set up the prompt/personality",
            "Wire up the phone number or webhook",
            "Make a live test call on camera",
        ]
    elif any(kw in text for kw in ["automat", "workflow", "make.com", "zapier"]):
        steps = [
            "Show the automation trigger (what kicks it off)",
            "Walk through each step in the workflow",
            "Connect the AI model (show the API call)",
            "Run it live — show real output",
        ]
    elif any(kw in text for kw in ["cursor", "codex", "copilot", "windsurf"]):
        steps = [
            "Open the IDE, show the starting point",
            "Write the prompt / give the instruction",
            "Watch the AI generate the code",
            "Run it — show it actually working",
        ]
    elif any(kw in text for kw in ["agent", "chatbot"]):
        steps = [
            "Set up the project structure",
            "Define the agent's tools and personality",
            "Build the core logic (show the code/config)",
            "Test it with real inputs",
        ]
    elif any(kw in text for kw in ["api", "sdk"]):
        steps = [
            "Get the API key / install the SDK",
            "Write the first API call",
            "Parse the response — show what you get back",
            "Build something useful with it",
        ]
    elif any(kw in text for kw in ["launch", "release", "open-source"]):
        steps = [
            "Go to the site/repo — show what's new",
            "Install it / sign up",
            "Run through the key features on screen",
            "Build a quick demo to test it",
        ]
    else:
        steps = [
            "Show the tool/feature in action",
            "Walk through the setup step by step",
            "Build something practical with it",
            "Show the final result",
        ]

    return steps


def _generate_takeaway(title: str, text: str, cat: str) -> str:
    """Generate the closing takeaway."""
    if any(kw in text for kw in ["automat", "workflow"]):
        return "This runs on autopilot once you set it up. That's the whole point."

    if any(kw in text for kw in ["agent", "chatbot", "voice"]):
        return "You now have an AI that works for you 24/7. Scale it from here."

    if any(kw in text for kw in ["open-source", "free"]):
        return "Free, open source, and you can customize it however you want."

    if any(kw in text for kw in ["api", "sdk", "mcp"]):
        return "Now you can connect this to anything. That's where it gets powerful."

    return "Try this yourself — it takes less time than you think."


def generate_scripts_for_digest(articles: list[Article], max_scripts: int = 3) -> str:
    """Generate video scripts for the top-scored articles in a digest."""
    top = [a for a in articles if a.score >= 5][:max_scripts]

    if not top:
        return ""

    parts = ["", "━━━ VIDEO SCRIPTS ━━━", ""]
    for article in top:
        parts.append(generate_script(article))
        parts.append("")

    return "\n".join(parts)
