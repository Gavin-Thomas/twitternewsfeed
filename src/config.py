"""All configuration for the AI News Digest system."""
import os
from pathlib import Path

# --- Paths ---
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present (no external dependency)
_env_path = PROJECT_DIR / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# --- User Configuration (from .env or GitHub Secrets) ---
PHONE_NUMBER = os.environ.get("ULTRAPLAN_PHONE", "")
FALLBACK_EMAIL = os.environ.get("ULTRAPLAN_EMAIL", "")
NTFY_TOPIC = os.environ.get("ULTRAPLAN_NTFY_TOPIC", "")
RECIPIENTS = [r for r in [PHONE_NUMBER, FALLBACK_EMAIL] if r]
DB_PATH = PROJECT_DIR / "data" / "articles.db"
LOG_DIR = PROJECT_DIR / "logs"

# --- Delivery Mode ---
# "ntfy" = push notification (works from cloud / GitHub Actions)
# "imessage" = local Mac only (requires Messages.app)
# "both" = try both
DELIVERY_MODE = os.environ.get("ULTRAPLAN_DELIVERY", "both")

# --- RSS Feeds ---
# Niche: practical AI automation & tool building (Nate Herk style)
RSS_FEEDS = {
    # Tier 1: Practical builders who ship AI automations
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "LangChain Blog": "https://blog.langchain.dev/rss/",
    "Anthropic Blog": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",

    # Tier 2: Tool & model launches
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",

    # Tier 3: Broad AI news (scoring filters out fluff)
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",

    # Tier 4: Dev community tutorials
    "Dev.to AI": "https://dev.to/feed/tag/ai",
}

# --- HackerNews ---
HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_QUERIES = [
    "Claude Code",
    "Codex CLI",
    "MCP server",
    "AI automation",
    "AI agent build",
    "Vapi voice agent",
    "AI chatbot",
    "NotebookLM",
    "Cursor AI",
    "open source LLM tool",
]
HN_HITS_PER_PAGE = 20
HN_MIN_POINTS = 15

# --- GitHub Trending ---
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# --- Scoring Keywords ---
# Weighted for: "Would Nate Herk make a video about this? Can I demo it on screen?"

IMPACT_KEYWORDS = {
    # Product launches people build with
    "launches": 2, "releases": 2, "open-source": 3, "open source": 3,
    "now available": 2, "announces": 1,
    # THE tools — instant high score
    "mcp": 4, "mcp server": 4, "claude code": 4, "codex": 4,
    "vapi": 4, "voiceflow": 4, "bland ai": 4,
    "notebooklm": 3, "notebook lm": 3,
    # Integration / API signals
    "api": 2, "sdk": 2, "integration": 2, "webhook": 2, "connector": 2,
    # Business automation
    "saas": 2, "client": 2, "agency": 3, "ai agency": 4,
}

DEMO_KEYWORDS = {
    # "Can I screen-record myself building this?"
    "tutorial": 3, "how to": 3, "step by step": 3, "walkthrough": 3,
    "build": 2, "built": 2, "automate": 3, "automation": 3,
    "workflow": 3, "pipeline": 2, "template": 2,
    "agent": 3, "chatbot": 3, "voice agent": 4, "voice ai": 3,
    "no-code": 3, "low-code": 2,
    "scrape": 2, "scraping": 2, "lead gen": 3, "outreach": 2,
    "prompt": 1, "rag": 2,
}

MODEL_KEYWORDS = {
    # New models = new capabilities to demo
    "gpt-4o": 2, "gpt-5": 3, "o1": 2, "o3": 2, "o4": 3,
    "claude": 2, "claude 4": 3, "opus": 2, "sonnet": 2,
    "gemini": 2, "gemini 2": 3, "gemini flash": 2,
    "llama": 1, "deepseek": 2,
    # Coding/building tools
    "cursor": 3, "windsurf": 2, "copilot": 2, "codex": 3,
}

MAX_SCORE = 10

MIN_SCORE_TOP = 5
MIN_SCORE_NOTABLE = 3

# --- Categories ---
CATEGORIES = {
    "BUILD": [
        "automation", "workflow", "agent", "chatbot", "voice agent",
        "vapi", "voiceflow", "bland ai", "zapier", "make.com",
        "mcp", "api", "webhook", "integration", "scrape", "pipeline",
        "langchain", "llamaindex", "crewai", "autogen",
    ],
    "CLAUDE": [
        "claude", "anthropic", "mcp", "claude code", "sonnet", "opus", "haiku",
        "artifacts", "projects", "claude api",
    ],
    "TOOLS": [
        "cursor", "windsurf", "copilot", "codex", "notebooklm", "notebook lm",
        "devin", "github copilot", "aider", "continue",
    ],
    "BIZ": [
        "agency", "ai agency", "client", "saas", "revenue", "pricing",
        "monetize", "productize", "lead gen", "outreach", "freelance",
    ],
    "MODELS": [
        "gpt", "gemini", "llama", "mistral", "deepseek",
        "open-source model", "fine-tune", "weights",
    ],
    "HEALTH": [
        "healthcare", "biotech", "fda", "clinical", "medical",
        "health tech", "drug", "health ai",
    ],
}

# --- Dedup ---
DEDUP_TITLE_SIMILARITY_THRESHOLD = 0.6
RETENTION_DAYS = 30

# --- Digest ---
MAX_TOP_STORIES = 5
MAX_NOTABLE_STORIES = 5

# --- HTTP ---
REQUEST_TIMEOUT = 15
USER_AGENT = "UltraPlan-Digest/1.0"
