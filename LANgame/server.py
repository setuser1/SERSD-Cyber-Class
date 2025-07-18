# ------------------ server.py ------------------
import socket
import threading
import pickle
import os
import json
from datetime import datetime
from litrpg_game import (
    Player, assign_quests, explore, use_item, allocate_stats,
    show_quests, visit_shop, revive_teammate, player_turn_done
)

HOST = '0.0.0.0'
PORT = 65432
MAX_PLAYERS = 4
SAVE_PREFIX = "autosave"

clients = []
players = []
lock = threading.Lock()
turn_index = 0

def save_game_state():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{SAVE_PREFIX}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump([p.to_dict() for p in players], f)
    saves = sorted([f for f in os.listdir() if f.startswith(SAVE_PREFIX) and f.endswith(".json")], key=os.path.getmtime, reverse=True)
    for old in saves[5:]:
        os.remove(old)

def load_latest_save():
    saves = sorted([f for f in os.listdir() if f.startswith(SAVE_PREFIX) and f.endswith(".json")], key=os.path.getmtime, reverse=True)
    if saves:
        with open(saves[0], "r") as f:
            for pdata in json.load(f):
                player = Player(pdata['name'], pdata['role'])
                player.from_dict(pdata)
                assign_quests(player)
                players.append(player)
        return True
    return False

def send_data(conn, data):
    try:
        conn.sendall(pickle.dumps(data))
    except:
        pass

def recv_data(conn):
    try:
        data = conn.recv(8192)
        if not data:
            return None
        return pickle.loads(data)
    except:
        return None

def handle_client(conn, addr):
    global turn_index
    print(f"[CONNECTED] {addr}")
    send_data(conn, {"type": "info", "msg": "Connected to server. Send your character."})

    player_data = recv_data(conn)
    if not player_data:
        conn.close()
        return

    player = Player(player_data['name'], player_data['role'])
    player.from_dict(player_data)
    assign_quests(player)

    with lock:
        players.append(player)
        clients.append((conn, player))

    while True:
        with lock:
            if players[turn_index] != player:
                continue

        send_data(conn, {
            "type": "turn",
            "player": player.to_dict(),
            "players": [p.to_dict() for p in players],
            "msg": f"It is your turn, {player.name}!"
        })

        action = recv_data(conn)
        if not action:
            with lock:
                idx = players.index(player)
                players.pop(idx)
                clients.pop(idx)
                turn_index %= max(1, len(players))
            break

        command = action.get("command")
        log = []

        if command == "explore":
            log = explore(player, players)
        elif command == "use_item":
            item = action.get("item")
            log = use_item(player, item, players)
        elif command == "allocate_stats":
            log = allocate_stats(player)
        elif command == "quests":
            log = show_quests(player)
        elif command == "shop":
            log = visit_shop(player)
        elif command == "revive":
            log = revive_teammate(player, players)
        elif command == "quit":
            send_data(conn, {"type": "info", "msg": "Thanks for playing!"})
            log.append(f"{player.name} has left the game.")
            print(f"[DISCONNECTED] {player.name} has left the game.")
            conn.close()
            with lock:
                idx = players.index(player)
                players.pop(idx)
                clients.pop(idx)
                turn_index %= max(1, len(players))
        # Notify remaining players
                for c, _ in clients:
                    send_data(c, {
                        "type": "log",
                        "log": log,
                        "players": [p.to_dict() for p in players]
                    })
            break
        else:
            log = ["Unknown command."]

        log += player_turn_done()

        with lock:
            for c, _ in clients:
                send_data(c, {
                    "type": "log",
                    "log": log,
                    "players": [p.to_dict() for p in players]
                })
            turn_index = (turn_index + 1) % len(players)
            save_game_state()

    conn.close()

def start_server():
    print(f"[STARTING] Server listening on {HOST}:{PORT}")
    load_latest_save()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        while True:
            conn, addr = s.accept()
            conn.settimeout(60)
            if len(clients) >= MAX_PLAYERS:
                conn.sendall(pickle.dumps({"type": "error", "msg": "Server full."}))
                conn.close()
                continue
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()

if __name__ == "__main__":
    start_server()
