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

# --- User Configuration (from .env) ---
PHONE_NUMBER = os.environ.get("ULTRAPLAN_PHONE", "")
FALLBACK_EMAIL = os.environ.get("ULTRAPLAN_EMAIL", "")
RECIPIENTS = [r for r in [PHONE_NUMBER, FALLBACK_EMAIL] if r]
DB_PATH = PROJECT_DIR / "data" / "articles.db"
LOG_DIR = PROJECT_DIR / "logs"

# --- RSS Feeds ---
# Practical AI automation, tools, and implementation — not generic news
RSS_FEEDS = {
    # Tier 1: Practical AI builders & automation
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "LangChain Blog": "https://blog.langchain.dev/rss/",
    "Anthropic Blog": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",

    # Tier 2: Major AI news (filtered by scoring to practical stuff)
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",

    # Tier 3: Google/Gemini ecosystem
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
}

# --- HackerNews ---
HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"  # search_by_date = recent first
HN_QUERIES = [
    "Claude Code",
    "MCP server",
    "AI automation",
    "AI agent workflow",
    "NotebookLM",
    "Gemini API",
    "LLM tool",
]
HN_HITS_PER_PAGE = 20
HN_MIN_POINTS = 20  # Lower bar since we're filtering by recency now

# --- GitHub Trending ---
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# --- Scoring Keywords ---
# Weighted for "can I make a video showing how to DO this?"

IMPACT_KEYWORDS = {
    # Product launches & releases
    "launches": 3, "releases": 3, "announces": 2, "introduces": 2,
    "open-source": 3, "open source": 3, "now available": 2,
    # Practical automation signals
    "mcp": 4, "mcp server": 4, "claude code": 4, "notebooklm": 4,
    "n8n": 3, "make.com": 3, "zapier": 2, "shortcuts": 2,
    "api": 2, "sdk": 2, "integration": 2, "connector": 2,
}

DEMO_KEYWORDS = {
    # "Can I show this on screen?"
    "tutorial": 3, "how to": 3, "step by step": 3, "walkthrough": 3,
    "build": 2, "built": 2, "automate": 3, "automation": 3,
    "workflow": 3, "pipeline": 2, "template": 2,
    "tool": 2, "agent": 3, "no-code": 3, "low-code": 2,
    "framework": 2, "library": 2, "plugin": 2, "extension": 2,
    "prompt": 2, "chain": 2, "rag": 2, "fine-tune": 2,
}

MODEL_KEYWORDS = {
    # New models = instant video topic
    "gpt-4o": 2, "gpt-5": 3, "o1": 2, "o3": 2, "o4": 3,
    "claude": 2, "claude 4": 3, "opus": 2, "sonnet": 2, "haiku": 1,
    "gemini": 2, "gemini 2": 3, "gemini flash": 2,
    "llama": 2, "llama 4": 3, "mistral": 1, "deepseek": 2,
    "cursor": 3, "windsurf": 2, "copilot": 2, "devin": 2,
}

MAX_SCORE = 10

MIN_SCORE_TOP = 5      # Lowered — more practical content hits top
MIN_SCORE_NOTABLE = 3

# --- Categories ---
CATEGORIES = {
    "AI-AUTO": [
        "automation", "workflow", "agent", "tool", "api", "no-code", "sdk",
        "framework", "mcp", "n8n", "make.com", "zapier", "pipeline",
        "langchain", "llamaindex", "crewai", "autogen",
    ],
    "CLAUDE": [
        "claude", "anthropic", "mcp", "claude code", "sonnet", "opus", "haiku",
        "artifacts", "projects", "claude api",
    ],
    "TOOLS": [
        "cursor", "windsurf", "copilot", "notebooklm", "notebook lm",
        "replit", "v0", "bolt", "lovable", "devin",
    ],
    "MODELS": [
        "gpt", "gemini", "llama", "mistral", "deepseek", "phi", "qwen",
        "open-source model", "fine-tune", "weights", "benchmark",
    ],
    "HEALTH": [
        "healthcare", "biotech", "fda", "clinical", "medical",
        "health tech", "drug", "alphafold", "health ai",
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
