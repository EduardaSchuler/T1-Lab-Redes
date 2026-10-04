# T1-Lab-Redes

Servidor HTTP/1.1 feito do zero com sockets TCP em Python, para o Trabalho 1 de Laboratório de Redes de Computadores.

Integrantes: Carolina Silveira de Oliveira da Silva, Larissa Oliveira da Silva e Maria Eduarda Schüler.

## O que tem aqui

| Arquivo ou pasta | Para que serve |
|---|---|
| `server.py` | O servidor HTTP. É o código principal do trabalho. |
| `medir.py` | Cliente que faz as 10 requisições dos cenários C1 e C2. |
| `analisar_captura.py` | Lê as capturas do Wireshark e calcula handshakes, pacotes, bytes, tempo e economia. |
| `www/` | Pasta de teste servida pelo servidor, com a página do teste de interoperabilidade. |
| `capturas/` | Capturas `.pcapng` das medições (`c1.pcapng` e `c2.pcapng`). |
## Como rodar

Só precisa do Python 3. Não tem biblioteca para instalar e não precisa de administrador.

```bash
python server.py --port 8080 --root ./www
```

Argumentos:

| Argumento | Obrigatório | Padrão | O que faz |
|---|---|---|---|
| `--port` | sim | nenhum | Porta TCP onde o servidor escuta (use uma porta alta, acima de 1024). |
| `--root` | sim | nenhum | Pasta raiz que será servida. Nada fora dela é entregue. |
| `--host` | não | `0.0.0.0` | Interface onde escutar. O padrão aceita conexões de outras máquinas. |
| `--timeout` | não | `5` | Segundos de conexão ociosa antes de o servidor fechar. |
| `--name` | não | `Grupo-PySock/1.0` | Texto enviado no cabeçalho `Server`. |

Para descobrir o IP da máquina do servidor, use `ipconfig` no Windows ou `ip -4 addr` no Linux. Depois, é só abrir `http://IP:8080/` no navegador de outra máquina da rede.

## Funcionamento dos métodos principais

- decodificar_percent: Percorre o texto byte a byte. Quando acha um %, lê os dois bytes seguintes, interpreta como hexadecimal e junta o byte decodificado no resultado.
- resolver_arquivo: Corta query string e fragment, decodifica percent-encoding, tira a / inicial e junta com a raiz configurada, verificando se o caminho permanece dentro dela.
- montar_cabecalho: Monta os cabeçalhos de uma resposta HTTP como texto.
- enviar_arquivo: Manda o cabeçalho pelo socket. Se for uma requisição HEAD, para por aí. Senão, abre o arquivo em modo binário e vai lendo em blocos de 64 KB, mandando cada bloco pelo socket.
- enviar_erro: Mesma lógica para respostas de erro. Monta um corpo HTML simples com o código e a descrição, gera o cabeçalho via montar_cabecalho e manda os dois pelo socket.
- responder: É o "roteador" que decide o que fazer com a requisição já interpretada.
- interpretar_requisicao: Recebe os bytes brutos do cabeçalho e extrai método, alvo e versão.
- tamanho_do_corpo: Lê o Content-Length dos cabeçalhos para saber quantos bytes de corpo vêm depois do cabeçalho.
- deve_fechar: Olha o cabeçalho Connection e verifica se um dos valores é close.
- atender: Roda em loop, atendendo uma requisição por vez na mesma conexão. Cada conexão roda na sua própria thread.

## Como testar

**A** = máquina do servidor, **B** = máquina do cliente.

### 1. No A: subir o servidor

```bash
python server.py --port 8080 --root ./www
```

A pasta `www/` já vem com `index.html`, `a.txt`, `b.txt`, `estilo.css`, `script.js`, `banner.png` e `logo.jpg`.

### 2. No A: liberar o firewall

- Windows (PowerShell como administrador):
  ```powershell
  netsh advfirewall firewall add rule name="HTTP 8080" dir=in action=allow protocol=TCP localport=8080
  ```
- Linux: `sudo ufw allow 8080/tcp`

### 3. No B: testar (troque `IP` pelo IP do A)

```bash
curl -i http://IP:8080/a.txt              # 200
curl -I http://IP:8080/a.txt              # HEAD: sem corpo
curl -i http://IP:8080/nao-existe         # 404
curl -i -X POST -d "x" http://IP:8080/    # 405
curl -i --path-as-is "http://IP:8080/../server.py"        # 403
curl -i --path-as-is "http://IP:8080/%2e%2e/server.py"    # 403
curl -i --path-as-is "http://IP:8080/..%2fserver.py"      # 403
curl -v http://IP:8080/a.txt http://IP:8080/b.txt         # reutiliza a conexão
```

No PowerShell do Windows use `curl.exe`.

### 4. Requisições malformadas

```bash
printf 'LIXO\r\n\r\n' | nc IP 8080                       # 400
printf 'GET / HTTP/1.1\r\n\r\n' | nc IP 8080             # 400 (sem Host)
```

### 5. Timeout e concorrência

- **Timeout:** conecte sem enviar nada (`nc IP 8080`). A conexão deve fechar em cerca de 5 segundos.
- **Concorrência:** com uma conexão ociosa aberta, rode `curl -i http://IP:8080/a.txt` em outro terminal. A resposta tem que vir na hora. Para o teste com duas máquinas, peça `/a.txt` do A e do B ao mesmo tempo e confira no log do servidor os dois IPs de origem.

## Medições da Parte 2 (C1 e C2)

O objetivo é comparar 10 requisições ao mesmo recurso em dois cenários: C1 (uma conexão nova por requisição) e C2 (uma única conexão persistente). Tudo é feito entre duas máquinas, com o servidor rodando no A e o cliente no B.

1. No B, anote o RTT médio: `ping IP` (guarde a captura de tela).
2. No B, abra o Wireshark na interface de rede e use o filtro `tcp.port == 8080`.
3. **C1:** inicie a captura, rode o comando abaixo e pare a captura. Salve como `capturas/c1.pcapng`.
   ```bash
   python medir.py --host IP --port 8080 --path /a.txt --modo c1
   ```
4. **C2:** repita com uma captura nova (sem misturar com a anterior) e salve como `capturas/c2.pcapng`.
   ```bash
   python medir.py --host IP --port 8080 --path /a.txt --modo c2
   ```
5. Gere os números e a tabela comparativa (troque `3.5` pelo RTT médio do ping, em ms):
   ```bash
   python analisar_captura.py capturas/c1.pcapng capturas/c2.pcapng --port 8080 --rtt 3.5
   ```

O analisador mostra handshakes completos, pacotes, bytes, tempo, a economia percentual de C2, quantos pacotes e bytes C1 gasta só abrindo e fechando conexões e quantos RTTs a mais o C1 gasta.

## Teste de interoperabilidade

Com o servidor rodando, abra no navegador de outra máquina `http://IP:8080/`. A página `index.html` referencia um CSS, duas imagens e um script, então o navegador faz várias requisições sozinho. O teste dá certo se a página aparece completa, com o banner e o logo.

## Se não conectar

1. Teste `curl http://127.0.0.1:8080/` no próprio A. Se funcionar, o problema é rede ou firewall.
2. Confira o IP e o firewall do A. Se o A tiver mais de um endereço (por exemplo, de uma VPN), use o IP da rede local.
3. Se o `ping` falhar, a rede pode isolar os dispositivos. Use hotspot do celular.
