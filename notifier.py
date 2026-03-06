import smtplib
import requests
import json
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Tuple, Dict
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config):
        self.config = config
        self.ollama_url = getattr(config, 'OLLAMA_URL', 'http://localhost:11434/api/generate')
        self.request_times = deque()
        self.max_rpm = getattr(config, 'AI_MAX_REQUESTS_PER_MINUTE', 20)
        self.default_model = getattr(config, 'GROQ_DEFAULT_MODEL', 'llama-3.1-8b-instant')
        self.insight_model = getattr(config, 'GROQ_INSIGHT_MODEL', 'llama-3.3-70b-versatile')
        self.categories = [
            "War & Military Action", "International Relations", "Currency Markets (Forex)",
            "Stock Market Performance", "Safe-Haven Assets", "Inflation & Cost of Living",
            "Monetary Policy", "Economic Indicators (PMI)", "GDP & Economic Growth",
            "Commodity Prices", "Energy Sector", "Global Trade",
            "Foreign Direct Investment (FDI)", "Retail & Consumer Spending", "Labor Market & Industry"
        ]

    def set_categories(self, db_categories: List[str]):
        if db_categories:
            valid_db_tags = [t for t in db_categories if t.lower() != 'others' and not t.startswith('NEW:')]
            merged = list(set(self.categories + valid_db_tags))
            self.categories = sorted(merged)

    def _wait_for_rate_limit(self):
        if not self.max_rpm: return
        now = time.time()
        while self.request_times and self.request_times[0] < now - 60:
            self.request_times.popleft()
        if len(self.request_times) >= self.max_rpm:
            sleep_time = self.request_times[0] - (now - 60)
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                return self._wait_for_rate_limit()
        self.request_times.append(time.time())

    def get_ai_prompt(self, title: str, summary: str) -> str:
        categories_str = "\n".join([f"- {cat}" for cat in self.categories])
        return f"""
        Analyze this news article and categorize it.
        Title: {title}
        Summary: {summary}

        Categorize the news into one or more of these categories:
        {categories_str}
        
        CRITICAL RULES:
        1. If it fits any category above, use the exact name.
        2. If it does NOT fit any, you MUST suggest a NEW concise name (1-3 words) that best describes the article.
        3. MANDATORY: Format suggestions as "NEW: Your Suggested Category".
        4. STRICTLY FORBIDDEN: Do NOT use the word "Others" or "Uncategorized". Always be specific.
        
        Respond ONLY in this exact format:
        TAGS: [Comma-separated categories or NEW: Suggestion]
        """

    def parse_ai_response(self, response_text: str) -> Tuple[bool, str]:
        tags_str = "Uncategorized"
        try:
            lines = response_text.strip().split('\n')
            for line in lines:
                if "TAGS:" in line.upper(): 
                    tags_str = line.split(':', 1)[1].strip()
            processed_tags = []
            for tag in [t.strip() for t in tags_str.split(',')]:
                if tag.lower() == 'others': continue
                match = re.match(r'Others\s*\((.*)\)', tag, re.IGNORECASE)
                if match: processed_tags.append(f"NEW: {match.group(1).strip()}")
                else: processed_tags.append(tag)
            final_tags = ", ".join(processed_tags) if processed_tags else "NEW: General News"
            return True, final_tags
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return True, "NEW: Pending Review"

    def summarize_category(self, category: str, articles: List[Dict]) -> str:
        if not articles: return ""
        self._wait_for_rate_limit()
        titles_list = "\n".join([f"- {a['title']}" for a in articles])
        prompt = f"Write a concise executive summary for news in category: {category}\n\nArticles:\n{titles_list}\n\nInstructions:\n1. Provide exactly 3 clear bullet points.\n2. Focus on the most important developments.\n3. Do NOT include intro/outro text."
        
        if self.config.GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.config.GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": self.default_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content'].strip()
            except Exception as e:
                logger.error(f"Groq summary failed: {str(e)}")
        return "Summary unavailable."

    def generate_market_insight(self, category: str, summary_text: str) -> str:
        """Deduce market implications from a CONSOLIDATED SUMMARY (Digest)."""
        if not summary_text: return ""
        self._wait_for_rate_limit()
        
        prompt = f"""
        Act as a senior Global Macro Strategist and Financial Analyst.
        Analyze the following Executive Summary of news under the category: {category}

        Executive Summary:
        {summary_text}

        Task: Based on these events, deduce the 'Ripple Effects' on global markets.
        Provide your analysis in exactly this format:
        
        ### MARKET DEDUCTIONS:
        - **Asset Class (e.g. Oil, Gold, USD/JPY):** Predicted movement and specific reasoning.
        - **Asset Class:** Predicted movement and reasoning.
        
        ### SENTIMENT:
        - Overall market tone (Risk-On, Risk-Off, or Neutral).
        """

        if self.config.GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.config.GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": self.insight_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.5}
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content'].strip()
            except Exception as e:
                logger.error(f"Groq insight failed: {str(e)}")
        return "Insight generation failed."

    def analyze_article(self, title: str, summary: str) -> Tuple[bool, str]:
        if not self.config.AI_ENABLED: return True, "Uncategorized"
        self._wait_for_rate_limit()
        prompt = self.get_ai_prompt(title, summary)
        if self.config.GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.config.GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": self.default_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                response.raise_for_status()
                return self.parse_ai_response(response.json()['choices'][0]['message']['content'])
            except Exception as e:
                logger.error(f"Groq tagging failed: {str(e)}")
                if not self.config.AI_FALLBACK_ENABLED: raise
        if self.config.AI_FALLBACK_ENABLED:
            try:
                payload = {"model": "llama3", "prompt": prompt, "stream": False}
                response = requests.post(self.ollama_url, json=payload, timeout=30)
                response.raise_for_status()
                return self.parse_ai_response(response.json().get('response', ''))
            except Exception as e:
                logger.error(f"Ollama fallback failed: {str(e)}")
                raise
        raise Exception("AI Analysis failed")

    def send_email_notification(self, subject: str, body: str) -> bool:
        if not self.config.EMAIL_ENABLED: return False
        try:
            msg = MIMEMultipart(); msg['From'] = self.config.EMAIL_USER; msg['To'] = self.config.EMAIL_RECIPIENT; msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(self.config.EMAIL_HOST, self.config.EMAIL_PORT); server.starttls(); server.login(self.config.EMAIL_USER, self.config.EMAIL_PASSWORD); server.sendmail(self.config.EMAIL_USER, self.config.EMAIL_RECIPIENT, msg.as_string()); server.quit()
            return True
        except Exception: return False

    def send_discord_notification(self, title: str, link: str, tags: str = "", summary: str = "") -> bool:
        if not self.config.DISCORD_ENABLED: return False
        try:
            data = {"embeds": [{"title": title, "url": link, "description": f"**Tags:** {tags}\n\n{summary[:4000]}" if summary else f"Tags: {tags}", "color": 0x00ff00, "timestamp": datetime.utcnow().isoformat() + "Z"}]}
            requests.post(self.config.DISCORD_WEBHOOK_URL, json=data).raise_for_status()
            return True
        except Exception: return False

    def send_notifications(self, articles: List[dict]) -> None:
        pass
