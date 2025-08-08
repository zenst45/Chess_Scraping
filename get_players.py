import requests
import json
import get_games

def main():
    with open('top_players.json', 'r', encoding='utf-8') as f:
        players = json.load(f)
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
    }
    leaderboards = requests.get("https://api.chess.com/pub/leaderboards", headers=headers).json()
    # with open('data.json', 'r', encoding='utf-8') as f:
    #     leaderboards = json.load(f)
    # print(leaderboards)

    # Scroll des leaderboards
    for leaderboard in leaderboards.values():
        # Scroll des joueurs
        for player in leaderboard:
            if player["player_id"] not in players["ids"]:
                players["players"].append(player)
                players["ids"].append(player["player_id"])

    top_countries = requests.get("https://api.chess.com/pub/leaderboards", headers=headers).json()

    with open('top_players.json', 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)
    get_games.main()
