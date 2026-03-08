# News Bot & Strategic Dashboard

An automated news intelligence system that fetches RSS feeds, summarizes them into market logic using AI, and provides a professional dashboard for strategic tracking and tiered user access.

## 🚀 Key Features

- **Integrated Architecture:** A single process runs both the fetching bot and the web dashboard using a production-grade Waitress server.
- **Strategic AI Analysis:** Automatically deduces **Instrument**, **Cause**, and **Effect** (↑/↓) for every news item.
- **Tiered Access System:** 
  - **Admin:** Full system control, user management, and moderation.
  - **Moderator:** Can manage RSS feeds, edit/delete articles, and revive deleted records.
  - **Member Plus:** Can view full history and **Export** data to CSV/TXT.
  - **Member:** Can view full article history.
  - **Member (Inactive):** Limited to viewing the top 10 most recent articles (Default for new signups).
- **Moderation Panel:** Centralized hub for Admins/Moderators to manage RSS sources and audit soft-deleted records.
- **User Management:** Secure SHA256 password encryption with account management for Admins and self-service password changes for all users.
- **One-Table Speed:** High-performance architecture storing all data in a single optimized SQLite table.
- **Localized Experience:** Automatic timezone conversion (GMT+8) and steady AI pacing.

## 🧠 The Intelligence Pipeline

1. **Feed Management:** Admins/Moderators add RSS URLs in the Moderation Panel.
2. **AI Analysis:** Every new article is processed by Groq Cloud (Llama 3.1) to deduce market triggers.
3. **Strategic Storage:** Results are saved with an audit trail for future review or revival.

## ⚙️ Configuration

Modify `config.py` to set your `GROQ_API_KEY`, `TIMEZONE`, and server settings.

## 📥 Installation (Setup)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Usage (Run)

```bash
pip install -r requirements.txt && python3 main.py
```

### 🔗 Navigation
- **Dashboard:** Strategic board with keyboard navigation (Arrows).
- **Export:** Filtered data downloads (CSV/TXT).
- **Moderation:** Feed management and record recovery (Admin/Mod only).
- **User Action:** Dropdown menu for Password changes and Account management.

---
*License: MIT*
