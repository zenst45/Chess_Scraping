from threading import Thread
from flask import Flask
import get_players
import get_games

app = Flask(__name__)

@app.route('/api/update/', methods=['GET'])
def update_players():
    # Lancer les tâches longues dans un thread séparé
    def background_task():
        get_players.main()
        get_games.main()

    Thread(target=background_task).start()

    return "Mise à jour lancée en arrière-plan", 202  # Code 202 = Accepted

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12346, debug=False)