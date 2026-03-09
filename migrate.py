import os, json, sqlite3, time, logging, sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('migrate')

DB_FILE = 'chess.db'
PLAYERS_DIR = 'players/'
BATCH_SIZE = 20

def init_db(conn):
    conn.executescript("""
PRAGMA journal_mode = OFF;
PRAGMA synchronous  = OFF;
PRAGMA cache_size   = -128000;
PRAGMA temp_store   = MEMORY;
PRAGMA locking_mode = EXCLUSIVE;
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
""")
    conn.commit()

def add_indexes(conn):
    logger.info("Création des index...")
    conn.executescript("""
PRAGMA locking_mode = NORMAL;
PRAGMA journal_mode = WAL;
CREATE INDEX IF NOT EXISTS idx_games_end_time    ON games(end_time DESC);
CREATE INDEX IF NOT EXISTS idx_games_white       ON games(white_username);
CREATE INDEX IF NOT EXISTS idx_games_black       ON games(black_username);
CREATE INDEX IF NOT EXISTS idx_games_time_class  ON games(time_class);
CREATE INDEX IF NOT EXISTS idx_games_rated       ON games(rated);
CREATE INDEX IF NOT EXISTS idx_player_games_user ON player_games(username);
CREATE INDEX IF NOT EXISTS idx_players_title     ON players(title);
""")
    conn.commit()

def extract_opening(pgn):
    eco, name = '', ''
    if not pgn:
        return eco, name
    for line in pgn.splitlines():
        if line.startswith('[ECO '):       eco  = line[6:-2]
        elif line.startswith('[Opening '): name = line[10:-2]
        if eco and name: break
    return eco, name

def migrate():
    if not os.path.isdir(PLAYERS_DIR):
        logger.error(f"Dossier '{PLAYERS_DIR}' introuvable.")
        sys.exit(1)
    files = [f for f in os.listdir(PLAYERS_DIR) if f.endswith('.json')]
    if not files:
        logger.warning("Aucun fichier JSON trouvé dans players/")
        return

    logger.info(f"{len(files)} fichiers joueurs à migrer → {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)

    total_games, total_players, start = 0, 0, time.time()
    game_rows_buf, pg_rows_buf, player_rows_buf = [], [], []

    for i, fname in enumerate(files, 1):
        path = os.path.join(PLAYERS_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Lecture échouée {fname}: {e}")
            continue

        player_info = data.get('player_info', {})
        games       = data.get('games', [])
        username    = player_info.get('username') or fname.replace('.json', '')

        for g in games:
            url     = g.get('url', '')
            game_id = url.rstrip('/').split('/')[-1]
            if not game_id: continue
            eco, opening = extract_opening(g.get('pgn', ''))
            white, black = g.get('white', {}), g.get('black', {})
            game_rows_buf.append((
                game_id, url, g.get('pgn',''), g.get('time_control',''),
                g.get('time_class',''), 1 if g.get('rated') else 0, g.get('end_time'),
                white.get('username',''), white.get('rating'), white.get('result',''),
                black.get('username',''), black.get('rating'), black.get('result',''),
                eco, opening
            ))
            pg_rows_buf.append((username, game_id))

        player_rows_buf.append((
            username, player_info.get('player_id'), player_info.get('title',''),
            player_info.get('avatar',''), player_info.get('@id',''), len(games)
        ))
        total_players += 1

        if i % BATCH_SIZE == 0 or i == len(files):
            conn.executemany("INSERT OR IGNORE INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", game_rows_buf)
            conn.executemany("INSERT OR IGNORE INTO player_games VALUES (?,?)", pg_rows_buf)
            conn.executemany("INSERT OR REPLACE INTO players VALUES (?,?,?,?,?,?)", player_rows_buf)
            conn.commit()
            total_games += len(game_rows_buf)
            game_rows_buf, pg_rows_buf, player_rows_buf = [], [], []

            elapsed = time.time() - start
            rate    = total_games / elapsed if elapsed else 0
            eta     = ((len(files) - i) / i) * elapsed if i > 0 else 0
            logger.info(f"  {i}/{len(files)} joueurs | {total_games:,} parties | {rate:,.0f} parties/s | ETA ~{eta/60:.1f} min")

    logger.info("Mise à jour compteurs de parties...")
    conn.execute("UPDATE players SET games_count = (SELECT COUNT(*) FROM player_games WHERE player_games.username = players.username)")
    conn.commit()

    add_indexes(conn)

    elapsed = time.time() - start
    nb_games   = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    nb_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    logger.info(f"Terminé en {elapsed/60:.1f} min")
    logger.info(f"  {nb_games:,} parties | {nb_players:,} joueurs")
    logger.info(f"  Taille DB : {os.path.getsize(DB_FILE)/1e9:.2f} Go")
    conn.close()

if __name__ == '__main__':
    migrate()
