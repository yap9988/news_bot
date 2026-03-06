# News Bot & Strategic Dashboard

An automated news intelligence system that fetches RSS feeds, summarizes them using AI, and deduces market ripple effects for a clean, professional reading experience.

## 🚀 Key Features

- **Integrated Architecture:** A single process runs both the fetching bot and the web dashboard.
- **Evolving AI Taxonomy:** The bot "learns" from you. Standardize a `NEW:` tag in the Category Manager, and the AI automatically uses it for all future news.
- **Consolidated AI Workflow:** 
  1. **AI Digest:** Rapidly summarizes raw news into 3-bullet point reports (8B Model).
  2. **Strategic Insights:** Analyzes those summaries to deduce market effects on Forex, Commodities, and Stocks (70B Model).
- **Steady-Pace Background Processing:** To respect rate limits and ensure stability, AI tasks are throttled (one category per 60 seconds) and run in the background.
- **Clean Workspace:** Summarized articles are automatically moved to the "Removal" list to keep your daily dashboard empty and focused.
- **Auditing & History:** Check past summaries via the "Show Archived" checkbox on the AI Digest page.
- **Real-time Monitoring:** Watch progress in the terminal with `BACKGROUND: [X/X]` logging and hear "ding" alerts for new articles.

## 🧠 The Intelligence Pipeline

1. **Raw Feed:** Bot fetches headlines (BBC, Reuters, etc.).
2. **Tagging:** AI categorizes news. If it's a new topic, it suggests a `NEW: Tag`.
3. **Digest:** You click "Summarize & Purge". The dashboard clears, and clean summaries are created.
4. **Insights:** You click "Deduce Market Effects". The AI reads the summaries and predicts market impacts.

## ⚙️ Configuration

Modify `config.py` or set environment variables:

- `GROQ_API_KEY`: Your API key from [Groq Cloud](https://console.groq.com/).
- `GROQ_DEFAULT_MODEL`: Model for tagging/summaries (default: `llama-3.1-8b-instant`).
- `GROQ_INSIGHT_MODEL`: Model for deep market analysis (default: `llama-3.3-70b-versatile`).
- `AI_MAX_REQUESTS_PER_MINUTE`: Max AI calls allowed (default: `20`).
- `TIMEZONE`: Your local GMT offset (default: `GMT+8`).
- `DEFAULT_ARTICLES_PER_PAGE`: Pagination limit (default: `30`).

## 📖 Usage

Run the system:
```bash
python3 main.py
```
- **Dashboard:** `http://localhost:5000` (Raw headlines + Alerts)
- **AI Digest:** `/digest` (Cleaned summaries)
- **Strategic Insights:** `/insights` (Market impact deductions)
- **Category Manager:** `/categories` (Train your AI)

---
*License: MIT*
