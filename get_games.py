import os
import json
import requests
from tqdm import tqdm

# Configuration
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
}

PLAYERS_DIR = 'players'
METADATA_FILE = 'metadata.json'
os.makedirs(PLAYERS_DIR, exist_ok=True)

def init_metadata():
    """Initialise les métadonnées si elles n'existent pas"""
    if not os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'w') as f:
            json.dump({"ids": [], "usernames": []}, f)

def load_metadata():
    """Charge les métadonnées existantes"""
    with open(METADATA_FILE, 'r') as f:
        return json.load(f)

def save_metadata(metadata):
    """Sauvegarde les métadonnées"""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_player_file(username):
    """Retourne le chemin du fichier d'un joueur"""
    return os.path.join(PLAYERS_DIR, f"{username}.json")

def fetch_player_games(player, existing_ids):
    """Récupère les nouvelles parties d'un joueur"""
    new_games = []
    try:
        urls = requests.get(player["@id"]+"/games/archives", headers=HEADERS, timeout=10).json().get("archives", [])
        for url in urls:
            month_games = requests.get(url, headers=HEADERS, timeout=10).json().get("games", [])
            for game in month_games:
                game_id = game["url"].split('/')[-1]
                if game_id not in existing_ids:
                    new_games.append(game)
    except Exception as e:
        print(f"\nErreur pour {player.get('username')}: {str(e)}")
    return new_games

def process_players(players_list):
    init_metadata()
    metadata = load_metadata()
    existing_ids = set(metadata["ids"])

    for player in tqdm(players_list, desc="Traitement des joueurs"):
        username = player["username"]
        player_file = get_player_file(username)

        # Charger/initialiser les données du joueur
        if os.path.exists(player_file):
            with open(player_file, 'r') as f:
                player_data = json.load(f)
        else:
            player_data = {
                "player_info": player,
                "games": [],
                "game_ids": []
            }

        # Récupérer les nouvelles parties
        new_games = fetch_player_games(player, existing_ids)

        # Mettre à jour les données
        for game in new_games:
            game_id = game["url"].split('/')[-1]
            player_data["games"].append(game)
            player_data["game_ids"].append(game_id)
            existing_ids.add(game_id)

        # Sauvegarder le joueur
        with open(player_file, 'w') as f:
            json.dump(player_data, f, indent=2)

        # Mettre à jour ET sauvegarder les métadonnées à chaque joueur
        if username not in metadata["usernames"]:
            metadata["usernames"].append(username)

        metadata["ids"] = list(existing_ids)  # Mise à jour des IDs
        save_metadata(metadata)  # <-- SAUVEGARDE SYSTÉMATIQUE

    print("\nTraitement terminé !")

def main():
    # Charger la liste des joueurs à traiter
    with open('top_players.json', 'r', encoding='utf-8') as f:
        players = json.load(f)["players"]

    # Lancer le traitement
    process_players(players)
    print("\nTraitement terminé avec succès !")

def build_full_export():
    metadata = load_metadata()
    full_data = {
        "ids": metadata["ids"],
        "by_username": {}
    }

    for username in metadata["usernames"]:
        with open(get_player_file(username), 'r') as f:
            full_data["by_username"][username] = json.load(f)

    with open('full_export.json', 'w') as f:
        json.dump(full_data, f, indent=2)

if __name__ == "__main__":
    main()