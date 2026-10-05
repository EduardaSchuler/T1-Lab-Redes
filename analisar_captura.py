"""Analisa capturas do Wireshark (.pcapng ou .pcap) das medicoes C1 e C2.

Nao precisa instalar nada: so usa a biblioteca padrao do Python.

Uso:
    # uma captura
    python analisar_captura.py capturas/c1.pcapng --port 8080

    # comparando C1 e C2 (com o RTT medido no ping, em ms)
    python analisar_captura.py capturas/c1.pcapng capturas/c2.pcapng --port 8080 --rtt 3.5

O que e contado (so pacotes TCP em que uma das portas e --port):
  - handshakes completos: conexoes com SYN, SYN/ACK e o ACK final do cliente;
  - pacotes e bytes totais: tamanho do quadro como aparece no Wireshark (inclui Ethernet);
  - tempo total: do primeiro ao ultimo pacote da captura filtrada;
  - abrir e fechar conexao:
      abertura   = SYN, SYN/ACK e o primeiro ACK do cliente;
      encerramento = pacotes sem dados com FIN ou RST e os pacotes sem dados que vem depois do primeiro FIN
                     (um pacote que carrega dados junto com o FIN conta como dados, nao como encerramento).

Cuidados: se a captura tiver outros programas usando a mesma porta, ou se voce ligou o
Wireshark antes de apagar uma captura antiga, os numeros ficam errados. Comece cada
captura do zero e pare logo depois do ultimo pedido.
"""

import argparse
import struct
import sys

FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10
METODOS = (b"GET ", b"HEAD ", b"POST ", b"PUT ", b"DELETE ", b"OPTIONS ")


# ---------------------------------------------------------------- leitura

def _opcoes_idb(corpo):
    """Le a opcao if_tsresol (codigo 9). Devolve a duracao de um tick em segundos."""
    resolucao = 1e-6
    pos = 8
    while pos + 4 <= len(corpo):
        codigo, tamanho = struct.unpack_from("<HH", corpo, pos)
        if codigo == 0:
            break
        valor = corpo[pos + 4: pos + 4 + tamanho]
        if codigo == 9 and valor:
            v = valor[0]
            resolucao = 2.0 ** -(v & 0x7F) if v & 0x80 else 10.0 ** -v
        pos += 4 + ((tamanho + 3) & ~3)
    return resolucao


def ler_pcapng(dados):
    pos = 0
    endian = "<"
    interfaces = []
    while pos + 12 <= len(dados):
        tipo = struct.unpack_from("<I", dados, pos)[0]
        if tipo == 0x0A0D0D0A:
            bom = struct.unpack_from("<I", dados, pos + 8)[0]
            endian = "<" if bom == 0x1A2B3C4D else ">"
            interfaces = []
        tipo, tamanho = struct.unpack_from(endian + "II", dados, pos)
        if tamanho < 12 or pos + tamanho > len(dados):
            break
        corpo = dados[pos + 8: pos + tamanho - 4]
        if tipo == 1 and len(corpo) >= 8:
            linktype = struct.unpack_from(endian + "H", corpo, 0)[0]
            resolucao = _opcoes_idb(corpo) if endian == "<" else 1e-6
            interfaces.append((linktype, resolucao))
        elif tipo == 6 and len(corpo) >= 20:
            iface, ts_alto, ts_baixo, capturado, original = struct.unpack_from(endian + "IIIII", corpo, 0)
            linktype, resolucao = interfaces[iface] if iface < len(interfaces) else (1, 1e-6)
            yield linktype, ((ts_alto << 32) | ts_baixo) * resolucao, original, corpo[20: 20 + capturado]
        pos += tamanho


def ler_pcap(dados):
    magico = dados[:4]
    if magico in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        endian = "<"
    elif magico in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        endian = ">"
    else:
        raise ValueError("arquivo nao parece ser pcap nem pcapng")
    nano = magico in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    linktype = struct.unpack_from(endian + "I", dados, 20)[0]
    pos = 24
    while pos + 16 <= len(dados):
        seg, frac, capturado, original = struct.unpack_from(endian + "IIII", dados, pos)
        pkt = dados[pos + 16: pos + 16 + capturado]
        yield linktype, seg + frac * (1e-9 if nano else 1e-6), original, pkt
        pos += 16 + capturado


def ler_capturas(caminho):
    with open(caminho, "rb") as f:
        dados = f.read()
    if dados[:4] == b"\x0a\x0d\x0d\x0a":
        return ler_pcapng(dados)
    return ler_pcap(dados)


# ---------------------------------------------------------------- pacotes

def interpretar_tcp(linktype, pkt):
    """Devolve (ip_origem, ip_destino, porta_origem, porta_destino, flags, bytes_de_dados, inicio_dados) ou None."""
    if linktype == 1:
        if len(pkt) < 14:
            return None
        tipo_eth = struct.unpack_from(">H", pkt, 12)[0]
        ip = 14
        if tipo_eth == 0x8100:
            tipo_eth = struct.unpack_from(">H", pkt, 16)[0]
            ip = 18
        if tipo_eth not in (0x0800, 0x86DD):
            return None
    elif linktype == 0:
        ip = 4
    elif linktype == 101:
        ip = 0
    else:
        return None
    if len(pkt) <= ip:
        return None
    versao = pkt[ip] >> 4
    if versao == 4 and len(pkt) >= ip + 20:
        ihl = (pkt[ip] & 0x0F) * 4
        total = struct.unpack_from(">H", pkt, ip + 2)[0]
        if total == 0:  # offload de segmentacao: o tamanho vem zerado na captura
            total = len(pkt) - ip
        if pkt[ip + 9] != 6:
            return None
        origem, destino = pkt[ip + 12: ip + 16], pkt[ip + 16: ip + 20]
        l4, l4_tamanho = ip + ihl, total - ihl
    elif versao == 6 and len(pkt) >= ip + 40:
        if pkt[ip + 6] != 6:
            return None
        origem, destino = pkt[ip + 8: ip + 24], pkt[ip + 24: ip + 40]
        l4, l4_tamanho = ip + 40, struct.unpack_from(">H", pkt, ip + 4)[0]
    else:
        return None
    if len(pkt) < l4 + 20:
        return None
    porta_o, porta_d, _, _, off_flags = struct.unpack_from(">HHIIH", pkt, l4)
    deslocamento = (off_flags >> 12) * 4
    flags = off_flags & 0x3F
    dados = max(0, l4_tamanho - deslocamento)
    return origem, destino, porta_o, porta_d, flags, dados, l4 + deslocamento


# ---------------------------------------------------------------- analise

class Conexao:
    def __init__(self):
        self.syn = self.synack = self.ack_final = False
        self.fin_visto = False
        self.pacotes_abertura = self.bytes_abertura = 0
        self.pacotes_fim = self.bytes_fim = 0


def analisar(caminho, porta):
    conexoes = {}
    total_pacotes = total_bytes = 0
    primeiro = ultimo = None
    requisicoes = respostas = 0

    for linktype, instante, original, pkt in ler_capturas(caminho):
        info = interpretar_tcp(linktype, pkt)
        if info is None:
            continue
        origem, destino, porta_o, porta_d, flags, dados, inicio_dados = info
        if porta_o == porta:
            chave = (destino, porta_d)
            do_cliente = False
        elif porta_d == porta:
            chave = (origem, porta_o)
            do_cliente = True
        else:
            continue

        total_pacotes += 1
        total_bytes += original
        primeiro = instante if primeiro is None else min(primeiro, instante)
        ultimo = instante if ultimo is None else max(ultimo, instante)

        c = conexoes.setdefault(chave, Conexao())
        corpo = pkt[inicio_dados: inicio_dados + 12]
        if dados and do_cliente and corpo.startswith(METODOS):
            requisicoes += 1
        if dados and not do_cliente and corpo.startswith(b"HTTP/1."):
            respostas += 1

        eh_abertura = False
        if flags & SYN and not flags & ACK and do_cliente:
            c.syn = eh_abertura = True
        elif flags & SYN and flags & ACK and not do_cliente:
            c.synack = eh_abertura = True
        elif c.syn and c.synack and not c.ack_final and do_cliente and flags & ACK and not flags & (SYN | FIN | RST) and dados == 0:
            c.ack_final = eh_abertura = True

        # pacote com dados nunca e overhead, mesmo que carregue o FIN junto (o servidor costuma
        # mandar o fim do corpo e o FIN no mesmo pacote)
        eh_fim = dados == 0 and not eh_abertura and (bool(flags & (FIN | RST)) or c.fin_visto)
        if flags & (FIN | RST):
            c.fin_visto = True

        if eh_abertura:
            c.pacotes_abertura += 1
            c.bytes_abertura += original
        elif eh_fim:
            c.pacotes_fim += 1
            c.bytes_fim += original

    handshakes = sum(1 for c in conexoes.values() if c.syn and c.synack and c.ack_final)
    return {
        "arquivo": caminho,
        "conexoes": len(conexoes),
        "handshakes": handshakes,
        "pacotes": total_pacotes,
        "bytes": total_bytes,
        "tempo_s": (ultimo - primeiro) if primeiro is not None else 0.0,
        "requisicoes": requisicoes,
        "respostas": respostas,
        "pacotes_abertura": sum(c.pacotes_abertura for c in conexoes.values()),
        "bytes_abertura": sum(c.bytes_abertura for c in conexoes.values()),
        "pacotes_fim": sum(c.pacotes_fim for c in conexoes.values()),
        "bytes_fim": sum(c.bytes_fim for c in conexoes.values()),
    }


# ---------------------------------------------------------------- saida

def pct(a, b):
    return 100.0 * (a - b) / a if a else 0.0


def imprimir_resumo(r):
    print("Arquivo: %s" % r["arquivo"])
    print("  Conexoes TCP vistas:          %d" % r["conexoes"])
    print("  Handshakes completos:         %d" % r["handshakes"])
    print("  Requisicoes / respostas HTTP: %d / %d" % (r["requisicoes"], r["respostas"]))
    print("  Total de pacotes:             %d" % r["pacotes"])
    print("  Total de bytes (quadros):     %d" % r["bytes"])
    print("  Tempo total da captura:       %.1f ms" % (r["tempo_s"] * 1000))
    pa, ba = r["pacotes_abertura"], r["bytes_abertura"]
    pf, bf = r["pacotes_fim"], r["bytes_fim"]
    print("  Abrir conexoes:               %d pacotes, %d bytes" % (pa, ba))
    print("  Fechar conexoes:              %d pacotes, %d bytes" % (pf, bf))
    if r["pacotes"] and r["bytes"]:
        print("  Abrir + fechar:               %d pacotes (%.0f%% do total), %d bytes (%.0f%% do total)" % (
            pa + pf, 100.0 * (pa + pf) / r["pacotes"], ba + bf, 100.0 * (ba + bf) / r["bytes"]))
    print()


def imprimir_comparacao(c1, c2, rtt_ms):
    print("Tabela comparativa (cole no relatorio):\n")
    print("| Metrica | C1 (uma conexao por requisicao) | C2 (conexao persistente) | Economia de C2 |")
    print("|---|---|---|---|")
    print("| Handshakes TCP completos | %d | %d | nao se aplica |" % (c1["handshakes"], c2["handshakes"]))
    print("| Total de pacotes | %d | %d | %.1f%% |" % (c1["pacotes"], c2["pacotes"], pct(c1["pacotes"], c2["pacotes"])))
    print("| Bytes totais | %d | %d | %.1f%% |" % (c1["bytes"], c2["bytes"], pct(c1["bytes"], c2["bytes"])))
    print("| Tempo total (captura) | %.1f ms | %.1f ms | %.1f%% |" % (
        c1["tempo_s"] * 1000, c2["tempo_s"] * 1000, pct(c1["tempo_s"], c2["tempo_s"])))
    print()
    pa, pf = c1["pacotes_abertura"], c1["pacotes_fim"]
    ba, bf = c1["bytes_abertura"], c1["bytes_fim"]
    print("Overhead de conexao em C1: %d pacotes e %d bytes para abrir e fechar %d conexoes "
          "(%d pacotes e %d bytes so de handshake)." % (pa + pf, ba + bf, c1["conexoes"], pa, ba))
    if c1["pacotes"] and c1["bytes"]:
        print("Isso e %.0f%% dos pacotes e %.0f%% dos bytes de C1." % (
            100.0 * (pa + pf) / c1["pacotes"], 100.0 * (ba + bf) / c1["bytes"]))
    print()
    if rtt_ms:
        n = max(c1["conexoes"], 1)
        diferenca_ms = (c1["tempo_s"] - c2["tempo_s"]) * 1000
        print("Analise em funcao do RTT (RTT medio = %.2f ms):" % rtt_ms)
        print("  Diferenca de tempo C1 - C2: %.1f ms" % diferenca_ms)
        print("  RTTs a mais em C1: %.1f" % (diferenca_ms / rtt_ms))
        print("  Esperado pelo modelo: %d conexoes - 1 = %d RTTs (um handshake a mais por conexao nova)" % (n, n - 1))
        print()


def main():
    parser = argparse.ArgumentParser(description="Analisa capturas do Wireshark das medicoes C1 e C2.")
    parser.add_argument("capturas", nargs="+", help="uma captura (resumo) ou duas (C1 e C2, comparacao)")
    parser.add_argument("--port", type=int, default=8080, help="porta do servidor (padrao 8080)")
    parser.add_argument("--rtt", type=float, help="RTT medio em ms (do ping), para a analise de RTTs")
    args = parser.parse_args()
    if len(args.capturas) > 2:
        parser.error("passe no maximo duas capturas: C1 e C2")

    resultados = [analisar(c, args.port) for c in args.capturas]
    for r in resultados:
        imprimir_resumo(r)
    if len(resultados) == 2:
        imprimir_comparacao(resultados[0], resultados[1], args.rtt)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as erro:
        sys.exit("Erro ao ler a captura: %s" % erro)
