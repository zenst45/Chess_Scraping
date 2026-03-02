"""
migrate.py — Migration des fichiers JSON vers SQLite
Usage : python migrate.py [--players-dir players/] [--top-players top_players.json]
"""

import os
import json
import argparse
import time
from database import get_conn, init_db, upsert_player, upsert_game


def migrate(players_dir: str = 'players/', top_players_file: str = 'top_players.json'):
    print("=" * 60)
    print("  Migration JSON → SQLite")
    print("=" * 60)

    # Initialiser la DB
    print("\n[1/3] Initialisation de la base de données...")
    init_db()
    print("      ✓ Schéma créé")

    conn = get_conn()

    # ── Joueurs depuis top_players.json ──────────────────────────
    print("\n[2/3] Import des joueurs depuis top_players.json...")
    players_migrated = 0

    if os.path.exists(top_players_file):
        with open(top_players_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        players_list = data.get('players', [])
        total = len(players_list)

        for i, player in enumerate(players_list, 1):
            try:
                upsert_player(conn, player)
                players_migrated += 1
            except Exception as e:
                print(f"      ✗ Erreur joueur {player.get('username')}: {e}")

            if i % 500 == 0 or i == total:
                conn.commit()
                pct = i / total * 100
                bar = '█' * int(pct / 2) + '░' * (50 - int(pct / 2))
                print(f"\r      [{bar}] {i}/{total} ({pct:.0f}%)", end='', flush=True)

        conn.commit()
        print(f"\n      ✓ {players_migrated} joueurs importés")
    else:
        print(f"      ⚠ {top_players_file} introuvable, passage à l'étape suivante")

    # ── Parties depuis players/*.json ────────────────────────────
    print("\n[3/3] Import des parties depuis players/...")

    if not os.path.exists(players_dir):
        print(f"      ✗ Dossier '{players_dir}' introuvable")
        conn.close()
        return

    files = [f for f in os.listdir(players_dir) if f.endswith('.json')]
    total_files = len(files)
    total_games = 0
    total_new = 0
    start = time.time()

    for file_idx, filename in enumerate(files, 1):
        username = filename.replace('.json', '')
        filepath = os.path.join(players_dir, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Upsert du joueur si pas déjà fait
            player_info = data.get('player_info', {})
            if player_info:
                try:
                    upsert_player(conn, player_info)
                except Exception:
                    pass

            games = data.get('games', [])
            file_new = 0

            for game in games:
                try:
                    upsert_game(conn, game, username)
                    file_new += 1
                except Exception:
                    pass  # Doublon ou données corrompues

            conn.commit()
            total_games += len(games)
            total_new += file_new

            # Progression
            elapsed = time.time() - start
            rate = total_games / elapsed if elapsed > 0 else 0
            pct = file_idx / total_files * 100
            bar = '█' * int(pct / 2) + '░' * (50 - int(pct / 2))
            eta = (total_files - file_idx) * (elapsed / file_idx) if file_idx > 0 else 0
            print(
                f"\r      [{bar}] {file_idx}/{total_files} | "
                f"{total_games:,} parties | "
                f"{rate:.0f}/s | "
                f"ETA {int(eta//60)}m{int(eta%60):02d}s",
                end='', flush=True
            )

        except json.JSONDecodeError as e:
            print(f"\n      ✗ JSON corrompu : {filename} ({e})")
        except Exception as e:
            print(f"\n      ✗ Erreur sur {filename}: {e}")

    conn.close()

    elapsed = time.time() - start
    print(f"\n\n{'=' * 60}")
    print(f"  Migration terminée en {int(elapsed//60)}m{int(elapsed%60):02d}s")
    print(f"  Joueurs : {players_migrated:,}")
    print(f"  Parties : {total_games:,} lues, {total_new:,} insérées")
    print(f"  Base    : chess.db")
    print(f"{'=' * 60}\n")

    # Stats finales
    conn2 = get_conn()
    nb_games   = conn2.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    nb_players = conn2.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    db_size    = os.path.getsize('chess.db') / 1024 / 1024
    conn2.close()

    print(f"  Vérification DB :")
    print(f"    {nb_players:,} joueurs")
    print(f"    {nb_games:,} parties")
    print(f"    {db_size:.1f} MB sur disque\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migration JSON → SQLite')
    parser.add_argument('--players-dir',  default='players/')
    parser.add_argument('--top-players',  default='top_players.json')
    args = parser.parse_args()
    migrate(args.players_dir, args.top_players)