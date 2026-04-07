"""All configuration for the AI News Digest system."""
from pathlib import Path

# --- User Configuration ---
PHONE_NUMBER = "REDACTED"
FALLBACK_EMAIL = "REDACTED"

# --- Paths ---
PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "data" / "articles.db"
LOG_DIR = PROJECT_DIR / "logs"

# --- RSS Feeds ---
RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "Anthropic Blog": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",
}

# --- HackerNews ---
HN_API_URL = "https://hn.algolia.com/api/v1/search"
HN_QUERIES = ["AI LLM", "artificial intelligence", "Claude Anthropic", "GPT OpenAI"]
HN_HITS_PER_PAGE = 30
HN_MIN_POINTS = 50

# --- GitHub Trending ---
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# --- Scoring Keywords ---
IMPACT_KEYWORDS = {
    "launches": 3, "releases": 3, "open-source": 3, "open source": 3,
    "billion": 2, "funding": 2, "raises": 2, "acquisition": 2,
    "breakthrough": 3, "state-of-the-art": 2, "sota": 2,
    "api": 1, "sdk": 1, "benchmark": 1,
}

DEMO_KEYWORDS = {
    "tool": 2, "build": 1, "workflow": 2, "automation": 2,
    "agent": 2, "no-code": 2, "tutorial": 1, "how to": 1,
    "framework": 2, "library": 1, "plugin": 1, "extension": 1,
}

MODEL_KEYWORDS = {
    "gpt": 1, "gpt-4": 2, "gpt-5": 3, "o1": 2, "o3": 2,
    "claude": 2, "opus": 2, "sonnet": 1, "haiku": 1,
    "gemini": 2, "llama": 2, "mistral": 1, "deepseek": 2,
    "phi": 1, "qwen": 1,
}

MAX_SCORE = 10

MIN_SCORE_TOP = 6
MIN_SCORE_NOTABLE = 3

# --- Categories ---
CATEGORIES = {
    "AI-AUTO": ["automation", "workflow", "agent", "tool", "api", "no-code", "sdk", "framework", "mcp"],
    "CLAUDE": ["claude", "anthropic", "mcp", "claude code", "sonnet", "opus", "haiku"],
    "HEALTH": ["healthcare", "biotech", "fda", "clinical", "medical", "health tech", "drug", "alphafold"],
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
