from threading import Thread
from flask import Flask, Response, send_file, jsonify, request
from flask_cors import CORS
import get_players
import get_games
import subprocess
import os

from database import get_conn, init_db

app = Flask(__name__)
CORS(app)

LOG_SERVICE_NAME = "chess-scraping"
LOG_LINES = 500

# Init DB au démarrage
init_db()

# ── Frontend ────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_file('index.html')

# ── Stats globales ──────────────────────────────────────────────
@app.route('/api/get/')
def get_stats():
    conn = get_conn()
    nb_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    nb_games   = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    conn.close()
    return jsonify({
        "players":       f"Nombre de joueurs : {nb_players}",
        "games":         f"Nombre de parties : {nb_games}",
        "players_count": nb_players,
        "games_count":   nb_games,
    })

# ── Liste des joueurs (paginée) ─────────────────────────────────
@app.route('/api/players/')
def list_players():
    page     = max(0, int(request.args.get('page', 0)))
    per_page = min(100, int(request.args.get('per_page', 50)))
    search   = request.args.get('search', '').strip()
    title    = request.args.get('title', '').strip()
    sort     = request.args.get('sort', 'username')

    sort_map = {
        'username':   'p.username ASC',
        'games_desc': 'games_count DESC',
        'games_asc':  'games_count ASC',
    }
    order = sort_map.get(sort, 'p.username ASC')

    where_clauses, params = [], []
    if search:
        where_clauses.append("p.username LIKE ?")
        params.append(f'%{search}%')
    if title:
        where_clauses.append("p.title = ?")
        params.append(title)
    where = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    conn = get_conn()
    total = conn.execute(f"SELECT COUNT(*) FROM players p {where}", params).fetchone()[0]
    rows  = conn.execute(f"""
        SELECT p.player_id, p.username, p.title, p.avatar, p.api_id, p.country,
               COUNT(pg.game_id) AS games_count
        FROM players p
        LEFT JOIN player_games pg ON pg.username = p.username
        {where}
        GROUP BY p.username
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """, params + [per_page, page * per_page]).fetchall()
    conn.close()

    return jsonify({
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "players": [dict(r) for r in rows],
    })

# ── Détail d'un joueur ──────────────────────────────────────────
@app.route('/api/players/<username>/')
def player_detail(username):
    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
    if not player:
        conn.close()
        return jsonify({"error": "Joueur introuvable"}), 404

    stats = conn.execute("""
        SELECT COUNT(*) AS total,
            SUM(CASE WHEN (white_id=? AND white_result='win') OR (black_id=? AND black_result='win') THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN white_result IN ('agreed','stalemate','repetition','timevsinsufficient','50move') THEN 1 ELSE 0 END) AS draws,
            SUM(CASE WHEN time_class='bullet'    THEN 1 ELSE 0 END) AS bullet,
            SUM(CASE WHEN time_class='blitz'     THEN 1 ELSE 0 END) AS blitz,
            SUM(CASE WHEN time_class='rapid'     THEN 1 ELSE 0 END) AS rapid,
            SUM(CASE WHEN time_class='daily'     THEN 1 ELSE 0 END) AS daily
        FROM games WHERE white_id=? OR black_id=?
    """, (username, username, username, username)).fetchone()
    conn.close()

    return jsonify({**dict(player), **dict(stats)})

# ── Parties d'un joueur (paginées) ─────────────────────────────
@app.route('/api/players/<username>/games/')
def player_games(username):
    page     = max(0, int(request.args.get('page', 0)))
    per_page = min(100, int(request.args.get('per_page', 50)))

    conn  = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM player_games WHERE username=?", (username,)).fetchone()[0]
    rows  = conn.execute("""
        SELECT g.* FROM games g
        JOIN player_games pg ON pg.game_id = g.game_id
        WHERE pg.username=?
        ORDER BY g.end_time DESC
        LIMIT ? OFFSET ?
    """, (username, per_page, page * per_page)).fetchall()
    conn.close()

    return jsonify({
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "games": [dict(r) for r in rows],
    })

# ── Liste des parties (paginée, filtrée) ───────────────────────
@app.route('/api/games/')
def list_games():
    page       = max(0, int(request.args.get('page', 0)))
    per_page   = min(100, int(request.args.get('per_page', 50)))
    search     = request.args.get('search', '').strip()
    result     = request.args.get('result', '').strip()
    time_class = request.args.get('time_class', '').strip()
    rated      = request.args.get('rated', '').strip()

    where_clauses, params = [], []
    if search:
        where_clauses.append("(white_id LIKE ? OR black_id LIKE ? OR opening LIKE ?)")
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if time_class:
        where_clauses.append("time_class=?")
        params.append(time_class)
    if rated == 'true':
        where_clauses.append("rated=1")
    elif rated == 'false':
        where_clauses.append("rated=0")
    if result == 'win':
        where_clauses.append("white_result='win'")
    elif result == 'loss':
        where_clauses.append("black_result='win'")
    elif result == 'draw':
        where_clauses.append("white_result IN ('agreed','stalemate','repetition','timevsinsufficient','50move')")

    where = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    conn  = get_conn()
    total = conn.execute(f"SELECT COUNT(*) FROM games {where}", params).fetchone()[0]
    rows  = conn.execute(
        f"SELECT game_id, url, time_control, time_class, rated, end_time, "
        f"white_id, white_rating, white_result, black_id, black_rating, black_result, eco, opening "
        f"FROM games {where} ORDER BY end_time DESC LIMIT ? OFFSET ?",
        params + [per_page, page * per_page]
    ).fetchall()
    conn.close()

    return jsonify({
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "games": [dict(r) for r in rows],
    })

# ── Détail d'une partie (avec PGN) ─────────────────────────────
@app.route('/api/games/<game_id>/')
def game_detail(game_id):
    conn = get_conn()
    game = conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone()
    conn.close()
    if not game:
        return jsonify({"error": "Partie introuvable"}), 404
    return jsonify(dict(game))

# ── Logs ────────────────────────────────────────────────────────
def log_stream():
    process = subprocess.Popen(
        ['journalctl', '-u', LOG_SERVICE_NAME, '-f', '-n', str(LOG_LINES)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            yield f"data: {line}\n\n"
    finally:
        process.terminate()

@app.route('/api/logs/')
def stream_logs():
    return Response(log_stream(), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no'})

@app.route('/api/logs/last/')
def get_last_logs():
    try:
        logs = subprocess.check_output(
            ['journalctl', '-u', LOG_SERVICE_NAME, '-n', str(LOG_LINES)],
            universal_newlines=True
        )
        return Response(logs, mimetype="text/plain")
    except subprocess.CalledProcessError as e:
        return Response(f"Erreur: {e}", status=500, mimetype="text/plain")

# ── Mise à jour ─────────────────────────────────────────────────
@app.route('/api/update/', methods=['GET'])
def update_players_route():
    def background_task():
        get_players.main()
        get_games.main()
    Thread(target=background_task).start()
    return "Mise à jour lancée en arrière-plan", 202

# ── Démarrage ───────────────────────────────────────────────────
if __name__ == '__main__':
    Thread(target=lambda: [get_players.main()]).start()
    app.run(host="0.0.0.0", port=12346, debug=False, threaded=True)