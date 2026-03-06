import os
from typing import List

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///news_bot.db")

# Feeds to monitor
FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rss.reuters.com/reuters/topNews",
    "https://seekingalpha.com/market_currents.xml"
]

# Notification settings
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

DISCORD_ENABLED = os.getenv("DISCORD_ENABLED", "false").lower() == "true"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Scheduler settings
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))

# Application settings
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", "10"))
DEFAULT_ARTICLES_PER_PAGE = int(os.getenv("DEFAULT_ARTICLES_PER_PAGE", "30"))

# AI Analysis settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_MAX_REQUESTS_PER_MINUTE = int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", "20"))
AI_FALLBACK_ENABLED = os.getenv("AI_FALLBACK_ENABLED", "false").lower() == "true"

# Groq Model settings
GROQ_DEFAULT_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama-3.1-8b-instant")
GROQ_INSIGHT_MODEL = os.getenv("GROQ_INSIGHT_MODEL", "llama-3.3-70b-versatile")

# Display settings
GLOBAL_ITEMS_PER_PAGE = int(os.getenv("GLOBAL_ITEMS_PER_PAGE", "10"))

# Timezone settings
TIMEZONE = os.getenv("TIMEZONE", "GMT+8")
