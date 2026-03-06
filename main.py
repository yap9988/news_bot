import logging
import re
import time
import threading
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, jsonify, request

import config
from database import DatabaseManager
from feed_parser import FeedParser
from notifier import Notifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flags for background tasks
is_generating_digest = False
is_generating_insights = False

# --- Timezone Helpers ---
def get_timezone_offset():
    tz_str = config.TIMEZONE.upper()
    match = re.match(r'GMT([+-])(\d+)', tz_str)
    if match:
        sign = 1 if match.group(1) == '+' else -1
        hours = int(match.group(2))
        return timezone(timedelta(hours=sign * hours))
    return timezone.utc

def format_local_time(dt):
    if not dt: return None
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(get_timezone_offset())
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
db_manager_web = DatabaseManager(config.DATABASE_URL)

@app.teardown_appcontext
def close_db(error):
    db_manager_web.close()

# --- Web Routes ---
@app.route('/')
def index(): return render_template('index.html', timezone=config.TIMEZONE)

@app.route('/todo')
def todo_page(): return render_template('todo.html', timezone=config.TIMEZONE)

@app.route('/removal')
def removal_page(): return render_template('removal.html', timezone=config.TIMEZONE)

@app.route('/categories')
def categories_page(): return render_template('categories.html', timezone=config.TIMEZONE)

@app.route('/digest')
def digest_page(): return render_template('digest.html', timezone=config.TIMEZONE)

@app.route('/insights')
def insights_page(): return render_template('insights.html', timezone=config.TIMEZONE)

@app.route('/board')
def board_page(): return render_template('board.html', timezone=config.TIMEZONE)

# --- API Endpoints ---
@app.route('/api/articles')
def get_articles():
    try:
        page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', config.GLOBAL_ITEMS_PER_PAGE, type=int)
        articles, total = db_manager_web.get_paginated_articles(page=page, per_page=per_page)
        articles_list = [{'id': a.id, 'title': a.title, 'source': a.source, 'tags': a.tags, 'link': a.link, 'summary': a.summary, 'published': format_local_time(a.published), 'processed': bool(a.processed), 'is_todo': bool(a.is_todo), 'created_at': format_local_time(a.created_at)} for a in articles]
        return jsonify({'articles': articles_list, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/todo')
def get_todo_articles():
    try:
        page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', config.GLOBAL_ITEMS_PER_PAGE, type=int)
        articles, total = db_manager_web.get_paginated_articles(page=page, per_page=per_page, todo_only=True)
        articles_list = [{'id': a.id, 'title': a.title, 'source': a.source, 'tags': a.tags, 'link': a.link, 'summary': a.summary, 'published': format_local_time(a.published), 'processed': bool(a.processed), 'is_todo': True, 'created_at': format_local_time(a.created_at)} for a in articles]
        return jsonify({'articles': articles_list, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/tags')
def get_tags_stats():
    try:
        articles = db_manager_web.get_all_articles(); tag_counts = {}
        for art in articles:
            if art.tags:
                for t in [t.strip() for t in art.tags.split(',') if t.strip()]: tag_counts[t] = tag_counts.get(t, 0) + 1
        stats = sorted([{'name': tag, 'count': count} for tag, count in tag_counts.items()], key=lambda x: x['count'], reverse=True)
        return jsonify(stats)
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/tags/rename', methods=['POST'])
def rename_tag():
    try:
        data = request.json; old_tag = data.get('old_tag'); new_tag = data.get('new_tag')
        if not old_tag or not new_tag: return jsonify({'error': 'Missing tag names'}), 400
        count = db_manager_web.rename_tag(old_tag, new_tag)
        return jsonify({'success': True, 'affected': count})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- Board API ---
@app.route('/api/board')
def get_board():
    try:
        entries = db_manager_web.get_all_board_entries()
        return jsonify([{
            'id': e.id, 'date': e.date, 'cause': e.cause,
            'effect1': e.effect1, 'effect2': e.effect2,
            'effect3': e.effect3, 'effect4': e.effect4,
            'created_at': format_local_time(e.created_at)
        } for e in entries])
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/board/add', methods=['POST'])
def add_board():
    try:
        data = request.json
        db_manager_web.add_board_entry(
            data.get('date'), data.get('cause'),
            data.get('effect1'), data.get('effect2'),
            data.get('effect3'), data.get('effect4')
        )
        return jsonify({'success': True})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/board/update/<int:entry_id>', methods=['POST'])
def update_board(entry_id):
    try:
        success = db_manager_web.update_board_entry(entry_id, request.json)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/board/delete/<int:entry_id>', methods=['DELETE'])
def delete_board(entry_id):
    try:
        success = db_manager_web.delete_board_entry(entry_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- Digest Logic ---
def run_background_digest():
    global is_generating_digest; is_generating_digest = True
    db_manager = DatabaseManager(config.DATABASE_URL); notifier = Notifier(config)
    try:
        articles = db_manager.get_articles_for_digest()
        if not articles: return
        grouped = {}
        for art in articles:
            tag = art.tags.split(',')[0].strip() if art.tags else "Others"
            if tag not in grouped: grouped[tag] = []
            grouped[tag].append(art)
        categories_to_process = sorted(list(grouped.keys()))
        total_cats = len(categories_to_process)
        for index, tag in enumerate(categories_to_process):
            art_list = grouped[tag]
            logger.info(f"BACKGROUND: [{index+1}/{total_cats}] Processing category: {tag} ({len(art_list)} articles)")
            art_dicts = [{'title': a.title, 'summary': a.summary} for a in art_list]
            summary_text = notifier.summarize_category(tag, art_dicts)
            if summary_text and "unavailable" not in summary_text and "failed" not in summary_text:
                db_manager.add_digest(tag, summary_text, [a.link for a in art_list])
                for a in art_list: db_manager.delete_article(a.id)
            if index < total_cats - 1: time.sleep(60)
    except Exception as e: logger.error(f"Digest error: {e}")
    finally: db_manager.close(); is_generating_digest = False

@app.route('/api/digest/generate', methods=['POST'])
def start_digest_process():
    global is_generating_digest
    if is_generating_digest: return jsonify({'error': 'Busy'}), 400
    threading.Thread(target=run_background_digest).start()
    return jsonify({'success': True, 'message': 'AI Digest started.'})

@app.route('/api/digest/status')
def get_digest_status(): return jsonify({'is_generating': is_generating_digest})

@app.route('/api/digest/recent')
def get_digests():
    try:
        page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', config.GLOBAL_ITEMS_PER_PAGE, type=int)
        show_archived = request.args.get('show_archived', 'false').lower() == 'true'
        digests, total = db_manager_web.get_paginated_digests(page=page, per_page=per_page, show_archived=show_archived)
        digest_list = [{'id': d.id, 'category': d.category, 'summary_text': d.summary_text, 'source_links': d.source_links.split(',') if d.source_links else [], 'insight_generated': bool(d.insight_generated), 'created_at': format_local_time(d.created_at)} for d in digests]
        return jsonify({'digests': digest_list, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/digest/update/<int:digest_id>', methods=['POST'])
def update_digest(digest_id):
    try:
        success = db_manager_web.update_digest(digest_id, request.json.get('summary_text'))
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/digest/delete/<int:digest_id>', methods=['DELETE'])
def delete_digest(digest_id):
    try:
        success = db_manager_web.delete_digest(digest_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- Throttled Background Insights ---
def run_background_insights():
    global is_generating_insights; is_generating_insights = True
    db_manager = DatabaseManager(config.DATABASE_URL); notifier = Notifier(config)
    try:
        digests = db_manager.get_pending_digests()
        if not digests: return
        total_digests = len(digests)
        for index, d in enumerate(digests):
            logger.info(f"BACKGROUND: [{index+1}/{total_digests}] Deducing market effects for: {d.category}")
            deduction = notifier.generate_market_insight(d.category, d.summary_text)
            if deduction and "failed" not in deduction:
                db_manager.add_insight(d.category, deduction, f"Based on Digest #{d.id}")
                db_manager.mark_digest_as_insight_generated(d.id)
            if index < total_digests - 1: time.sleep(60)
    except Exception as e: logger.error(f"Insight error: {e}")
    finally: db_manager.close(); is_generating_insights = False

@app.route('/api/insight/generate', methods=['POST'])
def start_insight_process():
    global is_generating_insights
    if is_generating_insights: return jsonify({'error': 'Busy'}), 400
    threading.Thread(target=run_background_insights).start()
    return jsonify({'success': True, 'message': 'Strategic Insight process started.'})

@app.route('/api/insight/status')
def get_insight_status(): return jsonify({'is_generating': is_generating_insights})

@app.route('/api/insight/recent')
def get_insights():
    try:
        page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', config.GLOBAL_ITEMS_PER_PAGE, type=int)
        insights, total = db_manager_web.get_paginated_insights(page=page, per_page=per_page)
        insight_list = [{'id': i.id, 'category': i.category, 'deduction_text': i.deduction_text, 'source_titles': i.source_titles.split(' | ') if i.source_titles else [], 'created_at': format_local_time(i.created_at)} for i in insights]
        return jsonify({'insights': insight_list, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/insight/update/<int:insight_id>', methods=['POST'])
def update_insight(insight_id):
    try:
        success = db_manager_web.update_insight(insight_id, request.json.get('deduction_text'))
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/insight/delete/<int:insight_id>', methods=['DELETE'])
def delete_insight(insight_id):
    try:
        success = db_manager_web.delete_insight(insight_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- General Logic ---
@app.route('/api/todo/toggle/<int:article_id>', methods=['POST'])
def toggle_todo(article_id):
    try:
        new_status = db_manager_web.toggle_todo(article_id)
        return jsonify({'id': article_id, 'is_todo': new_status})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/articles/delete/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    try:
        success = db_manager_web.delete_article(article_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/feeds')
def get_feeds():
    try:
        feeds = db_manager_web.get_all_feeds()
        return jsonify([{'id': f.id, 'url': f.url, 'last_checked': format_local_time(f.last_checked), 'active': bool(f.active), 'created_at': format_local_time(f.created_at)} for f in feeds])
    except Exception as e: return jsonify({'error': str(e)}), 500

def process_feed(feed_url: str, db_manager: DatabaseManager, feed_parser: FeedParser, notifier: Notifier):
    articles = feed_parser.parse_feed(feed_url)
    for article in articles:
        db_manager.add_article(title=article['title'], link=article['link'], source=article['source'], summary=article['summary'], published=article['published'])
    db_manager.update_feed_last_checked(feed_url)

def process_pending_articles(db_manager: DatabaseManager, notifier: Notifier):
    pending = db_manager.get_unprocessed_articles()
    if not pending: return
    db_tags = db_manager.get_unique_standardized_tags(); notifier.set_categories(db_tags)
    for art in pending:
        try:
            is_significant, tags = notifier.analyze_article(art.title, art.summary)
            if is_significant:
                notifier.send_discord_notification(art.title, art.link, tags, art.summary)
                if config.EMAIL_ENABLED:
                    subject = f"Significant News [{tags}]: {art.title}"
                    body = f"Source: {art.source}\nTags: {tags}\nLink: {art.link}\n\nSummary:\n{art.summary}"
                    notifier.send_email_notification(subject, body)
            db_manager.mark_article_as_processed(art.id, tags=tags)
        except Exception as e: logger.error(f"Failed to analyze article '{art.title}': {e}")

def process_all_feeds():
    db_manager = DatabaseManager(config.DATABASE_URL); feed_parser = FeedParser(config.MAX_ARTICLES_PER_FEED); notifier = Notifier(config)
    try:
        for feed_url in config.FEEDS: db_manager.add_feed(feed_url)
        db_feeds = db_manager.get_all_feeds()
        for df in db_feeds:
            session = db_manager.session
            feed = session.query(df.__class__).filter(df.__class__.id == df.id).first()
            if feed: feed.active = (df.url in config.FEEDS); session.commit()
        active_feeds = db_manager.get_active_feeds()
        for feed in active_feeds:
            try: process_feed(feed.url, db_manager, feed_parser, notifier)
            except Exception as e: logger.error(f"Error fetching feed {feed.url}: {str(e)}")
        process_pending_articles(db_manager, notifier)
    finally: db_manager.close()

def main():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_all_feeds, 'interval', minutes=config.CHECK_INTERVAL_MINUTES)
    scheduler.start(); scheduler.add_job(process_all_feeds)
    try: app.run(host='0.0.0.0', port=5001, use_reloader=False)
    except (KeyboardInterrupt, SystemExit): scheduler.shutdown()

if __name__ == "__main__":
    main()
