import requests
import json
import get_games

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'}
    with open('top_players.json', 'r', encoding='utf-8') as f:
        players = json.load(f)

    leaderboards = requests.get("https://api.chess.com/pub/leaderboards", headers=headers).json()
    # Scroll des leaderboards
    for leaderboard in leaderboards.values():
        # Scroll des joueurs
        for player in leaderboard:
            if player["player_id"] not in players["ids"]:
                players["players"].append(player)
                players["ids"].append(player["player_id"])

    gms = requests.get("https://api.chess.com/pub/titled/GM", headers=headers).json()
    print(len(gms["players"]))
    i = 0
    for player in gms["players"]:
        i += 1
        print(i)
        player_id = requests.get(f"https://api.chess.com/pub/player/{player}", headers=headers).json()["player_id"]
        if player_id not in players["ids"]:
            players["players"].append(player)
            players["ids"].append(player_id)

    with open('top_players.json', 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)
    get_games.main()