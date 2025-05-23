import socket
import threading

def atender_cliente(socket_cliente, endereco):
    print(f"[+] Conectado a {endereco}")
    with socket_cliente:
        while True:
            dados = socket_cliente.recv(1024)
            if not dados:
                break
            socket_cliente.sendall(dados)
    print(f"[-] Conexão encerrada com {endereco}")

def main():
    host = 'localhost'
    porta = 12345
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((host, porta))
    servidor.listen()

    print("[*] Servidor escutando...")

    try:
        while True:
            socket_cliente, endereco = servidor.accept()
            thread = threading.Thread(target=atender_cliente, args=(socket_cliente, endereco))
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Encerrando servidor.")
    finally:
        servidor.close()

if __name__ == "__main__":
    main()