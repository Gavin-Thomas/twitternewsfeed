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
# High-signal only: official blogs + practical builders
RSS_FEEDS = {
    # Tier 1: Practical builders who ship AI automations
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "LangChain Blog": "https://blog.langchain.dev/rss/",
    "Anthropic Blog": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",

    # Tier 2: Major lab announcements
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "OpenAI News": "https://openai.com/news/rss.xml",
}

# --- Reddit (free JSON API, no auth) ---
REDDIT_SUBS = ["LocalLLaMA", "ClaudeAI", "ChatGPT", "artificial"]
REDDIT_MIN_SCORE = 50
REDDIT_MIN_UPVOTE_RATIO = 0.7
REDDIT_LIMIT = 25  # posts per sub

# --- GitHub Releases API (free, no auth, 60 req/hr) ---
GITHUB_RELEASE_REPOS = [
    "anthropics/claude-code",
    "openai/codex",
    "langchain-ai/langchain",
    "microsoft/autogen",
    "crewAIInc/crewAI",
    "n8n-io/n8n",
]
GITHUB_RELEASE_MAX_AGE_HOURS = 48

# --- HackerNews ---
HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_QUERIES = [
    "Claude Code",
    "MCP server",
    "AI agent",
    "AI launch",
    "open source LLM",
]
HN_HITS_PER_PAGE = 20
HN_MIN_POINTS = 100

# --- GitHub Trending ---
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# --- Scoring: Launch Detection ---
# Strong signals that something NEW just shipped
LAUNCH_KEYWORDS = {
    "introducing": 3, "announcing": 3, "just shipped": 3,
    "now available": 3, "launches": 3, "just released": 3,
    "just launched": 3, "releasing": 2, "released": 2, "releases": 2,
    "unveiled": 2, "debut": 2, "beta": 2, "v2": 2, "v3": 2, "v4": 2,
}
LAUNCH_MAX = 4

# Weak launch signals
WEAK_LAUNCH_KEYWORDS = {
    "new feature": 1, "update": 1, "rollout": 1,
    "new version": 1, "ships": 1,
}
WEAK_LAUNCH_MAX = 2

# --- Scoring: Tool Relevance ---
TOOL_KEYWORDS = {
    # Core tools (instant high relevance)
    "mcp": 2, "mcp server": 2, "claude code": 2,
    "vapi": 2, "voiceflow": 2, "bland ai": 2,
    "n8n": 2, "make.com": 2,
    # Ecosystem
    "cursor": 1, "windsurf": 1, "copilot": 1,
    "langchain": 1, "crewai": 1, "autogen": 1,
    "agent": 1, "chatbot": 1, "voice agent": 2,
    "ai agency": 2, "agency": 1,
    # Models (new model = new capabilities to demo)
    "gpt": 1, "claude": 1, "gemini": 1, "llama": 1, "deepseek": 1,
    # Integration signals
    "api": 1, "sdk": 1, "webhook": 1, "open-source": 1, "open source": 1,
}
TOOL_MAX = 3

# --- Scoring: Demo-ability ---
DEMO_KEYWORDS = {
    "tutorial": 1, "how to": 1, "build": 1, "walkthrough": 1,
    "step by step": 1, "automate": 1, "automation": 1,
    "workflow": 1, "template": 1, "no-code": 1,
}
DEMO_MAX = 2

# --- Scoring: Anti-signals (penalties) ---
ANTI_SIGNAL_KEYWORDS = {
    # Bugs/outages
    "bug": 3, "broken": 3, "locked out": 3, "locking out": 3,
    "crash": 3, "not working": 3, "outage": 3,
    # Legal/drama/gossip (not video-worthy)
    "lawsuit": 3, "sued": 3, "abuse": 4, "sexual": 4,
    "accusing": 3, "scandal": 3, "fired": 2,
    "dies": 2, "death": 2, "suicide": 4,
}

OPINION_KEYWORDS = {
    "thoughts on": 2, "opinion": 2, "why i think": 2,
    "controversial": 2, "debate": 2, "rant": 2,
    "unpopular opinion": 2, "hot take": 2,
}

# Meme/joke signals — high-upvote Reddit fluff that isn't actionable
MEME_KEYWORDS = {
    "meme": 3, "shitpost": 3, "lmao": 2, "lol": 2,
    "saving my life": 2, "accidentally": 2, "whip": 2,
    "roasted": 2, "rant": 2, "humor": 2,
}

# --- Scoring: Freshness (hours -> multiplier) ---
# (max_hours, multiplier) — checked in order, first match wins
FRESHNESS_BRACKETS = [
    (12, 1.3),
    (24, 1.1),
    (72, 1.0),    # 1-3 days
    (168, 0.7),   # 3-7 days
    (None, 0.4),  # older
]

# --- Scoring: Source Authority ---
SOURCE_AUTHORITY = {
    "Anthropic Blog": 1.3,
    "OpenAI News": 1.3,
    "LangChain Blog": 1.2,
    "Google AI Blog": 1.2,
    "Simon Willison": 1.2,
    "GitHub Release": 1.3,
    "GitHub": 1.1,
    "HackerNews": 1.0,   # boosted separately by points
    "Reddit": 1.1,
}
SOURCE_AUTHORITY_DEFAULT = 1.0

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
