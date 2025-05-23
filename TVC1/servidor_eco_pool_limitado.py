import socket
import threading
from queue import Queue

MAXIMO_THREADS = 10

fila_clientes = Queue()
clientes_ativos = 0
trava = threading.Lock()

def atender_cliente(fila):
    global clientes_ativos
    while True:
        socket_cliente, endereco = fila.get()
        if socket_cliente is None:
            break

        with trava:
            clientes_ativos += 1

        print(f"[+] {threading.current_thread().name} atendendo {endereco}")
        with socket_cliente:
            try:
                while True:
                    dados = socket_cliente.recv(1024)
                    if not dados:
                        break
                    socket_cliente.sendall(dados)
            finally:
                with trava:
                    clientes_ativos -= 1
                print(f"[-] {threading.current_thread().name} liberando {endereco}")
                fila.task_done()

def main():
    host = 'localhost'
    porta = 12345
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((host, porta))
    servidor.listen()

    print("[*] Servidor com pool de 10 threads escutando...")

    threads = []
    for _ in range(MAXIMO_THREADS):
        t = threading.Thread(target=atender_cliente, args=(fila_clientes,), daemon=True)
        t.start()
        threads.append(t)

    try:
        while True:
            socket_cliente, endereco = servidor.accept()

            with trava:
                if clientes_ativos >= MAXIMO_THREADS:
                    print(f"[!] Conexão recusada de {endereco} (servidor ocupado)")
                    try:
                        socket_cliente.sendall(b"Servidor ocupado. Tente novamente mais tarde.\n")
                    except:
                        pass
                    socket_cliente.close()
                    continue
                else:
                   socket_cliente.sendall(b"Conectado.\n")


            fila_clientes.put((socket_cliente, endereco))
    except KeyboardInterrupt:
        print("\n[*] Encerrando servidor.")
    finally:
        servidor.close()

if __name__ == "__main__":
    main()
