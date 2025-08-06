from flask import Flask
import get_players
import get_games
import others

app = Flask(__name__)

@app.route('/api/update/players', methods=['GET'])
def update_players():
    return get_players.main()

@app.route('/api/update/games', methods=['GET'])
def update_games():
    return get_games.main()

@app.route('/api/get/games', methods=['GET'])
def get_games():
    return others.count_games()

@app.route('/api/get/players', methods=['GET'])
def get_players():
    return others.count_players()[0]

if __name__ == '__main__':
    app.run(debug=True, port=12346)