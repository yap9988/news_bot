import feedparser
import requests
from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class FeedParser:
    def __init__(self, max_articles_per_feed: int = 10):
        self.max_articles_per_feed = max_articles_per_feed

    def parse_feed(self, feed_url: str) -> List[Dict]:
        """
        Parse a feed and return a list of articles.

        Args:
            feed_url: URL of the RSS/Atom feed

        Returns:
            List of dictionaries containing article information
        """
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url)
            source_name = getattr(feed.feed, 'title', 'Unknown Source')

            # Extract articles
            articles = []
            for entry in feed.entries[:self.max_articles_per_feed]:
                article = {
                    'title': getattr(entry, 'title', 'No title'),
                    'source': source_name,
                    'link': getattr(entry, 'link', ''),
                    'summary': getattr(entry, 'summary', ''),
                    'published': self._parse_date(getattr(entry, 'published', None))
                }
                articles.append(article)

            logger.info(f"Parsed {len(articles)} articles from {feed_url}")
            return articles

        except Exception as e:
            logger.error(f"Error parsing feed {feed_url}: {str(e)}")
            return []

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse a date string into a datetime object.

        Args:
            date_str: Date string from feed entry

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                return None

    def validate_feed(self, feed_url: str) -> bool:
        """
        Validate if a feed URL is accessible and parsable.

        Args:
            feed_url: URL of the RSS/Atom feed

        Returns:
            True if feed is valid, False otherwise
        """
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(feed_url)
            return len(feed.entries) > 0
        except Exception as e:
            logger.error(f"Feed validation failed for {feed_url}: {str(e)}")
            return False
