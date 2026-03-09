import sqlite3
import requests
import logging
from datetime import datetime
import sys

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)
logger = logging.getLogger('chess-scraping')

DB_FILE = 'chess.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -32000")
    return conn

def ensure_tables(conn):
    conn.executescript("""
CREATE TABLE IF NOT EXISTS players (
    username TEXT PRIMARY KEY, player_id INTEGER, title TEXT,
    avatar TEXT, api_id TEXT, games_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY, url TEXT, pgn TEXT, time_control TEXT,
    time_class TEXT, rated INTEGER, end_time INTEGER,
    white_username TEXT, white_rating INTEGER, white_result TEXT,
    black_username TEXT, black_rating INTEGER, black_result TEXT,
    opening_eco TEXT, opening_name TEXT
);
CREATE TABLE IF NOT EXISTS player_games (
    username TEXT, game_id TEXT, PRIMARY KEY (username, game_id)
);
CREATE INDEX IF NOT EXISTS idx_games_end_time    ON games(end_time DESC);
CREATE INDEX IF NOT EXISTS idx_games_white       ON games(white_username);
CREATE INDEX IF NOT EXISTS idx_games_black       ON games(black_username);
CREATE INDEX IF NOT EXISTS idx_games_time_class  ON games(time_class);
CREATE INDEX IF NOT EXISTS idx_games_rated       ON games(rated);
CREATE INDEX IF NOT EXISTS idx_player_games_user ON player_games(username);
CREATE INDEX IF NOT EXISTS idx_players_title     ON players(title);
""")
    conn.commit()

def get_existing_ids(conn):
    rows = conn.execute("SELECT game_id FROM games").fetchall()
    return set(r[0] for r in rows)

def extract_opening(pgn):
    eco, name = '', ''
    if not pgn:
        return eco, name
    for line in pgn.splitlines():
        if line.startswith('[ECO '):       eco  = line[6:-2]
        elif line.startswith('[Opening '): name = line[10:-2]
        if eco and name: break
    return eco, name

def upsert_player(conn, player):
    conn.execute("""
        INSERT OR REPLACE INTO players (username, player_id, title, avatar, api_id)
        VALUES (?, ?, ?, ?, ?)
    """, (
        player.get('username', ''),
        player.get('player_id'),
        player.get('title', ''),
        player.get('avatar', ''),
        player.get('@id', ''),
    ))

def insert_games(conn, username, new_games):
    game_rows, pg_rows = [], []
    for g in new_games:
        url     = g.get('url', '')
        game_id = url.rstrip('/').split('/')[-1]
        if not game_id: continue
        eco, opening = extract_opening(g.get('pgn', ''))
        white = g.get('white', {})
        black = g.get('black', {})
        game_rows.append((
            game_id, url, g.get('pgn', ''), g.get('time_control', ''),
            g.get('time_class', ''), 1 if g.get('rated') else 0, g.get('end_time'),
            white.get('username', ''), white.get('rating'), white.get('result', ''),
            black.get('username', ''), black.get('rating'), black.get('result', ''),
            eco, opening
        ))
        pg_rows.append((username, game_id))
    if game_rows:
        conn.executemany("INSERT OR IGNORE INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", game_rows)
    if pg_rows:
        conn.executemany("INSERT OR IGNORE INTO player_games VALUES (?,?)", pg_rows)
    conn.execute("""
        UPDATE players SET games_count = (
            SELECT COUNT(*) FROM player_games WHERE username = ?
        ) WHERE username = ?
    """, (username, username))
    conn.commit()
    return len(game_rows)

def fetch_player_games(player, existing_ids):
    new_games = []
    username  = player.get('username', 'inconnu')
    try:
        logger.info(f"Début du traitement pour {username}")
        archives = requests.get(
            player["@id"] + "/games/archives", headers=HEADERS, timeout=10
        ).json().get("archives", [])
        logger.info(f"{username}: {len(archives)} mois à traiter")
        for i, url in enumerate(archives, 1):
            if i == len(archives) // 2 or i == len(archives):
                logger.info(f"{username}: Mois {i}/{len(archives)} traités")
            try:
                month_games = requests.get(url, headers=HEADERS, timeout=10).json().get("games", [])
                for game in month_games:
                    game_id = game["url"].split('/')[-1]
                    if game_id not in existing_ids:
                        new_games.append(game)
                        existing_ids.add(game_id)
            except Exception as e:
                logger.error(f"Erreur sur le mois {url} pour {username}: {e}")
                continue
        logger.info(f"{username}: {len(new_games)} nouvelles parties trouvées")
    except Exception as e:
        logger.error(f"Erreur majeure pour {username}: {e}", exc_info=True)
    return new_games

def process_players(players_list):
    conn = get_db()
    ensure_tables(conn)
    logger.info("Chargement des parties existantes en mémoire...")
    existing_ids = get_existing_ids(conn)
    logger.info(f"{len(existing_ids):,} parties déjà en DB")
    logger.info(f"Début du traitement de {len(players_list)} joueurs")
    start_time = datetime.now()
    total_new  = 0
    for i, player in enumerate(players_list, 1):
        username = player.get("username", "?")
        if i % 10 == 0 or i == len(players_list):
            logger.info(f"Progression: {i}/{len(players_list)} joueurs traités | {total_new:,} nouvelles parties")
        try:
            upsert_player(conn, player)
            new_games = fetch_player_games(player, existing_ids)
            if new_games:
                inserted = insert_games(conn, username, new_games)
                total_new += inserted
        except Exception as e:
            logger.error(f"Erreur critique sur {username}: {e}", exc_info=True)
            continue
    conn.close()
    duration = datetime.now() - start_time
    logger.info(f"Traitement terminé en {duration}. {total_new:,} nouvelles parties ajoutées en DB")

def main():
    import json
    with open('top_players.json', 'r', encoding='utf-8') as f:
        players = json.load(f)["players"]
    process_players(players)
    logger.info("Scraping terminé avec succès !")
