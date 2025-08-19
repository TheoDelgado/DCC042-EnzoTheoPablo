import socket
import threading
import sys
import os

HOST = "127.0.0.1"
PORT = 50007

players_state = {}   # {nome: progresso}
icons = ["🏃","🚗","🐢","🐇","🐙","🐉","🛸","🚀"]
track_length = 15    # será atualizado via LENGTH
current_word = None  # palavra atual deste cliente
my_name = None       # definido após WELCOME

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def draw_tracks():
    clear()
    print("🏁 Corrida das Palavras 🏁\n")
    # Desenha pistas
    # Garante ordem estável de exibição
    for i, name in enumerate(players_state.keys()):
        prog = players_state[name]
        icon = icons[i % len(icons)]
        filled = "-" * min(prog, track_length)
        empty = "-" * max(track_length - prog, 0)
        track = f"{filled}{icon}{empty}"
        label = f"{name} (eu)" if name == my_name else name
        print(f"{label:12}: {track} ({prog}/{track_length})")

    print("\n👉 Sua palavra: " + (current_word if current_word else "aguarde..."))
    print("Digite exatamente a palavra para avançar.\n")

def recv_loop(sock):
    global players_state, track_length, current_word, my_name
    file = sock.makefile("r", encoding="utf-8", newline="\n")
    for raw in file:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("PING "):
            nonce = line.split(" ", 1)[1]
            sock.sendall(f"PONG {nonce}\n".encode("utf-8"))

        elif line.startswith("WELCOME "):
            my_name = line[8:].strip()
            print(f"[SERVER] Bem-vindo, seu nome é {my_name}")

        elif line.startswith("LENGTH "):
            try:
                track_length = int(line.split(" ", 1)[1])
            except:
                track_length = 15
            draw_tracks()

        elif line.startswith("WORD "):
            current_word = line[5:]
            draw_tracks()

        elif line.startswith("STATE "):
            state_str = line[6:]
            new_state = {}
            for entry in state_str.split(";"):
                if not entry:
                    continue
                name, prog = entry.split(":")
                new_state[name] = int(prog)
            players_state = new_state
            draw_tracks()

        elif line.startswith("VICTORY "):
            winner = line[8:]
            print(f"\n🏆 Vitória do jogador {winner}")
        elif line == "END":
            print("\n[JOGO] Partida encerrada.")
            break
        elif line == "START":
            print("[JOGO] Partida iniciada!")
        elif line.startswith("INFO "):
            print(f"[INFO] {line[5:]}")
        elif line.startswith("LOBBY "):
            print(f"[SERVER] Jogadores na sala: {line[6:]}")
        else:
            # outras mensagens, apenas mostra ou ignora
            print(f"[SERVIDOR] {line}")

    print("[CLIENTE] Conexão encerrada pelo servidor.")
    sys.exit(0)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    threading.Thread(target=recv_loop, args=(sock,), daemon=True).start()

    name = input("Digite seu nome: ")
    sock.sendall(f"JOIN {name}\n".encode("utf-8"))

    while True:
        try:
            word = input("> Digite palavra: ")
            if not word:
                continue
            sock.sendall(f"WORD {word}\n".encode("utf-8"))
        except (EOFError, KeyboardInterrupt):
            break

    sock.close()

if __name__ == "__main__":
    main()
