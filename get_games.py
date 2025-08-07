import os
import json
import requests
from tqdm import tqdm
import get_players
import logging
from datetime import datetime
import sys

# Configuration
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
}

# Détection du contexte systemd
IS_SYSTEMD = 'journald' in os.environ.get('JOURNAL_STREAM', '')

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)
logger = logging.getLogger('chess-scraping')

# Configuration des dossiers
PLAYERS_DIR = 'players'
METADATA_FILE = 'metadata.json'
os.makedirs(PLAYERS_DIR, exist_ok=True)

class SystemdCompatibleTqdm(tqdm):
    """Version de tqdm compatible avec systemd"""
    def __init__(self, *args, **kwargs):
        kwargs.update({
            'disable': IS_SYSTEMD,
            'bar_format': '{desc}: {percentage:.1f}%|{bar}| {n_fmt}/{total_fmt}'
        })
        super().__init__(*args, **kwargs)

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
    username = player.get('username', 'inconnu')

    try:
        logger.info(f"Début du traitement pour {username}")
        urls = requests.get(player["@id"]+"/games/archives", headers=HEADERS, timeout=10).json().get("archives", [])
        logger.info(f"{username}: {len(urls)} mois à traiter")

        for url in SystemdCompatibleTqdm(urls, desc=f"{username[:10]}", leave=False):
            try:
                month_games = requests.get(url, headers=HEADERS, timeout=10).json().get("games", [])
                new_count = sum(1 for game in month_games if game["url"].split('/')[-1] not in existing_ids)

                if new_count > 0:
                    logger.debug(f"{username}: {new_count} nouvelles parties dans {url.split('/')[-1]}")

                for game in month_games:
                    game_id = game["url"].split('/')[-1]
                    if game_id not in existing_ids:
                        new_games.append(game)

            except Exception as e:
                logger.error(f"Erreur sur le mois {url} pour {username}: {str(e)}")
                continue

        logger.info(f"{username}: {len(new_games)} nouvelles parties trouvées")

    except Exception as e:
        logger.error(f"Erreur majeure pour {username}: {str(e)}", exc_info=True)

    return new_games

def process_players(players_list):
    """Traite la liste des joueurs"""
    init_metadata()
    metadata = load_metadata()
    existing_ids = set(metadata["ids"])

    logger.info(f"Début du traitement de {len(players_list)} joueurs")
    start_time = datetime.now()

    progress = SystemdCompatibleTqdm(players_list, desc="Traitement global")
    for player in progress:
        username = player["username"]

        if IS_SYSTEMD and progress.n % 10 == 0:
            logger.info(f"Progression: {progress.n}/{len(players_list)} joueurs traités")

        try:
            new_games = fetch_player_games(player, existing_ids)

            if new_games:
                player_file = get_player_file(username)

                # Charger/initialiser
                if os.path.exists(player_file):
                    with open(player_file, 'r') as f:
                        player_data = json.load(f)
                else:
                    player_data = {
                        "player_info": player,
                        "games": [],
                        "game_ids": []
                    }

                # Mise à jour
                player_data["games"].extend(new_games)
                player_data["game_ids"].extend(g["url"].split('/')[-1] for g in new_games)

                # Sauvegarde
                with open(player_file, 'w') as f:
                    json.dump(player_data, f, indent=2)

                # Metadata
                existing_ids.update(g["url"].split('/')[-1] for g in new_games)
                if username not in metadata["usernames"]:
                    metadata["usernames"].append(username)

                logger.debug(f"{username}: {len(new_games)} parties sauvegardées")

        except Exception as e:
            logger.error(f"Erreur critique sur {username}: {str(e)}", exc_info=True)
            continue

    # Sauvegarde finale metadata
    metadata["ids"] = list(existing_ids)
    save_metadata(metadata)

    duration = datetime.now() - start_time
    logger.info(f"Traitement terminé en {duration}. {len(existing_ids)} parties au total")

def main():
    """Point d'entrée principal"""
    # Charger la liste des joueurs à traiter
    with open('top_players.json', 'r', encoding='utf-8') as f:
        players = json.load(f)["players"]

    # Lancer le traitement
    process_players(players)
    logger.info("Traitement terminé avec succès !")

if __name__ == "__main__":
    main()