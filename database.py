from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
from typing import List
import hashlib

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    source = Column(String)
    tags = Column(String)
    link = Column(String, unique=True, nullable=False)
    summary = Column(Text)
    published = Column(DateTime)
    processed = Column(Boolean, default=False)
    is_todo = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Article(title='{self.title}', link='{self.link}')>"

class Digest(Base):
    __tablename__ = 'digests'
    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False)
    summary_text = Column(Text, nullable=False)
    source_links = Column(Text)
    insight_generated = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Insight(Base):
    __tablename__ = 'insights'
    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False)
    deduction_text = Column(Text, nullable=False)
    source_titles = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Board(Base):
    __tablename__ = 'board'
    id = Column(Integer, primary_key=True)
    date = Column(String)
    cause = Column(Text)
    effect1 = Column(Text)
    effect2 = Column(Text)
    effect3 = Column(Text)
    effect4 = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Feed(Base):
    __tablename__ = 'feeds'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    last_checked = Column(DateTime)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    def __init__(self, database_url: str):
        if database_url.startswith('sqlite'):
            self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        else:
            self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)

    @property
    def session(self):
        return self.Session()

    def add_article(self, title: str, link: str, source: str = "", tags: str = "", summary: str = "", published: datetime = None):
        session = self.session
        existing = session.query(Article).filter(Article.link == link).first()
        if existing: return None
        article = Article(title=title, link=link, source=source, tags=tags, summary=summary, published=published)
        session.add(article); session.commit()
        return article

    def add_digest(self, category: str, summary_text: str, links: List[str]):
        session = self.session
        digest = Digest(category=category, summary_text=summary_text, source_links=",".join(links))
        session.add(digest); session.commit()
        return digest

    def add_insight(self, category: str, deduction_text: str, source_info: str):
        session = self.session
        insight = Insight(category=category, deduction_text=deduction_text, source_titles=source_info)
        session.add(insight); session.commit()
        return insight

    def add_board_entry(self, date: str, cause: str, e1: str, e2: str, e3: str, e4: str):
        session = self.session
        entry = Board(date=date, cause=cause, effect1=e1, effect2=e2, effect3=e3, effect4=e4)
        session.add(entry); session.commit()
        return entry

    def get_all_board_entries(self):
        return self.session.query(Board).filter(Board.is_deleted == False).order_by(Board.created_at.desc()).all()

    def update_board_entry(self, entry_id: int, data: dict):
        session = self.session
        entry = session.query(Board).filter(Board.id == entry_id).first()
        if entry:
            for key, value in data.items():
                if hasattr(entry, key): setattr(entry, key, value)
            session.commit(); return True
        return False

    def delete_board_entry(self, entry_id: int):
        session = self.session
        entry = session.query(Board).filter(Board.id == entry_id).first()
        if entry:
            entry.is_deleted = True; session.commit(); return True
        return False

    def get_recent_digests(self, limit: int = 50):
        return self.session.query(Digest).filter(Digest.is_deleted == False).order_by(Digest.created_at.desc()).limit(limit).all()

    def get_paginated_digests(self, page: int = 1, per_page: int = 10, show_archived: bool = False):
        query = self.session.query(Digest).filter(Digest.is_deleted == False)
        if not show_archived: query = query.filter(Digest.insight_generated == False)
        total = query.count()
        digests = query.order_by(Digest.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return digests, total

    def get_pending_digests(self):
        return self.session.query(Digest).filter(Digest.insight_generated == False, Digest.is_deleted == False).all()

    def mark_digest_as_insight_generated(self, digest_id: int):
        session = self.session
        digest = session.query(Digest).filter(Digest.id == digest_id).first()
        if digest:
            digest.insight_generated = True; session.commit()

    def get_recent_insights(self, limit: int = 50):
        return self.session.query(Insight).filter(Insight.is_deleted == False).order_by(Insight.created_at.desc()).limit(limit).all()

    def get_paginated_insights(self, page: int = 1, per_page: int = 10):
        query = self.session.query(Insight).filter(Insight.is_deleted == False)
        total = query.count()
        insights = query.order_by(Insight.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return insights, total

    def delete_digest(self, digest_id: int):
        session = self.session
        digest = session.query(Digest).filter(Digest.id == digest_id).first()
        if digest:
            digest.is_deleted = True; session.commit(); return True
        return False

    def delete_insight(self, insight_id: int):
        session = self.session
        insight = session.query(Insight).filter(Insight.id == insight_id).first()
        if insight:
            insight.is_deleted = True; session.commit(); return True
        return False

    def update_digest(self, digest_id: int, new_text: str):
        session = self.session
        digest = session.query(Digest).filter(Digest.id == digest_id).first()
        if digest:
            digest.summary_text = new_text; session.commit(); return True
        return False

    def update_insight(self, insight_id: int, new_text: str):
        session = self.session
        insight = session.query(Insight).filter(Insight.id == insight_id).first()
        if insight:
            insight.deduction_text = new_text; session.commit(); return True
        return False

    def get_unprocessed_articles(self):
        return self.session.query(Article).filter(Article.processed == False, Article.is_deleted == False).all()

    def get_articles_for_digest(self):
        return self.session.query(Article).filter(Article.is_deleted == False).all()

    def mark_article_as_processed(self, article_id: int, tags: str = None):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.processed = True
            if tags: article.tags = tags
            session.commit()

    def add_feed(self, url: str):
        session = self.session
        existing = session.query(Feed).filter(Feed.url == url).first()
        if not existing:
            feed = Feed(url=url); session.add(feed); session.commit()

    def get_active_feeds(self):
        return self.session.query(Feed).filter(Feed.active == True).all()

    def update_feed_last_checked(self, feed_url: str):
        session = self.session
        feed = session.query(Feed).filter(Feed.url == feed_url).first()
        if feed: feed.last_checked = datetime.utcnow(); session.commit()

    def get_recent_articles(self, limit: int = 50):
        return self.session.query(Article).filter(Article.is_deleted == False).order_by(Article.created_at.desc()).limit(limit).all()

    def get_paginated_articles(self, page: int = 1, per_page: int = 10, todo_only: bool = False):
        query = self.session.query(Article).filter(Article.is_deleted == False)
        if todo_only: query = query.filter(Article.is_todo == True)
        total = query.count()
        articles = query.order_by(Article.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return articles, total

    def get_all_feeds(self):
        return self.session.query(Feed).order_by(Feed.created_at.desc()).all()

    def get_todo_articles(self):
        return self.session.query(Article).filter(Article.is_todo == True, Article.is_deleted == False).order_by(Article.created_at.desc()).all()

    def toggle_todo(self, article_id: int):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.is_todo = not article.is_todo; session.commit(); return article.is_todo
        return None

    def delete_article(self, article_id: int):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.is_deleted = True; session.commit(); return True
        return False

    def rename_tag(self, old_tag: str, new_tag: str):
        session = self.session
        articles = session.query(Article).filter(Article.tags.like(f"%{old_tag}%")).all()
        count = 0
        for art in articles:
            if art.tags:
                tag_list = [t.strip() for t in art.tags.split(',')]
                if old_tag in tag_list:
                    new_list = [new_tag if t == old_tag else t for t in tag_list]
                    new_list = list(dict.fromkeys(new_list))
                    art.tags = ", ".join(new_list); count += 1
        session.commit(); return count

    def get_all_articles(self):
        return self.session.query(Article).filter(Article.is_deleted == False).all()

    def get_unique_standardized_tags(self):
        session = self.session
        articles = session.query(Article).filter(Article.tags != None, Article.is_deleted == False).all()
        unique_tags = set()
        for art in articles:
            if art.tags:
                tags = [t.strip() for t in art.tags.split(',')]
                for tag in tags:
                    if tag and not tag.startswith('NEW:'): unique_tags.add(tag)
        return sorted(list(unique_tags))

    def close(self):
        self.Session.remove()
