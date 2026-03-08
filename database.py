from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
import hashlib

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    source = Column(String)
    link = Column(String, unique=True, nullable=False)
    summary = Column(Text)
    published = Column(DateTime)
    
    # Processed Data
    processed = Column(Boolean, default=False)
    instruments = Column(String)
    cause = Column(Text)
    effect = Column(Text)
    
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Article(title='{self.title}', link='{self.link}')>"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    password_hash = Column(String, nullable=False)
    # Group names: admin, moderator, member_plus, member, member_inactive
    group_name = Column(String, default='member_inactive') 
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

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

    # --- User Management ---
    def add_user(self, username, password, email=None, group='member_inactive'):
        session = self.session
        existing = session.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing: return None
        new_user = User(username=username, email=email, password_hash=User.hash_password(password), group_name=group)
        session.add(new_user); session.commit()
        return new_user

    def authenticate_user(self, username, password):
        user = self.session.query(User).filter(User.username == username, User.is_deleted == False).first()
        if user and user.check_password(password):
            return user
        return None

    def change_password(self, user_id, new_password):
        session = self.session
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = User.hash_password(new_password)
            session.commit(); return True
        return False

    def get_all_users(self):
        return self.session.query(User).filter(User.is_deleted == False).all()

    def update_user_group(self, user_id, new_group):
        session = self.session
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.group_name = new_group
            session.commit(); return True
        return False

    def delete_user(self, user_id):
        session = self.session
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_deleted = True
            session.commit(); return True
        return False

    # --- Article Management ---
    def add_article(self, title: str, link: str, source: str = "", summary: str = "", published: datetime = None):
        session = self.session
        existing = session.query(Article).filter(Article.link == link).first()
        if existing: return None
        article = Article(title=title, link=link, source=source, summary=summary, published=published)
        session.add(article); session.commit()
        return article

    def mark_article_as_processed(self, article_id: int, instruments: str, cause: str, effect: str):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.processed = True
            article.instruments = instruments
            article.cause = cause
            article.effect = effect
            session.commit(); return True
        return False

    def update_article_analysis(self, article_id: int, data: dict):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            if 'instruments' in data: article.instruments = data['instruments']
            if 'cause' in data: article.cause = data['cause']
            if 'effect' in data: article.effect = data['effect']
            session.commit(); return True
        return False

    def delete_article(self, article_id: int):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.is_deleted = True; session.commit(); return True
        return False

    def revive_article(self, article_id: int):
        session = self.session
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.is_deleted = False
            session.commit(); return True
        return False

    def get_unprocessed_articles(self):
        return self.session.query(Article).filter(Article.processed == False, Article.is_deleted == False).all()

    def get_paginated_articles(self, page: int = 1, per_page: int = 10, deleted_only: bool = False, limit_to_10: bool = False):
        query = self.session.query(Article).filter(Article.is_deleted == deleted_only)
        if limit_to_10:
            results = query.order_by(Article.created_at.desc()).limit(10).all()
            return results, 10
        total = query.count()
        results = query.order_by(Article.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return results, total

    # --- Feed Management ---
    def add_feed(self, url: str):
        session = self.session
        existing = session.query(Feed).filter(Feed.url == url).first()
        if not existing:
            feed = Feed(url=url); session.add(feed); session.commit()
            return feed
        return existing

    def toggle_feed(self, feed_id: int):
        session = self.session
        feed = session.query(Feed).filter(Feed.id == feed_id).first()
        if feed:
            feed.active = not feed.active
            session.commit()
            return feed.active
        return None

    def delete_feed(self, feed_id: int):
        session = self.session
        feed = session.query(Feed).filter(Feed.id == feed_id).first()
        if feed:
            session.delete(feed)
            session.commit()
            return True
        return False

    def get_active_feeds(self):
        return self.session.query(Feed).filter(Feed.active == True).all()

    def get_all_feeds(self):
        return self.session.query(Feed).order_by(Feed.created_at.desc()).all()

    def update_feed_last_checked(self, feed_url: str):
        session = self.session
        feed = session.query(Feed).filter(Feed.url == feed_url).first()
        if feed: feed.last_checked = datetime.utcnow(); session.commit()

    def get_all_articles(self):
        return self.session.query(Article).filter(Article.is_deleted == False).all()

    def close(self):
        self.Session.remove()
