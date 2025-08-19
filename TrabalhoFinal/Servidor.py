import socket
import threading
import time
import random
import sys

HOST = "0.0.0.0"
PORT = 50007

MIN_PLAYERS = 2
PING_ROUNDS = 5
PING_INTERVAL = 0.15
WORDS_COUNT = 15
ALL_WORDS = [
    "abacaxi","amizade","barco","cachorro","dado","elefante","floresta","girassol","hipopótamo","igreja",
    "janela","kilo","limão","macaco","nuvem","ocelote","praia","quadro","rosa","sol",
    "tigre","uva","violão","whisky","xadrez","yoga","zebra","alegria","bola","caderno",
    "doce","estrela","fogo","gato","história","ilha","jardim","kiwi","livro","montanha",
    "noite","olho","pato","queijo","rio","sapo","tartaruga","urso","vela","xadrezinho",
    "yeti","zoeira","abóbora","banho","campo","dente","escola","ferro","gelo","horizonte",
    "inseto","jornal","kanguru","linha","música","navio","orvalho","peixe","quintal","raiz",
    "saudade","tempo","universo","viagem","vento","xilofone","yakissoba","zíper","abacate","beijo",
    "carro","dinheiro","escada","felicidade","gelo","horta","imaginação","jogo","ketchup","lua",
    "mundo","ninho","oceano","papel","quietude","relógio","sorriso","terra","união"
]

class Player:
    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self.name = None
        self.progress = 0
        self.rtts = []
        self.rtt_avg_ms = None
        self.comp_delay_ms = 0
        self.alive = True

    def send(self, msg: str):
        try:
            self.sock.sendall((msg + "\n").encode("utf-8"))
        except:
            self.alive = False

class WordRaceServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients_lock = threading.Lock()
        self.players: list[Player] = []
        self.words: list[str] = []
        self.started = False
        self.ended = False
        self.pending_pings = {}  # (player, nonce) -> send_time

    def start(self):
        self.srv.bind((self.host, self.port))
        self.srv.listen()
        print(f"[SERVIDOR] Ouvindo em {self.host}:{self.port}")

        threading.Thread(target=self.accept_loop, daemon=True).start()

        print(f"[SERVIDOR] Aguarde jogadores... (mínimo {MIN_PLAYERS}). Pressione ENTER para iniciar.")
        input()
        with self.clients_lock:
            while len(self.players) < MIN_PLAYERS:
                print("[SERVIDOR] Jogadores insuficientes. Aguardando mais conexões...")
                time.sleep(1)
        self.begin_game()

        while not self.ended:
            time.sleep(0.5)
        print("[SERVIDOR] Encerrando.")
        self.srv.close()

    def accept_loop(self):
        while True:
            try:
                c, addr = self.srv.accept()
            except OSError:
                break
            p = Player(c, addr)
            threading.Thread(target=self.client_thread, args=(p,), daemon=True).start()

    def broadcast(self, msg: str):
        with self.clients_lock:
            for p in list(self.players):
                if p.alive:
                    p.send(msg)

    def client_thread(self, player: Player):
        file = player.sock.makefile("r", encoding="utf-8", newline="\n")
        try:
            player.send("INFO Bem-vindo! Envie: JOIN <seu_nome>")
            line = file.readline()
            if not line:
                player.alive = False
                return
            line = line.strip()
            if not line.startswith("JOIN "):
                player.send("INFO Protocolo: esperado JOIN <nome>")
                player.alive = False
                return
            name = line[5:].strip()
            if not name:
                player.send("INFO Nome inválido.")
                player.alive = False
                return
            player.name = self.unique_name(name)
            player.send(f"WELCOME {player.name}")
        except:
            player.alive = False
            return

        with self.clients_lock:
            self.players.append(player)
            lobby_count = len(self.players)
        self.broadcast(f"LOBBY {lobby_count}")
        print(f"[SERVIDOR] {player.name} conectado de {player.addr}.")

        while player.alive and not self.ended:
            try:
                line = file.readline()
                if not line:
                    player.alive = False
                    break
                line = line.strip()

                if line.startswith("WORD "):
                    word = line[5:].strip()
                    self.handle_word(player, word)

                elif line.startswith("PONG "):
                    nonce = line.split(" ", 1)[1]
                    now = time.perf_counter()
                    key = (player, nonce)
                    if key in self.pending_pings:
                        send_time = self.pending_pings.pop(key)
                        rtt = (now - send_time) * 1000.0
                        player.rtts.append(rtt)
                        print(f"[PING] {player.name} RTT {rtt:.1f} ms")

                else:
                    continue

            except:
                player.alive = False
                break

        with self.clients_lock:
            if player in self.players:
                self.players.remove(player)
        print(f"[SERVIDOR] {player.name} desconectou.")

    def unique_name(self, base: str) -> str:
        with self.clients_lock:
            names = {p.name for p in self.players if p.name}
        if base not in names:
            return base
        i = 2
        while f"{base}{i}" in names:
            i += 1
        return f"{base}{i}"

    def begin_game(self):
        with self.clients_lock:
            if self.started:
                return
            self.started = True
            self.words = random.sample(ALL_WORDS, k=WORDS_COUNT)
            print(f"[SERVIDOR] Palavras (ocultas aos clientes): {', '.join(self.words)}")

        # 1) Calibra RTT antes de começar
        self.calibrate_rtt()

        # 2) Calcula compensação e informa
        with self.clients_lock:
            if self.players:
                max_rtt = max(p.rtt_avg_ms or 0.0 for p in self.players)
                for p in self.players:
                    p.comp_delay_ms = max(0.0, max_rtt - (p.rtt_avg_ms or 0.0))
                    p.send(f"INFO RTT médio: {p.rtt_avg_ms:.1f} ms | compensação: {p.comp_delay_ms:.1f} ms")

        # 3) START, LENGTH e STATE inicial
        self.broadcast("START")
        self.broadcast(f"LENGTH {WORDS_COUNT}")
        self.push_state()

        # 4) Envia a PRIMEIRA palavra a cada jogador (individualmente)
        with self.clients_lock:
            for p in self.players:
                if p.alive and p.progress == 0:
                    p.send(f"WORD {self.words[0]}")

    def calibrate_rtt(self):
        with self.clients_lock:
            players = list(self.players)

        for round_i in range(PING_ROUNDS):
            nonce = f"{round_i}-{random.randint(1000,9999)}"
            for p in players:
                if not p.alive:
                    continue
                p.send(f"PING {nonce}")
                self.pending_pings[(p, nonce)] = time.perf_counter()
            time.sleep(PING_INTERVAL)

        with self.clients_lock:
            for p in players:
                if p.rtts:
                    p.rtt_avg_ms = sum(p.rtts) / len(p.rtts)
                else:
                    p.rtt_avg_ms = 0.0

    def handle_word(self, player: Player, word: str):
        if self.ended or not self.started:
            return
        delay = (player.comp_delay_ms or 0.0) / 1000.0
        if delay > 0:
            time.sleep(delay)

        expected = self.words[player.progress] if player.progress < len(self.words) else None
        if expected and word.strip().lower() == expected.lower():
            player.progress += 1
            self.broadcast(f"MOVE {player.name} {player.progress}")
            self.push_state()

            if player.progress < WORDS_COUNT:
                next_word = self.words[player.progress]
                player.send(f"WORD {next_word}")
            else:
                self.broadcast(f"VICTORY {player.name}")
                self.broadcast("END")
                self.ended = True
        else:
            player.send("INFO Palavra incorreta. Tente novamente.")

    def push_state(self):
        with self.clients_lock:
            items = [f"{p.name}:{p.progress}" for p in self.players]
        self.broadcast("STATE " + ";".join(items))


if __name__ == "__main__":
    try:
        server = WordRaceServer(HOST, PORT)
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Interrompido.")
        sys.exit(0)
