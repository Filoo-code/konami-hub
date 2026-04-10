import json
import os
from datetime import datetime

DATA_DIR = 'data'

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Reset users
default_users = [
    {"id": "u1", "username": "efootball_fan", "password": "pass123", "joined": "2025-01-15", "is_admin": False},
    {"id": "u2", "username": "pro_gamer", "password": "goal2025", "joined": "2025-02-10", "is_admin": True}
]
with open(os.path.join(DATA_DIR, 'users.json'), 'w', encoding='utf-8') as f:
    json.dump(default_users, f, indent=2, ensure_ascii=False)

# Reset posts
default_posts = [
    {
        "id": "p1",
        "title": "eFootball 2025: New Season Update",
        "excerpt": "Konami drops massive gameplay overhaul and new legends...",
        "body": "The latest eFootball 2025 update introduces smarter AI, revamped passing mechanics, and new Epic cards. Cross-play enhancements are now fully integrated.",
        "image_label": "⚽",
        "date": "April 2, 2025",
        "author_id": "sys",
        "author_name": "Konami Insider"
    },
    {
        "id": "p2",
        "title": "Best Formation Guide: 3-2-4-1",
        "excerpt": "Master the meta with this aggressive possession tactic...",
        "body": "3-2-4-1 is dominating the eFootball leaderboards. With two holding midfielders and four attacking mids, you overload the center.",
        "image_label": "📊",
        "date": "March 28, 2025",
        "author_id": "sys",
        "author_name": "Tactics Guru"
    },
    {
        "id": "p3",
        "title": "Player Review: Epic Messi '09",
        "excerpt": "Is the new Big Time Messi worth the coins? Full analysis...",
        "body": "Epic Messi '09 card features 99 dribbling, 98 finishing, and 'Phenomenal Finishing' skill.",
        "image_label": "🐐",
        "date": "March 20, 2025",
        "author_id": "sys",
        "author_name": "Card Scout"
    }
]
with open(os.path.join(DATA_DIR, 'posts.json'), 'w', encoding='utf-8') as f:
    json.dump(default_posts, f, indent=2, ensure_ascii=False)

# Reset comments
with open(os.path.join(DATA_DIR, 'comments.json'), 'w', encoding='utf-8') as f:
    json.dump([], f, indent=2, ensure_ascii=False)

# Reset leagues
default_leagues = [
    {
        "id": "l1",
        "name": "Champions League",
        "description": "Top-tier eFootball tournament featuring the best players",
        "created_by": "pro_gamer",
        "created_at": "2025-03-01",
        "members": ["efootball_fan"],
        "status": "active",
        "standings": [
            {"username": "efootball_fan", "played": 5, "won": 3, "drawn": 1, "lost": 1, "points": 10}
        ]
    }
]
with open(os.path.join(DATA_DIR, 'leagues.json'), 'w', encoding='utf-8') as f:
    json.dump(default_leagues, f, indent=2, ensure_ascii=False)

# Reset tournaments
default_tournaments = [
    {
        "id": "t1",
        "name": "Konami Cup 2025",
        "league_id": "l1",
        "league_name": "Champions League",
        "description": "Annual championship with exclusive rewards",
        "start_date": "2025-04-15",
        "end_date": "2025-04-30",
        "max_participants": 16,
        "current_participants": ["efootball_fan"],
        "status": "upcoming",
        "created_by": "pro_gamer",
        "created_at": "2025-03-20"
    }
]
with open(os.path.join(DATA_DIR, 'tournaments.json'), 'w', encoding='utf-8') as f:
    json.dump(default_tournaments, f, indent=2, ensure_ascii=False)

# Reset chat messages
with open(os.path.join(DATA_DIR, 'chat_messages.json'), 'w', encoding='utf-8') as f:
    json.dump([], f, indent=2, ensure_ascii=False)

# Reset fixtures
default_fixtures = [
    {
        "id": "f1",
        "league_id": "l1",
        "tournament_id": None,
        "home_team": "efootball_fan",
        "away_team": "pro_gamer",
        "date": "2025-04-16",
        "time": "20:00",
        "result": None,
        "status": "scheduled"
    }
]
with open(os.path.join(DATA_DIR, 'fixtures.json'), 'w', encoding='utf-8') as f:
    json.dump(default_fixtures, f, indent=2, ensure_ascii=False)

print("✅ All data files have been reset successfully!")