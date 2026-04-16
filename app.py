import os
import sys
import traceback
from datetime import datetime, timedelta
import uuid
import random
import sqlite3
from contextlib import contextmanager
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room

# Initialize Flask app first
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'konami-hub-2026-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# ==================== DATABASE CONFIGURATION ====================
# Configure for different platforms
if os.environ.get('RENDER'):
    # Render.com configuration
    DATA_DIR = '/opt/render/project/src/data'
    DATABASE_PATH = os.path.join(DATA_DIR, 'konami_hub.db')
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    print(f"Running on Render - Data dir: {DATA_DIR}")
elif os.environ.get('FLY_APP_NAME'):
    # Fly.io configuration
    DATA_DIR = '/data'
    DATABASE_PATH = os.path.join(DATA_DIR, 'konami_hub.db')
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    print(f"Running on Fly.io - Data dir: {DATA_DIR}")
else:
    # Local development
    DATA_DIR = 'data'
    DATABASE_PATH = os.path.join(DATA_DIR, 'konami_hub.db')
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    print(f"Running locally - Data dir: {DATA_DIR}")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== SOCKET.IO ====================
# SocketIO - use threading for Render (more compatible)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
print("Running with threading async mode (compatible with all platforms)")

# ==================== DATABASE ====================

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def dict_from_row(row):
    return dict(zip(row.keys(), row)) if row else None

def list_from_cursor(cursor):
    return [dict_from_row(row) for row in cursor.fetchall()]

def init_database():
    try:
        with get_db() as conn:
            # Users table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    joined TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # Posts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    excerpt TEXT,
                    body TEXT NOT NULL,
                    image_label TEXT,
                    date TEXT NOT NULL,
                    author_id TEXT,
                    author_name TEXT
                )
            ''')
            
            # Comments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # Leagues table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS leagues (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    champion_declared INTEGER DEFAULT 0
                )
            ''')
            
            # League members table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS league_members (
                    league_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    PRIMARY KEY (league_id, username)
                )
            ''')
            
            # League standings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS league_standings (
                    league_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    played INTEGER DEFAULT 0,
                    won INTEGER DEFAULT 0,
                    drawn INTEGER DEFAULT 0,
                    lost INTEGER DEFAULT 0,
                    goals_for INTEGER DEFAULT 0,
                    goals_against INTEGER DEFAULT 0,
                    goal_difference INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    PRIMARY KEY (league_id, username)
                )
            ''')
            
            # Tournaments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tournaments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    league_id TEXT NOT NULL,
                    league_name TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    max_participants INTEGER DEFAULT 16,
                    status TEXT DEFAULT 'upcoming',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    champion_declared INTEGER DEFAULT 0
                )
            ''')
            
            # Tournament participants table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tournament_participants (
                    tournament_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    PRIMARY KEY (tournament_id, username)
                )
            ''')
            
            # Fixtures table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fixtures (
                    id TEXT PRIMARY KEY,
                    league_id TEXT,
                    tournament_id TEXT,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    result TEXT,
                    status TEXT DEFAULT 'scheduled',
                    round TEXT,
                    played INTEGER DEFAULT 0,
                    winner TEXT
                )
            ''')
            
            # Chat messages table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    league_id TEXT,
                    tournament_id TEXT,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    time_display TEXT NOT NULL
                )
            ''')
            
            # Champions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS champions (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    competition_name TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    date TEXT NOT NULL,
                    season TEXT NOT NULL
                )
            ''')
            
            # Admin photos table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admin_photos (
                    id TEXT PRIMARY KEY,
                    from_user TEXT NOT NULL,
                    photo_url TEXT NOT NULL,
                    caption TEXT,
                    match_id TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Insert default admin user
            cursor = conn.execute('SELECT * FROM users WHERE username = ?', ('pro_gamer',))
            if not cursor.fetchone():
                conn.execute('''
                    INSERT INTO users (id, username, password, joined, is_admin)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('u2', 'pro_gamer', 'goal2026', datetime.now().strftime('%Y-%m-%d'), 1))
            
            # Insert default regular user
            cursor = conn.execute('SELECT * FROM users WHERE username = ?', ('efootball_fan',))
            if not cursor.fetchone():
                conn.execute('''
                    INSERT INTO users (id, username, password, joined, is_admin)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('u1', 'efootball_fan', 'pass123', datetime.now().strftime('%Y-%m-%d'), 0))
            
            # Insert default post
            cursor = conn.execute('SELECT * FROM posts LIMIT 1')
            if not cursor.fetchone():
                conn.execute('''
                    INSERT INTO posts (id, title, excerpt, body, image_label, date, author_id, author_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ('p1', 'eFootball 2026: Next Generation Update', 
                      'Konami unveils revolutionary gameplay mechanics for 2026...',
                      'The latest eFootball 2026 update introduces revolutionary AI, cross-platform progression, and the new Ultimate Team mode.',
                      '⚽', 'January 15, 2026', 'sys', 'Konami Insider'))

        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Create a simple fallback
        with open(os.path.join(DATA_DIR, 'init_log.txt'), 'w') as f:
            f.write(f"Error: {e}\n")

# ==================== DATABASE HELPER FUNCTIONS ====================

def get_users():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM users'))

def get_posts():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM posts ORDER BY date DESC'))

def save_post(post):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO posts (id, title, excerpt, body, image_label, date, author_id, author_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post['id'], post['title'], post['excerpt'], post['body'], 
              post['image_label'], post['date'], post['author_id'], post['author_name']))

def delete_post(post_id):
    with get_db() as conn:
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))

def get_comments():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM comments ORDER BY created_at DESC'))

def save_comment(comment):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO comments (id, post_id, user_id, user_name, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (comment['id'], comment['post_id'], comment['user_id'], 
              comment['user_name'], comment['text'], comment['created_at']))

def get_leagues():
    with get_db() as conn:
        leagues = list_from_cursor(conn.execute('SELECT * FROM leagues'))
        for league in leagues:
            members = conn.execute('SELECT username FROM league_members WHERE league_id = ?', (league['id'],))
            league['members'] = [row['username'] for row in members.fetchall()]
            standings = conn.execute('''
                SELECT * FROM league_standings WHERE league_id = ? 
                ORDER BY points DESC, goal_difference DESC, goals_for DESC
            ''', (league['id'],))
            league['standings'] = list_from_cursor(standings)
        return leagues

def save_league(league):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO leagues (id, name, description, created_by, created_at, status, champion_declared)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (league['id'], league['name'], league['description'], league['created_by'], 
              league['created_at'], league['status'], league.get('champion_declared', 0)))
        
        conn.execute('DELETE FROM league_members WHERE league_id = ?', (league['id'],))
        for member in league.get('members', []):
            conn.execute('INSERT INTO league_members (league_id, username) VALUES (?, ?)', (league['id'], member))
        
        conn.execute('DELETE FROM league_standings WHERE league_id = ?', (league['id'],))
        for team in league.get('standings', []):
            conn.execute('''
                INSERT INTO league_standings (league_id, username, played, won, drawn, lost, goals_for, goals_against, goal_difference, points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (league['id'], team['username'], team['played'], team['won'], team['drawn'], 
                  team['lost'], team['goals_for'], team['goals_against'], team['goal_difference'], team['points']))

def delete_league(league_id):
    with get_db() as conn:
        conn.execute('DELETE FROM leagues WHERE id = ?', (league_id,))
        conn.execute('DELETE FROM league_members WHERE league_id = ?', (league_id,))
        conn.execute('DELETE FROM league_standings WHERE league_id = ?', (league_id,))
        conn.execute('DELETE FROM fixtures WHERE league_id = ?', (league_id,))
        conn.execute('DELETE FROM chat_messages WHERE league_id = ?', (league_id,))

def get_tournaments():
    with get_db() as conn:
        tournaments = list_from_cursor(conn.execute('SELECT * FROM tournaments'))
        for tournament in tournaments:
            participants = conn.execute('SELECT username FROM tournament_participants WHERE tournament_id = ?', (tournament['id'],))
            tournament['current_participants'] = [row['username'] for row in participants.fetchall()]
        return tournaments

def save_tournament(tournament):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO tournaments (id, name, league_id, league_name, description, start_date, end_date, max_participants, status, created_by, created_at, champion_declared)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tournament['id'], tournament['name'], tournament['league_id'], tournament['league_name'],
              tournament['description'], tournament['start_date'], tournament['end_date'], 
              tournament['max_participants'], tournament['status'], tournament['created_by'],
              tournament['created_at'], tournament.get('champion_declared', 0)))
        
        conn.execute('DELETE FROM tournament_participants WHERE tournament_id = ?', (tournament['id'],))
        for participant in tournament.get('current_participants', []):
            conn.execute('INSERT INTO tournament_participants (tournament_id, username) VALUES (?, ?)', (tournament['id'], participant))

def delete_tournament(tournament_id):
    with get_db() as conn:
        conn.execute('DELETE FROM tournaments WHERE id = ?', (tournament_id,))
        conn.execute('DELETE FROM tournament_participants WHERE tournament_id = ?', (tournament_id,))
        conn.execute('DELETE FROM fixtures WHERE tournament_id = ?', (tournament_id,))
        conn.execute('DELETE FROM chat_messages WHERE tournament_id = ?', (tournament_id,))

def get_chat_messages():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM chat_messages ORDER BY timestamp ASC'))

def save_chat_message(message):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO chat_messages (id, league_id, tournament_id, username, message, timestamp, time_display)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message['id'], message.get('league_id'), message.get('tournament_id'), 
              message['username'], message['message'], message['timestamp'], message['time_display']))

def clear_chat_messages(chat_type, id):
    with get_db() as conn:
        if chat_type == 'league':
            conn.execute('DELETE FROM chat_messages WHERE league_id = ?', (id,))
        elif chat_type == 'tournament':
            conn.execute('DELETE FROM chat_messages WHERE tournament_id = ?', (id,))

def get_fixtures():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM fixtures ORDER BY date ASC'))

def save_fixture(fixture):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO fixtures (id, league_id, tournament_id, home_team, away_team, date, time, result, status, round, played, winner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fixture['id'], fixture.get('league_id'), fixture.get('tournament_id'), 
              fixture['home_team'], fixture['away_team'], fixture['date'], fixture['time'],
              fixture.get('result'), fixture.get('status', 'scheduled'), fixture.get('round'), 
              fixture.get('played', 0), fixture.get('winner')))

def delete_fixtures_by_league(league_id):
    with get_db() as conn:
        conn.execute('DELETE FROM fixtures WHERE league_id = ?', (league_id,))

def get_champions():
    with get_db() as conn:
        return list_from_cursor(conn.execute('SELECT * FROM champions ORDER BY date DESC'))

def save_champion(champion):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO champions (id, type, competition_name, champion, date, season)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (champion['id'], champion['type'], champion['competition_name'], 
              champion['champion'], champion['date'], champion['season']))

def delete_all_champions():
    with get_db() as conn:
        conn.execute('DELETE FROM champions')

def delete_champion_by_id(champion_id):
    with get_db() as conn:
        conn.execute('DELETE FROM champions WHERE id = ?', (champion_id,))

def is_admin(user):
    return user and user.get('username') == 'pro_gamer'

# ==================== LEAGUE & TOURNAMENT FUNCTIONS ====================

def generate_league_fixtures(league_id, members):
    delete_fixtures_by_league(league_id)
    
    if len(members) < 2:
        return
    
    schedule = []
    n = len(members)
    
    for i in range(n):
        for j in range(i + 1, n):
            schedule.append({'home': members[i], 'away': members[j]})
            schedule.append({'home': members[j], 'away': members[i]})
    
    random.shuffle(schedule)
    
    start_date = datetime.now() + timedelta(days=7)
    matches_per_week = max(2, len(members) // 2)
    
    for idx, match in enumerate(schedule):
        week_number = idx // matches_per_week
        match_date = start_date + timedelta(days=week_number * 7)
        
        fixture = {
            'id': str(uuid.uuid4()),
            'league_id': league_id,
            'tournament_id': None,
            'home_team': match['home'],
            'away_team': match['away'],
            'date': match_date.strftime('%Y-%m-%d'),
            'time': '20:00',
            'result': None,
            'status': 'scheduled',
            'played': False,
            'winner': None
        }
        save_fixture(fixture)
    
    total_matches = len(schedule)
    matches_per_team = total_matches * 2 // len(members) if len(members) > 0 else 0
    
    socketio.emit('chat_message', {
        'username': '⚽ League Bot',
        'message': f'🏆 League fixtures generated!\n\n📊 {len(members)} teams\n⚽ {total_matches} total matches\n🎯 Each team will play {matches_per_team} matches',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'is_system': True
    }, room=f"league_{league_id}")

def update_league_standings(league_id):
    leagues = get_leagues()
    league = next((l for l in leagues if l['id'] == league_id), None)
    if not league:
        return
    
    fixtures = get_fixtures()
    league_fixtures = [f for f in fixtures if f.get('league_id') == league_id and f.get('played') == True]
    
    standings = {}
    for member in league['members']:
        standings[member] = {
            'username': member,
            'played': 0,
            'won': 0,
            'drawn': 0,
            'lost': 0,
            'goals_for': 0,
            'goals_against': 0,
            'goal_difference': 0,
            'points': 0
        }
    
    for fixture in league_fixtures:
        if fixture.get('result'):
            home_team = fixture['home_team']
            away_team = fixture['away_team']
            result_parts = fixture['result'].split('-')
            if len(result_parts) == 2:
                home_score = int(result_parts[0])
                away_score = int(result_parts[1])
                
                standings[home_team]['played'] += 1
                standings[home_team]['goals_for'] += home_score
                standings[home_team]['goals_against'] += away_score
                standings[away_team]['played'] += 1
                standings[away_team]['goals_for'] += away_score
                standings[away_team]['goals_against'] += home_score
                
                if home_score > away_score:
                    standings[home_team]['won'] += 1
                    standings[home_team]['points'] += 3
                    standings[away_team]['lost'] += 1
                elif home_score < away_score:
                    standings[away_team]['won'] += 1
                    standings[away_team]['points'] += 3
                    standings[home_team]['lost'] += 1
                else:
                    standings[home_team]['drawn'] += 1
                    standings[home_team]['points'] += 1
                    standings[away_team]['drawn'] += 1
                    standings[away_team]['points'] += 1
    
    for team in standings.values():
        team['goal_difference'] = team['goals_for'] - team['goals_against']
    
    standings_list = sorted(standings.values(), key=lambda x: (-x['points'], -x['goal_difference'], -x['goals_for']))
    league['standings'] = standings_list
    save_league(league)
    check_and_declare_league_champion(league_id)

def check_and_declare_league_champion(league_id):
    leagues = get_leagues()
    league = next((l for l in leagues if l['id'] == league_id), None)
    if not league or league.get('champion_declared'):
        return
    
    fixtures = get_fixtures()
    league_fixtures = [f for f in fixtures if f.get('league_id') == league_id]
    unplayed = [f for f in league_fixtures if not f.get('played')]
    
    if len(unplayed) == 0 and league.get('standings') and len(league['standings']) > 0:
        champion = league['standings'][0]['username']
        announce_champion('league', league['name'], champion)
        league['champion_declared'] = True
        save_league(league)

def announce_champion(competition_type, competition_name, champion_name):
    champion_entry = {
        'id': str(uuid.uuid4()),
        'type': competition_type,
        'competition_name': competition_name,
        'champion': champion_name,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'season': datetime.now().strftime('%Y')
    }
    save_champion(champion_entry)
    
    if competition_type == 'league':
        leagues = get_leagues()
        league = next((l for l in leagues if l['name'] == competition_name), None)
        if league:
            announcement = f"🏆 CHAMPION ANNOUNCEMENT! 🏆\n\nCongratulations {champion_name}! You are the CHAMPION of {competition_name}!"
            socketio.emit('chat_message', {
                'username': '🏆 CHAMPION BOT 🏆',
                'message': announcement,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{league['id']}")

# ==================== PAGE ROUTES ====================

@app.route('/')
def index():
    posts = get_posts()
    champions = get_champions()
    user = session.get('user')
    return render_template('index.html', posts=posts, champions=champions, user=user, is_admin=is_admin(user))

@app.route('/privacy')
def privacy():
    user = session.get('user')
    return render_template('privacy.html', user=user, is_admin=is_admin(user), datetime=datetime)

@app.route('/terms')
def terms():
    user = session.get('user')
    return render_template('terms.html', user=user, is_admin=is_admin(user), datetime=datetime)

@app.route('/about')
def about():
    user = session.get('user')
    return render_template('about.html', user=user, is_admin=is_admin(user))

@app.route('/messages')
def messages_page():
    if not is_admin(session.get('user')):
        return redirect('/')
    return render_template('messages.html', user=session.get('user'), is_admin=True)

@app.route('/post/<post_id>')
def post_detail(post_id):
    posts = get_posts()
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        return "Post not found", 404
    
    comments = [c for c in get_comments() if c['post_id'] == post_id]
    comments.sort(key=lambda x: x['created_at'], reverse=True)
    
    user = session.get('user')
    return render_template('post_detail.html', post=post, comments=comments, user=user, is_admin=is_admin(user))

@app.route('/admin')
def admin_dashboard():
    if not is_admin(session.get('user')):
        return redirect('/')
    
    users = get_users()
    leagues = get_leagues()
    tournaments = get_tournaments()
    posts = get_posts()
    comments = get_comments()
    fixtures = get_fixtures()
    champions = get_champions()
    
    recent_posts = sorted(posts, key=lambda x: x.get('date', ''), reverse=True)[:5]
    
    user = session.get('user')
    return render_template('admin_dashboard.html', 
                         users=users, leagues=leagues, tournaments=tournaments,
                         posts=posts, comments=comments, fixtures=fixtures,
                         champions=champions, recent_posts=recent_posts,
                         user=user, is_admin=True)

@app.route('/admin/posts')
def admin_posts():
    if not is_admin(session.get('user')):
        return redirect('/')
    
    posts = get_posts()
    comments = get_comments()
    user = session.get('user')
    return render_template('admin_posts.html', posts=posts, comments=comments, user=user, is_admin=True)

@app.route('/admin/posts/create', methods=['GET', 'POST'])
def create_post():
    if not is_admin(session.get('user')):
        return redirect('/')
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        body = request.form.get('body', '').strip()
        image_label = request.form.get('image_label', '⚽').strip()
        
        if not title or not body:
            user = session.get('user')
            return render_template('create_post.html', error='Title and body are required', user=user, is_admin=True)
        
        new_post = {
            'id': str(uuid.uuid4()),
            'title': title,
            'excerpt': excerpt if excerpt else body[:100] + '...',
            'body': body,
            'image_label': image_label,
            'date': datetime.now().strftime('%B %d, %Y'),
            'author_id': session['user']['id'],
            'author_name': session['user']['username']
        }
        save_post(new_post)
        return redirect(url_for('admin_posts'))
    
    user = session.get('user')
    return render_template('create_post.html', user=user, is_admin=True)

@app.route('/admin/posts/edit/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if not is_admin(session.get('user')):
        return redirect('/')
    
    posts = get_posts()
    post = next((p for p in posts if p['id'] == post_id), None)
    
    if not post:
        return redirect(url_for('admin_posts'))
    
    if request.method == 'POST':
        post['title'] = request.form.get('title', '').strip()
        post['excerpt'] = request.form.get('excerpt', '').strip()
        post['body'] = request.form.get('body', '').strip()
        post['image_label'] = request.form.get('image_label', '⚽').strip()
        
        if not post['title'] or not post['body']:
            user = session.get('user')
            return render_template('edit_post.html', post=post, error='Title and body are required', user=user, is_admin=True)
        
        if not post['excerpt']:
            post['excerpt'] = post['body'][:100] + '...'
        
        save_post(post)
        return redirect(url_for('admin_posts'))
    
    user = session.get('user')
    return render_template('edit_post.html', post=post, user=user, is_admin=True)

@app.route('/leagues')
def leagues_page():
    leagues = get_leagues()
    user = session.get('user')
    return render_template('leagues.html', leagues=leagues, user=user, is_admin=is_admin(user))

@app.route('/leagues/<league_id>/chat')
def league_chat(league_id):
    leagues = get_leagues()
    league = next((l for l in leagues if l['id'] == league_id), None)
    if not league:
        return redirect(url_for('leagues_page'))
    
    user = session.get('user')
    if not user or user['username'] not in league['members']:
        return redirect(url_for('leagues_page'))
    
    all_messages = get_chat_messages()
    messages = [m for m in all_messages if m.get('league_id') == league_id]
    fixtures = get_fixtures()
    league_fixtures = [f for f in fixtures if f.get('league_id') == league_id]
    
    return render_template('league_chat.html', league=league, messages=messages, 
                         fixtures=league_fixtures, user=user, is_admin=is_admin(user))

@app.route('/tournaments')
def tournaments_page():
    tournaments = get_tournaments()
    leagues = get_leagues()
    user = session.get('user')
    return render_template('tournaments.html', tournaments=tournaments, leagues=leagues, 
                         user=user, is_admin=is_admin(user))

@app.route('/tournaments/<tournament_id>/chat')
def tournament_chat(tournament_id):
    tournaments = get_tournaments()
    tournament = next((t for t in tournaments if t['id'] == tournament_id), None)
    if not tournament:
        return redirect(url_for('tournaments_page'))
    
    user = session.get('user')
    if not user or user['username'] not in tournament['current_participants'] and not is_admin(user):
        return redirect(url_for('tournaments_page'))
    
    all_messages = get_chat_messages()
    messages = [m for m in all_messages if m.get('tournament_id') == tournament_id]
    fixtures = get_fixtures()
    tournament_fixtures = [f for f in fixtures if f.get('tournament_id') == tournament_id]
    
    return render_template('tournament_chat.html', tournament=tournament, messages=messages, 
                         fixtures=tournament_fixtures, user=user, is_admin=is_admin(user))

# ==================== API ENDPOINTS ====================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'Username already exists'}), 400
        
        user_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO users (id, username, password, joined, is_admin)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, password, datetime.now().strftime('%Y-%m-%d'), 0))
        
        session['user'] = {'id': user_id, 'username': username, 'is_admin': False}
        return jsonify({'success': True, 'user': session['user']})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        session['user'] = {'id': user['id'], 'username': user['username'], 'is_admin': user['is_admin']}
        return jsonify({'success': True, 'user': session['user']})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/api/comments', methods=['POST'])
def add_comment():
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    post_id = data.get('post_id')
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'success': False, 'error': 'Comment cannot be empty'}), 400
    
    comment = {
        'id': str(uuid.uuid4()),
        'post_id': post_id,
        'user_id': session['user']['id'],
        'user_name': session['user']['username'],
        'text': text,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_comment(comment)
    return jsonify({'success': True, 'comment': comment})

@app.route('/api/leagues', methods=['POST'])
def create_league():
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': 'League name required'}), 400
    
    league_id = str(uuid.uuid4())
    new_league = {
        'id': league_id,
        'name': name,
        'description': description,
        'created_by': session['user']['username'],
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'members': [],
        'status': 'active',
        'standings': [],
        'champion_declared': False
    }
    save_league(new_league)
    return jsonify({'success': True, 'league': new_league})

@app.route('/api/leagues/<league_id>/members', methods=['POST'])
def add_member_to_league(league_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        cursor = conn.execute('SELECT * FROM leagues WHERE id = ?', (league_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'League not found'}), 404
    
    leagues = get_leagues()
    league = next((l for l in leagues if l['id'] == league_id), None)
    
    if username not in league['members']:
        league['members'].append(username)
        save_league(league)
        generate_league_fixtures(league_id, league['members'])
        
        socketio.emit('chat_message', {
            'username': '⚽ Bot',
            'message': f'{username} has joined the league! Fixtures have been generated.',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"league_{league_id}")
    
    return jsonify({'success': True, 'members': league['members']})

@app.route('/api/leagues/<league_id>', methods=['DELETE'])
def delete_league_route(league_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    delete_league(league_id)
    return jsonify({'success': True, 'message': 'League deleted successfully'})

@app.route('/api/tournaments', methods=['POST'])
def create_tournament():
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    name = data.get('name', '').strip()
    league_id = data.get('league_id', '').strip()
    description = data.get('description', '').strip()
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    max_participants = data.get('max_participants', 16)
    
    if not name or not league_id:
        return jsonify({'success': False, 'error': 'Name and league ID required'}), 400
    
    leagues = get_leagues()
    league = next((l for l in leagues if l['id'] == league_id), None)
    if not league:
        return jsonify({'success': False, 'error': 'League not found'}), 404
    
    tournament_id = str(uuid.uuid4())
    new_tournament = {
        'id': tournament_id,
        'name': name,
        'league_id': league_id,
        'league_name': league['name'],
        'description': description,
        'start_date': start_date,
        'end_date': end_date,
        'max_participants': max_participants,
        'current_participants': [],
        'status': 'upcoming',
        'created_by': session['user']['username'],
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'champion_declared': False
    }
    save_tournament(new_tournament)
    return jsonify({'success': True, 'tournament': new_tournament})

@app.route('/api/tournaments/<tournament_id>', methods=['DELETE'])
def delete_tournament_route(tournament_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    delete_tournament(tournament_id)
    return jsonify({'success': True, 'message': 'Tournament deleted successfully'})

@app.route('/api/tournaments/<tournament_id>/join', methods=['POST'])
def join_tournament(tournament_id):
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401
    
    tournaments = get_tournaments()
    tournament = next((t for t in tournaments if t['id'] == tournament_id), None)
    if not tournament:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    username = session['user']['username']
    
    if username in tournament['current_participants']:
        return jsonify({'success': False, 'error': 'Already joined'}), 400
    
    if len(tournament['current_participants']) >= tournament['max_participants']:
        return jsonify({'success': False, 'error': 'Tournament is full'}), 400
    
    tournament['current_participants'].append(username)
    save_tournament(tournament)
    
    return jsonify({'success': True, 'participants': tournament['current_participants']})

@app.route('/api/fixtures/<fixture_id>/update', methods=['PUT'])
def update_fixture_datetime(fixture_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    new_date = data.get('date')
    new_time = data.get('time')
    
    fixtures = get_fixtures()
    fixture = next((f for f in fixtures if f['id'] == fixture_id), None)
    if not fixture:
        return jsonify({'success': False, 'error': 'Fixture not found'}), 404
    
    if new_date:
        fixture['date'] = new_date
    if new_time:
        fixture['time'] = new_time
    
    save_fixture(fixture)
    return jsonify({'success': True, 'fixture': fixture})

@app.route('/api/fixtures/<fixture_id>/result', methods=['PUT'])
def update_fixture_result(fixture_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    home_score = data.get('home_score')
    away_score = data.get('away_score')
    
    fixtures = get_fixtures()
    fixture = next((f for f in fixtures if f['id'] == fixture_id), None)
    if not fixture:
        return jsonify({'success': False, 'error': 'Fixture not found'}), 404
    
    fixture['result'] = f"{home_score}-{away_score}"
    fixture['status'] = 'completed'
    fixture['played'] = True
    save_fixture(fixture)
    
    if fixture.get('league_id'):
        update_league_standings(fixture['league_id'])
        
        leagues = get_leagues()
        league = next((l for l in leagues if l['id'] == fixture['league_id']), None)
        if league and league.get('standings'):
            standings_text = "📊 UPDATED LEAGUE STANDINGS 📊\n"
            for i, team in enumerate(league['standings'][:5], 1):
                standings_text += f"{i}. {team['username']} - {team['points']} pts\n"
            
            socketio.emit('chat_message', {
                'username': '⚽ Bot',
                'message': standings_text,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{fixture['league_id']}")
    
    return jsonify({'success': True, 'fixture': fixture})

@app.route('/api/chat/clear/<chat_type>/<id>', methods=['DELETE'])
def clear_chat_messages_route(chat_type, id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    clear_chat_messages(chat_type, id)
    
    if chat_type == 'league':
        socketio.emit('chat_message', {
            'username': '⚽ Bot',
            'message': '🧹 Chat history has been cleared by an admin!',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"league_{id}")
    elif chat_type == 'tournament':
        socketio.emit('chat_message', {
            'username': '🏆 Tournament Bot',
            'message': '🧹 Chat history has been cleared by an admin!',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"tournament_{id}")
    
    return jsonify({'success': True, 'message': 'Chat cleared successfully'})

@app.route('/api/admin/posts/<post_id>', methods=['DELETE'])
def delete_post_route(post_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    delete_post(post_id)
    return jsonify({'success': True, 'message': 'Post deleted successfully'})

@app.route('/api/admin/reset-champions', methods=['DELETE'])
def reset_champions():
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    delete_all_champions()
    return jsonify({'success': True, 'message': 'Wall of Champions reset successfully'})

@app.route('/api/admin/champions/<champion_id>', methods=['DELETE'])
def remove_champion(champion_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    delete_champion_by_id(champion_id)
    return jsonify({'success': True, 'message': 'Champion removed successfully'})

# ==================== PHOTO UPLOAD API ====================

@app.route('/api/upload-photo', methods=['POST'])
def upload_photo_to_admin():
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401
    
    if 'photo' not in request.files:
        return jsonify({'success': False, 'error': 'No photo uploaded'}), 400
    
    file = request.files['photo']
    caption = request.form.get('caption', '')
    match_id = request.form.get('match_id', '')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400
    
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': f'File too large. Max 5MB'}), 400
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    original_filename = secure_filename(file.filename)
    filename = f"{session['user']['username']}_{timestamp}_{original_filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    photo_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute('''
            INSERT INTO admin_photos (id, from_user, photo_url, caption, match_id, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (photo_id, session['user']['username'], filename, caption, match_id,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))
    
    socketio.emit('new_photo_submission', {
        'id': photo_id,
        'from_user': session['user']['username'],
        'caption': caption,
        'match_id': match_id,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }, room='admin_room')
    
    return jsonify({'success': True, 'message': 'Photo sent to admin for review', 'photo_id': photo_id})

@app.route('/api/admin/photos', methods=['GET'])
def get_photo_submissions():
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    status = request.args.get('status', 'pending')
    
    with get_db() as conn:
        if status == 'all':
            cursor = conn.execute('SELECT * FROM admin_photos ORDER BY timestamp DESC')
        else:
            cursor = conn.execute('SELECT * FROM admin_photos WHERE status = ? ORDER BY timestamp DESC', (status,))
        
        photos = list_from_cursor(cursor)
        
        for photo in photos:
            photo['photo_url_full'] = f"/api/photos/{photo['photo_url']}"
        
        return jsonify({'success': True, 'photos': photos})

@app.route('/api/photos/<filename>')
def serve_photo(filename):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if '..' in filename or filename.startswith('/'):
        return jsonify({'error': 'Invalid filename'}), 400
    
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Photo not found'}), 404
    
    with get_db() as conn:
        cursor = conn.execute('SELECT from_user FROM admin_photos WHERE photo_url = ?', (filename,))
        photo = cursor.fetchone()
        
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        if not is_admin(session.get('user')) and photo['from_user'] != session['user']['username']:
            return jsonify({'error': 'Unauthorized'}), 401
    
    return send_file(filepath, mimetype='image/jpeg')

@app.route('/api/admin/photos/<photo_id>/status', methods=['PUT'])
def update_photo_status(photo_id):
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    status = data.get('status')
    
    with get_db() as conn:
        conn.execute('UPDATE admin_photos SET status = ? WHERE id = ?', (status, photo_id))
        
        cursor = conn.execute('SELECT from_user FROM admin_photos WHERE id = ?', (photo_id,))
        photo = cursor.fetchone()
        
        if photo:
            socketio.emit('photo_status_update', {
                'photo_id': photo_id,
                'status': status,
                'message': f'Your photo submission has been {status}'
            }, room=f"user_{photo['from_user']}")
    
    return jsonify({'success': True, 'message': f'Photo {status}'})

@app.route('/api/users', methods=['GET'])
def get_all_users():
    if not is_admin(session.get('user')):
        return jsonify({'success': False, 'error': 'Admin privileges required'}), 403
    
    users = get_users()
    user_list = [{'username': u['username'], 'joined': u['joined'], 'is_admin': u['is_admin']} for u in users]
    return jsonify({'success': True, 'users': user_list})

# ==================== SOCKET.IO CHAT EVENTS ====================

@socketio.on('join_user_room')
def handle_join_user_room():
    username = session.get('user', {}).get('username')
    if username:
        join_room(f"user_{username}")
        if is_admin(session.get('user')):
            join_room('admin_room')

@socketio.on('join_league_chat')
def handle_join_league_chat(data):
    league_id = data.get('league_id')
    username = session.get('user', {}).get('username')
    
    if username:
        join_room(f"league_{league_id}")
        emit('chat_message', {
            'username': '⚽ Bot',
            'message': f'👋 {username} has joined the chat! Use @table for standings or @fixtures for matches.',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"league_{league_id}")

@socketio.on('leave_league_chat')
def handle_leave_league_chat(data):
    league_id = data.get('league_id')
    username = session.get('user', {}).get('username')
    
    if username:
        leave_room(f"league_{league_id}")
        emit('chat_message', {
            'username': '⚽ Bot',
            'message': f'{username} has left the chat',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"league_{league_id}")

@socketio.on('send_chat_message')
def handle_send_chat_message(data):
    league_id = data.get('league_id')
    message = data.get('message', '').strip()
    username = session.get('user', {}).get('username')
    
    if not username or not message:
        return
    
    if message.lower() == '@table':
        leagues = get_leagues()
        league = next((l for l in leagues if l['id'] == league_id), None)
        if league and league.get('standings'):
            standings_text = "📊 COMPLETE LEAGUE STANDINGS 📊\n"
            standings_text += "================================\n"
            for i, team in enumerate(league['standings'], 1):
                standings_text += f"{i}. {team['username']}\n"
                standings_text += f"   Points: {team['points']} | P: {team['played']} | W: {team['won']} | D: {team['drawn']} | L: {team['lost']}\n"
                standings_text += f"   GF: {team['goals_for']} | GA: {team['goals_against']} | GD: {team['goal_difference']}\n"
                standings_text += "--------------------------------\n"
            
            emit('chat_message', {
                'username': '📊 Standings Bot',
                'message': standings_text,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{league_id}")
        else:
            emit('chat_message', {
                'username': '⚽ Bot',
                'message': 'No standings available yet.',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{league_id}")
    
    elif message.lower() == '@fixtures':
        fixtures = get_fixtures()
        league_fixtures = [f for f in fixtures if f.get('league_id') == league_id]
        
        if league_fixtures:
            fixtures_text = "📅 LEAGUE FIXTURES & RESULTS 📅\n"
            fixtures_text += "================================\n"
            upcoming = [f for f in league_fixtures if not f.get('played')]
            completed = [f for f in league_fixtures if f.get('played')]
            
            if upcoming:
                fixtures_text += "⏳ UPCOMING MATCHES:\n"
                for f in upcoming[:10]:
                    fixtures_text += f"   {f['home_team']} vs {f['away_team']} - {f['date']} at {f['time']}\n"
                fixtures_text += "--------------------------------\n"
            
            if completed:
                fixtures_text += "✅ COMPLETED MATCHES:\n"
                for f in completed[-10:]:
                    fixtures_text += f"   {f['home_team']} {f['result']} {f['away_team']} - {f['date']}\n"
                fixtures_text += "--------------------------------\n"
            
            emit('chat_message', {
                'username': '📋 Fixtures Bot',
                'message': fixtures_text,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{league_id}")
        else:
            emit('chat_message', {
                'username': '⚽ Bot',
                'message': 'No fixtures scheduled yet.',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"league_{league_id}")
    
    else:
        new_message = {
            'id': str(uuid.uuid4()),
            'league_id': league_id,
            'tournament_id': None,
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'time_display': datetime.now().strftime('%H:%M:%S')
        }
        save_chat_message(new_message)
        
        emit('chat_message', {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': False
        }, room=f"league_{league_id}")

@socketio.on('join_tournament_chat')
def handle_join_tournament_chat(data):
    tournament_id = data.get('tournament_id')
    username = session.get('user', {}).get('username')
    
    if username:
        join_room(f"tournament_{tournament_id}")
        emit('chat_message', {
            'username': '🏆 Tournament Bot',
            'message': f'👋 {username} has joined the tournament chat!',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"tournament_{tournament_id}")

@socketio.on('leave_tournament_chat')
def handle_leave_tournament_chat(data):
    tournament_id = data.get('tournament_id')
    username = session.get('user', {}).get('username')
    
    if username:
        leave_room(f"tournament_{tournament_id}")
        emit('chat_message', {
            'username': '🏆 Tournament Bot',
            'message': f'{username} has left the tournament chat',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': True
        }, room=f"tournament_{tournament_id}")

@socketio.on('send_tournament_chat_message')
def handle_send_tournament_chat_message(data):
    tournament_id = data.get('tournament_id')
    message = data.get('message', '').strip()
    username = session.get('user', {}).get('username')
    
    if not username or not message:
        return
    
    if message.lower() == '@fixtures':
        fixtures = get_fixtures()
        tournament_fixtures = [f for f in fixtures if f.get('tournament_id') == tournament_id]
        
        if tournament_fixtures:
            fixtures_text = "🏆 TOURNAMENT BRACKETS 🏆\n"
            fixtures_text += "================================\n"
            
            for f in tournament_fixtures:
                if f.get('result'):
                    fixtures_text += f"✅ {f['home_team']} {f['result']} {f['away_team']}\n"
                else:
                    fixtures_text += f"⏳ {f['home_team']} vs {f['away_team']} - {f['date']}\n"
            
            emit('chat_message', {
                'username': '🏆 Tournament Bot',
                'message': fixtures_text,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"tournament_{tournament_id}")
        else:
            emit('chat_message', {
                'username': '🏆 Tournament Bot',
                'message': 'No fixtures scheduled yet.',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'is_system': True
            }, room=f"tournament_{tournament_id}")
    
    else:
        new_message = {
            'id': str(uuid.uuid4()),
            'league_id': None,
            'tournament_id': tournament_id,
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'time_display': datetime.now().strftime('%H:%M:%S')
        }
        save_chat_message(new_message)
        
        emit('chat_message', {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_system': False
        }, room=f"tournament_{tournament_id}")

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    print("=" * 50)
    print("ERROR TRACEBACK:")
    traceback.print_exc()
    print("=" * 50)
    return "Internal server error", 500

# ==================== RUN APP ====================

if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)