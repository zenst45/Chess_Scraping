from threading import Thread
from flask import Flask, Response, send_file, jsonify, request
from flask_cors import CORS
import get_players
import get_games
import subprocess
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB_FILE = 'chess.db'
LOG_SERVICE_NAME = "chess-scraping"
LOG_LINES = 500

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA cache_size = -32000")
    return conn

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/get/')
def api_get():
    if not os.path.exists(DB_FILE):
        return jsonify({"players": "DB non initialisée", "games": "Lancez migrate.py"})
    db = get_db()
    nb_players = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    nb_games   = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    db.close()
    return jsonify({
        "players": f"Nombre de joueurs : {nb_players}",
        "games":   f"Nombre de parties : {nb_games}",
    })

@app.route('/api/players/')
def api_players():
    page   = max(0, int(request.args.get('page',  0)))
    limit  = min(200, max(1, int(request.args.get('limit', request.args.get('per_page', 50)))))
    search = request.args.get('search', '').strip()
    title  = request.args.get('title',  '').strip()
    sort   = request.args.get('sort',   'username')
    sort_map = {
        'username':   'username ASC',
        'games_desc': 'games_count DESC',
        'games_asc':  'games_count ASC',
    }
    order = sort_map.get(sort, 'username ASC')
    where, params = [], []
    if search:
        where.append("username LIKE ?")
        params.append(f"%{search}%")
    if title:
        where.append("title = ?")
        params.append(title)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM players {where_sql}", params).fetchone()[0]
    rows  = db.execute(
        f"SELECT username, player_id, title, avatar, api_id, games_count FROM players {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [limit, page * limit]
    ).fetchall()
    db.close()
    return jsonify({"total": total, "page": page, "limit": limit, "players": [dict(r) for r in rows]})

@app.route('/api/games/')
def api_games():
    page       = max(0, int(request.args.get('page',  0)))
    limit      = min(200, max(1, int(request.args.get('limit', request.args.get('per_page', 50)))))
    search     = request.args.get('search',     '').strip()
    result     = request.args.get('result',     '').strip()
    time_class = request.args.get('time_class', '').strip()
    rated      = request.args.get('rated',      '').strip()
    username   = request.args.get('username',   '').strip()
    where, params = [], []
    if search:
        where.append("(white_username LIKE ? OR black_username LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if username:
        where.append("(white_username = ? OR black_username = ?)")
        params += [username, username]
    if time_class:
        where.append("time_class = ?")
        params.append(time_class)
    if rated != '':
        where.append("rated = ?")
        params.append(1 if rated == 'true' else 0)
    DRAWS = ('agreed','stalemate','repetition','timevsinsufficient','50move','insufficient')
    if result == 'win':
        where.append("white_result = 'win'")
    elif result == 'loss':
        where.append("black_result = 'win'")
    elif result == 'draw':
        where.append(f"white_result IN ({','.join('?'*len(DRAWS))})")
        params += list(DRAWS)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM games {where_sql}", params).fetchone()[0]
    rows  = db.execute(
        f"SELECT game_id, url, time_control, time_class, rated, end_time, white_username, white_rating, white_result, black_username, black_rating, black_result, opening_eco, opening_name FROM games {where_sql} ORDER BY end_time DESC LIMIT ? OFFSET ?",
        params + [limit, page * limit]
    ).fetchall()
    db.close()
    return jsonify({"total": total, "page": page, "limit": limit, "games": [dict(r) for r in rows]})

@app.route('/api/games/<game_id>', strict_slashes=False)
def api_game_detail(game_id):
    db  = get_db()
    row = db.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "Partie introuvable"}), 404
    return jsonify(dict(row))

@app.route('/api/players/<username>', strict_slashes=False)
def api_player_detail(username):
    db = get_db()
    player = db.execute("SELECT * FROM players WHERE username = ?", (username,)).fetchone()
    if not player:
        db.close()
        return jsonify({"error": "Joueur introuvable"}), 404
    stats = db.execute("""
        SELECT COUNT(*) AS total,
            SUM(CASE WHEN white_username=? AND white_result='win' THEN 1
                     WHEN black_username=? AND black_result='win' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN white_result IN ('agreed','stalemate','repetition','timevsinsufficient','50move','insufficient') THEN 1 ELSE 0 END) AS draws
        FROM games WHERE white_username=? OR black_username=?
    """, (username, username, username, username)).fetchone()
    tc = db.execute("""
        SELECT time_class, COUNT(*) as cnt
        FROM games WHERE white_username=? OR black_username=?
        GROUP BY time_class
    """, (username, username)).fetchall()
    tc_map = {row["time_class"]: row["cnt"] for row in tc}
    db.close()
    country = None
    try:
        import urllib.request as _ur, json as _j
        req = _ur.Request(dict(player)["api_id"], headers={"User-Agent": "ChessArchive/1.0"})
        with _ur.urlopen(req, timeout=3) as r:
            data = _j.loads(r.read())
            country_url = data.get("country", "")
            if country_url:
                country = country_url.split("/")[-1]
    except Exception:
        pass
    return jsonify({
        "player": dict(player),
        "stats": {
            "total":  stats["total"]  or 0,
            "wins":   stats["wins"]   or 0,
            "draws":  stats["draws"]  or 0,
            "losses": (stats["total"] or 0) - (stats["wins"] or 0) - (stats["draws"] or 0),
            "bullet": tc_map.get("bullet", 0),
            "blitz":  tc_map.get("blitz",  0),
            "rapid":  tc_map.get("rapid",  0),
            "country": country,
        }
    })

def log_stream():
    process = subprocess.Popen(
        ['journalctl', '-u', LOG_SERVICE_NAME, '-f', '-n', str(LOG_LINES)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    try:
        while True:
            line = process.stdout.readline()
            if not line: break
            yield f"data: {line}\n\n"
    finally:
        process.terminate()

@app.route('/api/logs/')
def stream_logs():
    return Response(log_stream(), mimetype='text/event-stream', headers={'X-Accel-Buffering': 'no'})

@app.route('/api/logs/last/')
def get_last_logs():
    try:
        logs = subprocess.check_output(['journalctl', '-u', LOG_SERVICE_NAME, '-n', str(LOG_LINES)], universal_newlines=True)
        return Response(logs, mimetype="text/plain")
    except subprocess.CalledProcessError as e:
        return Response(f"Erreur: {e}", status=500, mimetype="text/plain")

@app.route('/api/update/', methods=['GET'])
def update_players():
    def background_task():
        import logging
        log = logging.getLogger('chess-scraping')
        try:
            log.info("Mise à jour des joueurs...")
            get_players.main()
        except Exception as e:
            log.error(f"get_players: {e}", exc_info=True)
        try:
            log.info("Scraping des parties...")
            get_games.main()
            log.info("Scraping terminé")
        except Exception as e:
            log.error(f"get_games: {e}", exc_info=True)
    Thread(target=background_task).start()
    return "Mise à jour lancée en arrière-plan", 202

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=12346, debug=False, threaded=True)
