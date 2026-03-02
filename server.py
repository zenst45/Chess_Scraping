from threading import Thread
from flask import Flask, Response, send_file, jsonify
from flask_cors import CORS
import get_players
import get_games
import others
import subprocess
import os
import json

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/players/')
def list_players():
    players = []
    for f in os.listdir('players/'):
        if f.endswith('.json'):
            with open(f'players/{f}') as fp:
                d = json.load(fp)
                p = d.get('player_info', {})
                p['games_count'] = len(d.get('games', []))
                p['games'] = d.get('games', [])[:50]  # last 50
                players.append(p)
    return {'players': players, 'games': [g for p in players for g in p.pop('games', [])]}

# Configuration des logs
LOG_SERVICE_NAME = "chess-scraping"
LOG_LINES = 500  # Nombre de lignes à retourner par défaut

def log_stream():
    """Générateur pour le streaming des logs"""
    process = subprocess.Popen(
        ['journalctl', '-u', LOG_SERVICE_NAME, '-f', '-n', str(LOG_LINES)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
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
    """Endpoint pour streamer les logs en temps réel"""
    return Response(
        log_stream(),
        mimetype='text/event-stream',
        headers={'X-Accel-Buffering': 'no'}
    )

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

@app.route('/api/update/', methods=['GET'])
def update_players():
    def background_task():
        get_players.main()
        get_games.main()

    Thread(target=background_task).start()
    return "Mise à jour lancée en arrière-plan", 202

@app.route('/api/get/', methods=['GET'])
def get():
    return {
        "players": others.count_players()[0],
        "games": others.count_games()
    }

if __name__ == '__main__':
    # Démarrer les tâches de fond au lancement
    Thread(target=lambda: [get_players.main()]).start()

    # Démarrer le serveur Flask
    app.run(
        host="0.0.0.0",
        port=12346,
        debug=False,
        threaded=True
    )