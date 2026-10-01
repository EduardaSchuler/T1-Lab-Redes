import argparse
import os
import socket
import threading
import time

DIAS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MESES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

STATUS_TEXT = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
}

TIPOS_MIME = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}

TAMANHO_MAXIMO_CABECALHO = 16 * 1024
TAMANHO_MAXIMO_CORPO = 1024 * 1024


class RequisicaoInvalida(Exception):
    pass


def data_http():
    t = time.gmtime()
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
        DIAS[t.tm_wday],
        t.tm_mday,
        MESES[t.tm_mon - 1],
        t.tm_year,
        t.tm_hour,
        t.tm_min,
        t.tm_sec,
    )


def decodificar_percent(texto):
    bruto = texto.encode("iso-8859-1")
    saida = bytearray()
    i = 0
    while i < len(bruto):
        byte = bruto[i]
        if byte != 0x25:
            saida.append(byte)
            i += 1
            continue
        par = bruto[i + 1 : i + 3]
        if len(par) != 2:
            raise RequisicaoInvalida()
        try:
            saida.append(int(par, 16))
        except ValueError:
            raise RequisicaoInvalida()
        i += 3
    try:
        resultado = saida.decode("utf-8")
    except UnicodeDecodeError:
        raise RequisicaoInvalida()
    if "\x00" in resultado:
        raise RequisicaoInvalida()
    return resultado


def resolver_arquivo(raiz, alvo):
    caminho = alvo.split("?")[0].split("#")[0]
    caminho = decodificar_percent(caminho).lstrip("/")
    completo = os.path.realpath(os.path.join(raiz, caminho))
    dentro_da_raiz = completo == raiz or completo.startswith(raiz + os.sep)
    return completo, dentro_da_raiz


def tipo_mime(caminho):
    extensao = os.path.splitext(caminho)[1].lower()
    return TIPOS_MIME.get(extensao, "application/octet-stream")


def montar_cabecalho(status, servidor, manter_conexao, timeout, tipo, tamanho, extras):
    linhas = [
        "HTTP/1.1 %d %s" % (status, STATUS_TEXT[status]),
        "Date: " + data_http(),
        "Server: " + servidor,
        "Content-Type: " + tipo,
        "Content-Length: %d" % tamanho,
    ]
    linhas += extras
    linhas.append("Connection: keep-alive" if manter_conexao else "Connection: close")
    if manter_conexao:
        linhas.append("Keep-Alive: timeout=%d" % timeout)
    return ("\r\n".join(linhas) + "\r\n\r\n").encode("iso-8859-1")


def enviar_arquivo(conexao, caminho, cabecalho, somente_cabecalho):
    conexao.sendall(cabecalho)
    if somente_cabecalho:
        return
    with open(caminho, "rb") as arquivo:
        while True:
            pedaco = arquivo.read(65536)
            if not pedaco:
                break
            conexao.sendall(pedaco)


def enviar_erro(conexao, cfg, status, manter_conexao, somente_cabecalho, extras=()):
    texto = "%d %s" % (status, STATUS_TEXT[status])
    corpo = ("<html><body><h1>%s</h1></body></html>" % texto).encode()
    cabecalho = montar_cabecalho(
        status,
        cfg.nome,
        manter_conexao,
        cfg.timeout,
        "text/html; charset=utf-8",
        len(corpo),
        list(extras),
    )
    conexao.sendall(cabecalho)
    if not somente_cabecalho:
        conexao.sendall(corpo)
    return status


def responder(conexao, cfg, metodo, alvo, manter_conexao):
    somente_cabecalho = metodo == "HEAD"

    if metodo not in ("GET", "HEAD"):
        return enviar_erro(
            conexao, cfg, 405, manter_conexao, False, ["Allow: GET, HEAD"]
        )

    try:
        caminho, dentro_da_raiz = resolver_arquivo(cfg.raiz, alvo)
    except RequisicaoInvalida:
        return enviar_erro(conexao, cfg, 400, manter_conexao, somente_cabecalho)

    if not dentro_da_raiz:
        return enviar_erro(conexao, cfg, 403, manter_conexao, somente_cabecalho)

    if os.path.isdir(caminho):
        caminho = os.path.join(caminho, "index.html")

    if not os.path.isfile(caminho):
        return enviar_erro(conexao, cfg, 404, manter_conexao, somente_cabecalho)

    tamanho = os.path.getsize(caminho)
    cabecalho = montar_cabecalho(
        200, cfg.nome, manter_conexao, cfg.timeout, tipo_mime(caminho), tamanho, []
    )
    enviar_arquivo(conexao, caminho, cabecalho, somente_cabecalho)
    return 200


def interpretar_requisicao(dados):
    try:
        texto = dados.decode("iso-8859-1")
    except UnicodeDecodeError:
        raise RequisicaoInvalida()

    linhas = texto.split("\r\n")
    partes = linhas[0].split(" ")
    if len(partes) != 3:
        raise RequisicaoInvalida()
    metodo, alvo, versao = partes
    if not metodo.isalpha() or versao not in ("HTTP/1.1", "HTTP/1.0"):
        raise RequisicaoInvalida()

    cabecalhos = {}
    for linha in linhas[1:]:
        if ":" not in linha:
            raise RequisicaoInvalida()
        nome, valor = linha.split(":", 1)
        cabecalhos[nome.strip().lower()] = valor.strip()

    return metodo, alvo, versao, cabecalhos


def tamanho_do_corpo(cabecalhos):
    try:
        tamanho = int(cabecalhos.get("content-length", "0"))
    except ValueError:
        raise RequisicaoInvalida()
    if tamanho < 0 or tamanho > TAMANHO_MAXIMO_CORPO:
        raise RequisicaoInvalida()
    return tamanho


def deve_fechar(cabecalhos):
    valor = cabecalhos.get("connection", "")
    return "close" in [token.strip().lower() for token in valor.split(",")]


def atender(conexao, endereco, cfg):
    conexao.settimeout(cfg.timeout)
    buffer = b""

    try:
        while True:
            while b"\r\n\r\n" not in buffer:
                if len(buffer) > TAMANHO_MAXIMO_CABECALHO:
                    enviar_erro(conexao, cfg, 400, False, False)
                    return
                recebido = conexao.recv(4096)
                if not recebido:
                    return
                buffer += recebido

            cabecalho_bruto, _, buffer = buffer.partition(b"\r\n\r\n")

            try:
                metodo, alvo, versao, cabecalhos = interpretar_requisicao(
                    cabecalho_bruto
                )
                tamanho_corpo = tamanho_do_corpo(cabecalhos)
            except RequisicaoInvalida:
                status = enviar_erro(conexao, cfg, 400, False, False)
                registrar_log(endereco, "requisicao invalida", status)
                return

            while len(buffer) < tamanho_corpo:
                recebido = conexao.recv(4096)
                if not recebido:
                    return
                buffer += recebido
            buffer = buffer[tamanho_corpo:]

            manter_conexao = versao == "HTTP/1.1" and not deve_fechar(cabecalhos)
            status = responder(conexao, cfg, metodo, alvo, manter_conexao)
            registrar_log(endereco, "%s %s" % (metodo, alvo), status)

            if not manter_conexao:
                return

    except (socket.timeout, OSError):
        pass
    finally:
        conexao.close()


trava_log = threading.Lock()


def registrar_log(endereco, requisicao, status):
    with trava_log:
        print(
            '%s %s:%d "%s" %d'
            % (time.strftime("%H:%M:%S"), endereco[0], endereco[1], requisicao, status)
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--name", default="Grupo-PySock/1.0")
    args = parser.parse_args()

    class Config:
        pass

    cfg = Config()
    cfg.raiz = os.path.realpath(args.root)
    cfg.timeout = args.timeout
    cfg.nome = args.name

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((args.host, args.port))
    servidor.listen(128)
    print("Servindo %s em %s:%d" % (cfg.raiz, args.host, args.port))

    try:
        while True:
            conexao, endereco = servidor.accept()
            threading.Thread(
                target=atender, args=(conexao, endereco, cfg), daemon=True
            ).start()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.close()


if __name__ == "__main__":
    main()
