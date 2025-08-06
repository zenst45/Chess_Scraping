import os

def count_games():
    with open("metadata.json", "r", encoding="utf-8") as f:
        nb_lignes = sum(1 for _ in f)-5-count_players()[1]
    return f"Nombre de parties : {nb_lignes}"

def count_players():
    dossier = "players/"
    nb_fichiers = len([f for f in os.listdir(dossier) if os.path.isfile(os.path.join(dossier, f))])
    return f"Nombre de joueurs : {nb_fichiers}", nb_fichiers
