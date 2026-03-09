import sqlite3
import get_players
import get_games

DB_FILE = 'chess.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def count_games():
    db = get_db()
    n  = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    db.close()
    return f"Nombre de parties : {n}"

def count_players():
    db = get_db()
    n  = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    db.close()
    return f"Nombre de joueurs : {n}", n

def scan_players():
    get_players.main()

def scan_games():
    get_games.main()
