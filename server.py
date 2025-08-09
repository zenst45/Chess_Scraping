from threading import Thread
from flask import Flask, Response
import get_players
import get_games
import others
import subprocess

app = Flask(__name__)

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
    """Récupère les derniers logs (non-streaming)"""
    try:
        logs = subprocess.check_output(
            ['journalctl', '-u', LOG_SERVICE_NAME, '-n', str(LOG_LINES)],
            universal_newlines=True
        )
        return logs, 200
    except subprocess.CalledProcessError as e:
        return f"Erreur: {e}", 500

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
