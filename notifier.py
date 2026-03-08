import requests
import json
import time
import re
import logging
from typing import List, Tuple, Dict
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config):
        self.config = config
        self.request_times = deque()
        # Set a slightly lower limit to avoid boundary errors
        self.max_rpm = getattr(config, 'AI_MAX_REQUESTS_PER_MINUTE', 20) - 1
        self.default_model = getattr(config, 'GROQ_DEFAULT_MODEL', 'llama-3.1-8b-instant')

    def _wait_for_rate_limit(self):
        """Strictly ensures we don't exceed RPM and paces requests evenly."""
        if not self.max_rpm: return
        
        now = time.time()
        # Remove timestamps older than 60 seconds
        while self.request_times and self.request_times[0] < now - 60:
            self.request_times.popleft()

        if len(self.request_times) >= self.max_rpm:
            # Calculate exactly how long to wait until the oldest request falls out of the window
            wait_time = self.request_times[0] - (now - 60)
            if wait_time > 0:
                logger.info(f"Rate Limiter: Reached {self.max_rpm} RPM. Pacing for {wait_time:.2f}s...")
                time.sleep(wait_time)
                return self._wait_for_rate_limit()

        self.request_times.append(time.time())

    def analyze_article_cause_effect(self, title: str, summary: str) -> Tuple[str, str, str]:
        """High-quality Strategic Analysis prompt."""
        if not self.config.GROQ_API_KEY:
            return "ERROR", "Missing API Key", "Check config.py"

        self._wait_for_rate_limit()
        
        # Use context limit from config
        context_limit = getattr(self.config, 'AI_CONTEXT_CHAR_LIMIT', 500)
        
        # High-quality Strategist Prompt
        prompt = f"""
        Act as a Senior Global Macro Strategist. 
        Summarize the following news into professional market logic.

        News: {title}
        Context: {summary[:context_limit]}

        Rules:
        1. INSTRUMENT: Identify the specific asset affected (e.g., Gold, Oil, WTI, S&P 500, USD/JPY, Bond Yields).
        2. CAUSE: Explain the trigger concisely.
        3. EFFECT: State the asset movement using symbols ↑ or ↓ followed by brief context.

        Example Result:
        INSTRUMENT: Gold
        CAUSE: Escalating Middle East conflict and safe-haven demand
        EFFECT: Gold ↑ (Targeting new highs amid geopolitical uncertainty)

        Respond ONLY in this exact format:
        INSTRUMENT: [Asset]
        CAUSE: [Trigger]
        EFFECT: [Asset] [↑/↓] [Context]
        """

        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.config.GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": self.default_model, 
                "messages": [{"role": "user", "content": prompt}], 
                "temperature": getattr(self.config, 'AI_TEMPERATURE', 0.1)
            }
            
            timeout = getattr(self.config, 'AI_TIMEOUT_SECONDS', 25)
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            
            if response.status_code != 200:
                return "API ERROR", f"Code {response.status_code}", response.text[:100]

            text = response.json()['choices'][0]['message']['content'].strip()
            
            # Extract fields
            inst_match = re.search(r'INSTRUMENT:\s*(.*)', text, re.IGNORECASE)
            cause_match = re.search(r'CAUSE:\s*(.*)', text, re.IGNORECASE)
            effect_match = re.search(r'EFFECT:\s*(.*)', text, re.IGNORECASE)
            
            def clean(v): return re.sub(r'[\[\]]', '', v.strip()) if v else "Unknown"

            return (
                clean(inst_match.group(1)) if inst_match else "Misc",
                clean(cause_match.group(1)) if cause_match else "Unknown",
                clean(effect_match.group(1)) if effect_match else "Unknown"
            )

        except Exception as e:
            logger.error(f"Analysis Failed: {e}")
            return "FAIL", "Timeout/Error", str(e)[:50]
