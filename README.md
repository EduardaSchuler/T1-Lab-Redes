# T1-Lab-Redes

### Funcionamento dos métodos principais:

- decodificar_percent: Percorre o texto byte a byte: quando acha um %, lê os dois bytes seguintes, interpreta como hexadecimal e junta o byte decodificado no resultado

- resolver_arquivo: Corta query string e fragment, decodifica percent-encoding, tira a / inicial e junta com a raiz configurada, verificando se o caminho permanece dentro dela.

- montar_cabecalho: Monta os cabeçalhos de uma resposta HTTP como texto

- enviar_arquivo: Manda o cabeçalho pelo socket. Se for uma requisição HEAD, para por aí. Senão, abre o arquivo em modo binário e vai lendo em blocos de 64 KB, mandando cada bloco pelo socket.

- enviar_erro: Mesma lógica para respostas de erro, monta um corpo HTML simples com o código e a descrição, gera o cabeçalho via montar_cabecalho e manda os dois pelo socket.

- responder: É o "roteador" que decide o que fazer com a requisição já interpretada.

- interpretar_requisicao: Recebe os bytes brutos do cabeçalho e extrai método, alvo e versão.

- tamanho_do_corpo: Lê o Content-Length dos cabeçalhos para saber quantos bytes de corpo vêm depois do cabeçalho.

- deve_fechar: Olha o cabeçalho Connection e verifica se um dos valores é close.

- atender: Roda em loop, atendendo uma requisição por vez na mesma conexão



### Como testar:

**A** = máquina do servidor, **B** = máquina do cliente.

## 1. No A: preparar e subir

```bash
mkdir -p www
echo "<h1>ola</h1>" > www/index.html
echo "arquivo a" > www/a.txt
echo "arquivo b" > www/b.txt
python server.py --port 8080 --root ./www
```

Descubra o IP do A (`ip -4 addr` no Linux, `ipconfig` no Windows), por exemplo `192.168.0.10`.

## 2. No A: liberar o firewall

- Windows (PowerShell como administrador):
  ```powershell
  netsh advfirewall firewall add rule name="HTTP 8080" dir=in action=allow protocol=TCP localport=8080
  ```
- Linux: `sudo ufw allow 8080/tcp`

## 3. No B: testar (troque `IP` pelo IP do A)

```bash
curl -i http://IP:8080/a.txt              # 200
curl -I http://IP:8080/a.txt              # HEAD: sem corpo
curl -i http://IP:8080/nao-existe         # 404
curl -i -X POST -d "x" http://IP:8080/    # 405
curl -i --path-as-is "http://IP:8080/../server.py"      # 403
curl -i --path-as-is "http://IP:8080/%2e%2e/server.py"  # 403
curl -v http://IP:8080/a.txt http://IP:8080/b.txt         # reutiliza a conexão
```

No PowerShell do Windows use `curl.exe`.

## 4. Requisições malformadas

```bash
printf 'LIXO\r\n\r\n' | nc IP 8080                       # 400
printf 'GET / HTTP/1.1\r\n\r\n' | nc IP 8080             # 400 (sem Host)
```

## 5. Timeout e concorrência

- **Timeout:** conecte sem enviar nada (`nc IP 8080`). A conexão deve fechar em cerca de 5 segundos.
- **Concorrência:** com uma conexão ociosa aberta, rode `curl -i http://IP:8080/a.txt` em outro terminal. A resposta tem que vir na hora.

## Se não conectar

1. Teste `curl http://127.0.0.1:8080/` no próprio A. Se funcionar, o problema é rede ou firewall.
2. Confira o IP e o firewall do A.
3. Se o `ping` falhar, a rede pode isolar os dispositivos. Use hotspot do celular.
