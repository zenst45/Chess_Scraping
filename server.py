from flask import Flask
import get_players
import get_games
import others
app = Flask(__name__)

@app.route('/api/update/', methods=['GET'])
def update_players():
    get_players.main()
    get_games.main()

@app.route('/api/get/', methods=['GET'])
def get():
    return [others.count_players()[0], others.count_games()]

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=12346)