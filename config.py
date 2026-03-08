import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Security
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "default-dev-key")

# Feeds to monitor
FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",   
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",   
    "https://rss.reuters.com/reuters/topNews",
    "https://seekingalpha.com/market_currents.xml"    
]

# Scheduler settings
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))

# Application settings
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", "10"))
GLOBAL_ITEMS_PER_PAGE = int(os.getenv("GLOBAL_ITEMS_PER_PAGE", "10"))

# AI Analysis settings (Groq Cloud)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_DEFAULT_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama-3.1-8b-instant")
AI_MAX_REQUESTS_PER_MINUTE = int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", "20"))

# --- Advanced AI Tuning ---
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.1"))
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
AI_CONTEXT_CHAR_LIMIT = int(os.getenv("AI_CONTEXT_CHAR_LIMIT", "600"))

# --- Server Infrastructure ---
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))
SERVER_THREADS = int(os.getenv("SERVER_THREADS", "4"))

# --- Bot Pacing ---
BOT_SLEEP_BETWEEN_ARTICLES = float(os.getenv("BOT_SLEEP_BETWEEN_ARTICLES", "2.0"))

# --- UI Experience ---
DASHBOARD_REFRESH_MS = int(os.getenv("DASHBOARD_REFRESH_MS", "30000"))
ENABLE_SOUND_ALERTS = os.getenv("ENABLE_SOUND_ALERTS", "true").lower() == "true"

# Timezone settings
TIMEZONE = os.getenv("TIMEZONE", "GMT+8")
