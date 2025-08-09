import requests
import json
import others
import logging
import os

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('chess-scraping-players')

def initialize_players_file():
    """Crée le fichier avec une structure vide si il n'existe pas"""
    if not os.path.exists('top_players.json'):
        with open('top_players.json', 'w', encoding='utf-8') as f:
            json.dump({"players": [], "ids": []}, f, ensure_ascii=False, indent=2)
        logger.info("Fichier top_players.json créé avec une structure vide")

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'}

    # Initialiser le fichier si nécessaire
    initialize_players_file()

    try:
        with open('top_players.json', 'r', encoding='utf-8') as f:
            players = json.load(f)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier: {str(e)}")
        return False

    try:
        # Récupérer les leaderboards
        leaderboards = requests.get("https://api.chess.com/pub/leaderboards", headers=headers).json()
        new_players = 0

        for leaderboard in leaderboards.values():
            for player in leaderboard:
                if player["player_id"] not in players["ids"]:
                    players["players"].append(player)
                    players["ids"].append(player["player_id"])
                    new_players += 1

        logger.info(f"Ajouté {new_players} joueurs depuis les leaderboards")

        # Récupérer les GMs
        gms = requests.get("https://api.chess.com/pub/titled/GM", headers=headers).json()
        new_gms = 0

        for username in gms["players"]:
            try:
                player_info = requests.get(f"https://api.chess.com/pub/player/{username}", headers=headers).json()
                player_id = player_info["player_id"]

                if player_id not in players["ids"]:
                    players["players"].append({
                        "username": username,
                        "player_id": player_id,
                        "title": "GM",
                        "@id": f"https://api.chess.com/pub/player/{username}"
                    })
                    players["ids"].append(player_id)
                    new_gms += 1

            except Exception as e:
                logger.error(f"Erreur avec le GM {username}: {str(e)}")
                continue

        logger.info(f"Ajouté {new_gms} nouveaux GMs")

        # Sauvegarder
        with open('top_players.json', 'w', encoding='utf-8') as f:
            json.dump(players, f, ensure_ascii=False, indent=2)

        logger.info(f"Total joueurs: {len(players['players'])}")

        # Lancer la récupération des parties
        others.scan_games()
        return True

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}", exc_info=True)
        return False