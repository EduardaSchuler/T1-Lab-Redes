"""Cliente de medicao C1 x C2 (Parte 2 do T1).

Executar no dispositivo B, apontando para o servidor do dispositivo A:

    python medir.py --host 192.168.0.11 --port 8080 --path /a.txt --modo c1
    python medir.py --host 192.168.0.11 --port 8080 --path /a.txt --modo c2

C1: uma conexao nova por requisicao (Connection: close).
C2: uma unica conexao persistente para todas as requisicoes.

Rode um modo por vez com o Wireshark capturando (filtro tcp.port == 8080)
e salve cada captura separadamente (capturas/c1.pcapng e capturas/c2.pcapng).
O tempo impresso aqui e o tempo total do cliente; handshakes, pacotes e bytes
totais devem ser extraidos da captura.
"""

import argparse
import socket
import time


def montar_requisicao(host, caminho, fechar):
    linhas = [
        "GET %s HTTP/1.1" % caminho,
        "Host: %s" % host,
        "Connection: %s" % ("close" if fechar else "keep-alive"),
    ]
    return ("\r\n".join(linhas) + "\r\n\r\n").encode("ascii")


def ler_resposta(conexao, buffer):
    """Le uma resposta completa usando Content-Length. Retorna (corpo, resto, bytes_lidos)."""
    while b"\r\n\r\n" not in buffer:
        pedaco = conexao.recv(4096)
        if not pedaco:
            raise ConnectionError("conexao fechada antes do fim do cabecalho")
        buffer += pedaco
    cabecalho, _, resto = buffer.partition(b"\r\n\r\n")
    tamanho = 0
    for linha in cabecalho.decode("iso-8859-1").split("\r\n")[1:]:
        nome, _, valor = linha.partition(":")
        if nome.lower() == "content-length":
            tamanho = int(valor.strip())
    while len(resto) < tamanho:
        pedaco = conexao.recv(4096)
        if not pedaco:
            raise ConnectionError("conexao fechada antes do fim do corpo")
        resto += pedaco
    status = cabecalho.split(b"\r\n")[0].decode("iso-8859-1")
    return status, resto[tamanho:], len(cabecalho) + 4 + tamanho


def c1(host, porta, caminho, n):
    total = 0
    for i in range(n):
        with socket.create_connection((host, porta)) as conexao:
            conexao.sendall(montar_requisicao(host, caminho, True))
            status, _, lidos = ler_resposta(conexao, b"")
            total += lidos
            print("  req %2d: %s" % (i + 1, status))
    return total


def c2(host, porta, caminho, n):
    total = 0
    with socket.create_connection((host, porta)) as conexao:
        buffer = b""
        for i in range(n):
            ultima = i == n - 1
            conexao.sendall(montar_requisicao(host, caminho, ultima))
            status, buffer, lidos = ler_resposta(conexao, buffer)
            total += lidos
            print("  req %2d: %s" % (i + 1, status))
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--path", default="/a.txt")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--modo", choices=("c1", "c2"), required=True)
    args = parser.parse_args()

    funcao = c1 if args.modo == "c1" else c2
    print("Modo %s: %d requisicoes a http://%s:%d%s" % (args.modo.upper(), args.n, args.host, args.port, args.path))
    inicio = time.perf_counter()
    bytes_http = funcao(args.host, args.port, args.path, args.n)
    duracao = time.perf_counter() - inicio
    print("Tempo total: %.1f ms" % (duracao * 1000))
    print("Bytes HTTP recebidos (cabecalho + corpo): %d" % bytes_http)


if __name__ == "__main__":
    main()
