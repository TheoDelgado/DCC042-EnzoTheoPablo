import socket

def main():
    host = 'localhost'
    porta = 12345

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        cliente.connect((host, porta))
        dados = cliente.recv(1024)
        print("Conectado ao servidor.")
        print(dados.decode())
        try:
            while True:
                mensagem = input("Digite algo: ")
                if mensagem.lower() == 'sair':
                    break
                cliente.sendall(mensagem.encode())
                dados = cliente.recv(1024)
                print("Recebido:", dados.decode())
        except KeyboardInterrupt:
            pass
        print("Conexão encerrada.")

if __name__ == "__main__":
    main()
