import logging
import re
import time
import threading
import csv
import io
from functools import wraps
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, send_file

import config
from database import DatabaseManager, Article, User
from feed_parser import FeedParser
from notifier import Notifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    return local_dt.strftime('%Y-%m-%d %H:%M')

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
app.secret_key = config.SECRET_KEY
db_manager_web = DatabaseManager(config.DATABASE_URL)

@app.teardown_appcontext
def close_db(error):
    db_manager_web.close()

# --- Auth Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('group') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def mod_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('group') not in ['admin', 'moderator']:
            return jsonify({'error': 'Moderator access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Web Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username'); password = request.form.get('password')
        user = db_manager_web.authenticate_user(username, password)
        if user:
            session['user_id'] = user.id; session['username'] = user.username; session['group'] = user.group_name
            return redirect(url_for('index'))
        else: flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username'); email = request.form.get('email'); password = request.form.get('password')
        if not username or not email or not password:
            flash('Please fill all fields'); return render_template('register.html')
        user = db_manager_web.add_user(username, password, email=email, group='member_inactive')
        if user: flash('Registration successful! Please login.'); return redirect(url_for('login_page'))
        else: flash('Username or Email already exists')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login_page'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            db_manager_web.change_password(session['user_id'], new_password)
            flash('Password changed successfully'); return redirect(url_for('index'))
    return render_template('change_password.html', username=session.get('username'), group=session.get('group'))

@app.route('/')
@login_required
def index(): 
    return render_template('index.html', timezone=config.TIMEZONE, refresh_ms=config.DASHBOARD_REFRESH_MS, 
                           sound_enabled=config.ENABLE_SOUND_ALERTS, username=session.get('username'), group=session.get('group'))

@app.route('/moderation')
@login_required
@mod_required
def moderation_page(): 
    return render_template('moderation.html', timezone=config.TIMEZONE, username=session.get('username'), group=session.get('group'))

@app.route('/export')
@login_required
def export_page():
    if session.get('group') not in ['admin', 'moderator', 'member_plus']:
        flash('Export restricted to PRO accounts.'); return redirect(url_for('index'))
    return render_template('export.html', username=session.get('username'), group=session.get('group'))

@app.route('/users')
@login_required
@admin_only
def users_page():
    return render_template('users.html', username=session.get('username'), group=session.get('group'))

# --- API Endpoints ---
@app.route('/api/articles')
@login_required
def get_articles():
    try:
        page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', config.GLOBAL_ITEMS_PER_PAGE, type=int)
        deleted_only = request.args.get('deleted_only', 'false').lower() == 'true'
        if deleted_only and session.get('group') not in ['admin', 'moderator']: return jsonify({'error': 'Unauthorized'}), 403
        limit_inactive = (session.get('group') == 'member_inactive')
        articles, total = db_manager_web.get_paginated_articles(page=page, per_page=per_page, deleted_only=deleted_only, limit_to_10=limit_inactive)
        articles_list = [{'id': a.id, 'title': a.title, 'source': a.source, 'link': a.link, 'summary': a.summary, 'instruments': a.instruments, 'cause': a.cause, 'effect': a.effect, 'processed': bool(a.processed), 'created_at': format_local_time(a.created_at)} for a in articles]
        return jsonify({'articles': articles_list, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page, 'is_restricted': limit_inactive})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/articles/update/<int:article_id>', methods=['POST'])
@login_required
@mod_required
def update_article(article_id):
    try:
        success = db_manager_web.update_article_analysis(article_id, request.json)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/articles/delete/<int:article_id>', methods=['DELETE'])
@login_required
@mod_required
def delete_article(article_id):
    try:
        success = db_manager_web.delete_article(article_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/articles/revive/<int:article_id>', methods=['POST'])
@login_required
@mod_required
def revive_article(article_id):
    try:
        success = db_manager_web.revive_article(article_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/feeds')
@login_required
@mod_required
def get_feeds():
    try:
        feeds = db_manager_web.get_all_feeds()
        return jsonify([{'id': f.id, 'url': f.url, 'last_checked': format_local_time(f.last_checked), 'active': bool(f.active), 'created_at': format_local_time(f.created_at)} for f in feeds])
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/feeds/add', methods=['POST'])
@login_required
@mod_required
def add_feed():
    try:
        url = request.json.get('url')
        if not url: return jsonify({'error': 'URL required'}), 400
        db_manager_web.add_feed(url); return jsonify({'success': True})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/feeds/toggle/<int:feed_id>', methods=['POST'])
@login_required
@mod_required
def toggle_feed(feed_id):
    try:
        new_status = db_manager_web.toggle_feed(feed_id)
        return jsonify({'success': True, 'active': new_status})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/feeds/delete/<int:feed_id>', methods=['DELETE'])
@login_required
@mod_required
def delete_feed(feed_id):
    try:
        success = db_manager_web.delete_feed(feed_id)
        return jsonify({'success': success})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/export')
@login_required
def export_data():
    if session.get('group') not in ['admin', 'moderator', 'member_plus']: return jsonify({'error': 'Unauthorized'}), 403
    try:
        start_str = request.args.get('start_date'); end_str = request.args.get('end_date'); fmt = request.args.get('format', 'csv').lower()
        start_dt = datetime.strptime(start_str, '%Y-%m-%d'); end_dt = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
        session_db = db_manager_web.session
        articles = session_db.query(Article).filter(Article.created_at >= start_dt, Article.created_at < end_dt, Article.is_deleted == False, Article.processed == True).order_by(Article.created_at.asc()).all()
        if fmt == 'csv':
            output = io.StringIO(); writer = csv.writer(output)
            writer.writerow(['Date', 'Instrument', 'Cause', 'Effect', 'Title', 'Link'])
            for a in articles: writer.writerow([format_local_time(a.created_at), a.instruments, a.cause, a.effect, a.title, a.link])
            output.seek(0); return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f"news_export_{start_str}_to_{end_str}.csv")
        else:
            output = io.StringIO(); output.write(f"STRATEGIC ANALYSIS REPORT: {start_str} to {request.args.get('end_date')}\n" + "="*80 + "\n\n")
            for a in articles: output.write(f"DATE: {format_local_time(a.created_at)}\nINSTRUMENT: {a.instruments}\nCAUSE: {a.cause}\nEFFECT: {a.effect}\nSOURCE: {a.title} ({a.link})\n" + "-" * 40 + "\n")
            output.seek(0); return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/plain', as_attachment=True, download_name=f"news_report_{start_str}_to_{end_str}.txt")
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- User Management API ---
@app.route('/api/users')
@login_required
@admin_only
def get_users():
    users = db_manager_web.get_all_users()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'group': u.group_name, 'created_at': format_local_time(u.created_at)} for u in users])

@app.route('/api/users/add', methods=['POST'])
@login_required
@admin_only
def add_user():
    data = request.json
    user = db_manager_web.add_user(data.get('username'), data.get('password'), email=data.get('email'), group=data.get('group', 'member_inactive'))
    if user: return jsonify({'success': True})
    return jsonify({'error': 'User already exists'}), 400

@app.route('/api/users/update/<int:user_id>', methods=['POST'])
@login_required
@admin_only
def update_user(user_id):
    if user_id == session.get('user_id'): return jsonify({'error': 'Cannot change your own group'}), 400
    success = db_manager_web.update_user_group(user_id, request.json.get('group'))
    return jsonify({'success': success})

@app.route('/api/users/delete/<int:user_id>', methods=['DELETE'])
@login_required
@admin_only
def delete_user(user_id):
    if user_id == session.get('user_id'): return jsonify({'error': 'Cannot delete yourself'}), 400
    success = db_manager_web.delete_user(user_id)
    return jsonify({'success': success})

# --- Bot Logic ---
def process_feed(feed_url: str, db_manager: DatabaseManager, feed_parser: FeedParser, notifier: Notifier):
    articles = feed_parser.parse_feed(feed_url)
    for article in articles: db_manager.add_article(title=article['title'], link=article['link'], source=article['source'], summary=article['summary'], published=article['published'])
    db_manager.update_feed_last_checked(feed_url)

def process_pending_articles(db_manager: DatabaseManager, notifier: Notifier):
    pending = db_manager.get_unprocessed_articles()
    if not pending: return
    for art in pending:
        try:
            inst, cause, effect = notifier.analyze_article_cause_effect(art.title, art.summary)
            db_manager.mark_article_as_processed(art.id, instruments=inst, cause=cause, effect=effect)
            if config.BOT_SLEEP_BETWEEN_ARTICLES > 0: time.sleep(config.BOT_SLEEP_BETWEEN_ARTICLES)
        except Exception as e: logger.error(f"Failed to analyze article '{art.title}': {e}")

def process_all_feeds():
    db_manager = DatabaseManager(config.DATABASE_URL); feed_parser = FeedParser(config.MAX_ARTICLES_PER_FEED); notifier = Notifier(config)
    try:
        # Pre-seed from config if empty
        active_feeds = db_manager.get_active_feeds()
        if not active_feeds: 
            for url in config.FEEDS: db_manager.add_feed(url)
            active_feeds = db_manager.get_active_feeds()
        
        for feed in active_feeds:
            try: process_feed(feed.url, db_manager, feed_parser, notifier)
            except Exception as e: logger.error(f"Error fetching feed {feed.url}: {str(e)}")
        process_pending_articles(db_manager, notifier)
    finally: db_manager.close()

def main():
    scheduler = BackgroundScheduler(); scheduler.add_job(process_all_feeds, 'interval', minutes=config.CHECK_INTERVAL_MINUTES)
    scheduler.start(); scheduler.add_job(process_all_feeds)
    from waitress import serve
    logger.info(f"Starting Production Server (Waitress) on http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    try: serve(app, host=config.SERVER_HOST, port=config.SERVER_PORT, threads=config.SERVER_THREADS)
    except (KeyboardInterrupt, SystemExit): scheduler.shutdown(); logger.info("News Bot stopped")

if __name__ == "__main__":
    main()
