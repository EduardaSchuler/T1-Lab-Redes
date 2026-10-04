# Plano de testes — T1-Lab-Redes

## 1. Identificação

- **Projeto:** servidor HTTP didático em Python.
- **Arquivo sob teste:** `server.py`.
- **Objetivo:** validar acesso entre dois dispositivos, respostas HTTP, validação de requisições, restrição à raiz servida, persistência de conexão, timeout e atendimento de conexões simultâneas.
- **Ambiente executado:** dois dispositivos Windows na mesma rede local.
- **Servidor (A):** IPv4 `192.168.0.11`, porta TCP `8080`.
- **Cliente (B):** endereço de origem observado `192.168.0.3`.
- **Pasta servida no A:** `www`.
- **Identificação HTTP:** `Grupo-PySock/1.0`.
- **Status geral:** os casos abaixo foram executados; os resultados observados estão registrados individualmente.

> Antes de reutilizar este plano em outra execução, confirme os IPs atuais. Eles podem mudar. O endereço `26.243.101.53` pertencia ao adaptador Radmin VPN do A; os testes bem-sucedidos foram feitos pelo endereço local `192.168.0.11`.

## 2. Pré-condições

1. Python está instalado no dispositivo A.
2. O projeto está disponível no A e a pasta `www` contém os arquivos de teste.
3. O servidor foi iniciado no A com `python .\server.py --port 8080 --root .\www`.
4. O processo do servidor continua ativo enquanto os casos são executados.
5. O firewall e a rede permitem TCP na porta `8080` entre A e B.
6. Os dois dispositivos estão na mesma rede local e o cliente usa o IPv4 local do A.

## 3. Dados de teste

| Recurso | Conteúdo esperado | Uso |
|---|---|---|
| `/a.txt` | `arquivo a` | GET, HEAD, keep-alive e concorrência |
| `/b.txt` | `arquivo b` | GET e teste de múltiplas requisições |
| `/index.html` | `<h1>ola</h1>` | Página inicial da pasta de teste |
| `/nao-existe` | Não existe | Validar resposta 404 |
| `/../server.py` | Caminho fora da raiz | Validar bloqueio 403 |
| `/%2e%2e/server.py` | Caminho fora da raiz codificado | Validar decodificação e bloqueio 403 |

## 4. Casos e evidências

Anexe capturas de tela na coluna de evidência ou crie uma pasta, por exemplo, `evidencias/`, e registre aqui o caminho de cada imagem. Preserve a saída do terminal junto com o comando quando isso ajudar a demonstrar o resultado.

| ID | Caso | Procedimento/entrada | Resultado esperado | Resultado observado | Situação | Evidência |
|---|---|---|---|---|---|---|
| T01 | Conectividade TCP entre B e A | No B: `Test-NetConnection 192.168.0.11 -Port 8080` | `TcpTestSucceeded : True` | `True`; origem observada `192.168.0.3` | Passou | A anexar |
| T02 | GET de arquivo existente | No B: `curl.exe -i http://192.168.0.11:8080/a.txt` | `200 OK` e conteúdo `arquivo a` | `200 OK`; conteúdo recebido | Passou | A anexar |
| T03 | HEAD sem corpo | No B: `curl.exe -I http://192.168.0.11:8080/a.txt` | Cabeçalhos de `200 OK`, sem corpo do arquivo | `200 OK`; a saída apresentou somente cabeçalhos | Passou | A anexar |
| T04 | Caminho inexistente | No B: `curl.exe -i http://192.168.0.11:8080/nao-existe` | `404 Not Found` | `404 Not Found` | Passou | A anexar |
| T05 | Método não permitido | No B: `curl.exe -i -X POST -d "x" http://192.168.0.11:8080/` | `405 Method Not Allowed` e `Allow: GET, HEAD` | `405`; cabeçalho `Allow: GET, HEAD` presente | Passou | A anexar |
| T06 | Travessia de diretório literal | No B: `curl.exe --path-as-is -i "http://192.168.0.11:8080/../server.py"` | `403 Forbidden` | `403 Forbidden` | Passou | A anexar |
| T07 | Travessia de diretório percent-encoded | No B: `curl.exe --path-as-is -i "http://192.168.0.11:8080/%2e%2e/server.py"` | `403 Forbidden` | `403 Forbidden` | Passou | A anexar |
| T08 | Reutilização da conexão HTTP | No B: `curl.exe -v http://192.168.0.11:8080/a.txt http://192.168.0.11:8080/b.txt` | A saída detalhada deve mostrar reutilização da conexão | A saída mostrou `Reusing existing connection`; nessa execução, o segundo pedido deu `404` porque `b.txt` ainda não existia | Passou, com observação | A anexar |
| T09 | Requisição malformada | No B, enviar `LIXO\r\n\r\n` por `TcpClient` | `400 Bad Request` | `400 Bad Request`; conexão encerrada | Passou | A anexar |
| T10 | HTTP/1.1 sem Host | No B, enviar `GET / HTTP/1.1\r\n\r\n` por `TcpClient` | `400 Bad Request` e fechamento da conexão | `400 Bad Request`; `Connection: close` | Passou | A anexar |
| T11 | Timeout de conexão ociosa | No B, conectar ao A sem enviar dados e medir a leitura | Conexão encerrada perto de 5 s; leitura retorna 0 bytes | `Bytes recebidos: 0; tempo: 5 segundos` | Passou | A anexar |
| T12 | Atendimento concorrente | No B, manter uma conexão TCP ociosa numa janela e pedir `/a.txt` noutra antes dos 15 s | A segunda conexão recebe `200 OK` enquanto a primeira permanece aberta | A segunda janela recebeu `200 OK` durante a espera da conexão ociosa | Passou | A anexar |
| T13 | GET de b.txt depois de criado | Criar `www\b.txt` no A e pedir no B | `200 OK` e conteúdo `arquivo b` | `200 OK`; conteúdo recebido | Passou | A anexar |

### Observação do T08

O T08 comprova a reutilização da conexão pelo cliente porque a saída verbose do curl mostrou `Reusing existing connection`. O `404` inicial de `/b.txt` não invalida essa evidência: o arquivo ainda não havia sido criado no momento do teste. Depois, o T13 confirmou que `b.txt` podia ser entregue após sua criação. Se for necessário demonstrar duas respostas bem-sucedidas na mesma conexão, repita o comando de T08 com os dois arquivos já presentes e salve a nova evidência.

## 5. Observações sobre os dados transferidos

- Os arquivos originais `www\a.txt`, `www\b.txt` e `www\index.html` foram armazenados no disco do A.
- Os comandos `curl.exe -i` exibiram as respostas no terminal do B; não foi usado `-o` para salvar cópias de `a.txt` ou `b.txt` no disco do B.
- Os bytes recebidos foram processados temporariamente pelo cliente na memória. TCP transporta bytes; não determina que a aplicação grave esses bytes em arquivo.
- Os arquivos `.txt` criados pelo PowerShell com `Set-Content -Encoding utf8` tinham 14 bytes e exibiram um caractere BOM antes do texto. Isso é relacionado à codificação dos arquivos de teste, não a falha da transmissão.

Para testar explicitamente o salvamento no B numa execução futura, use:

```powershell
curl.exe -o .\a-recebido.txt http://192.168.0.11:8080/a.txt
Get-Item .\a-recebido.txt
Get-Content .\a-recebido.txt
```

Esse teste adicional **não foi executado** e não deve ser relatado como resultado observado até que seja realizado.

## 6. Relação simplificada com o modelo OSI

1. **Aplicação:** HTTP representa o pedido e a resposta; `curl.exe` e `server.py` interpretam essas mensagens.
2. **Transporte:** TCP leva o fluxo de bytes entre as portas; o socket é a interface de programação usada pela aplicação para acessar essa comunicação.
3. **Rede:** IP endereça os dispositivos; neste teste, o cliente acessou `192.168.0.11`.
4. **Enlace:** Wi-Fi/Ethernet transporta quadros no enlace local. Os resultados comprovam a comunicação IP/TCP, mas não são uma captura direta dos quadros.
5. **Física:** bits são representados no meio físico, como sinais de rádio no Wi-Fi ou sinais no cabo. Não foi feita medição/captura da camada física.

Os dados saem da aplicação em direção ao meio de rede e são reconstruídos na ordem inversa ao chegar ao outro dispositivo. A execução observada validou a comunicação HTTP sobre TCP/IP entre dois dispositivos; ela não foi uma captura de pacotes nem uma análise dos sinais físicos.

## 7. Registro de evidências

Use nomes consistentes, por exemplo:

```text
evidencias/
  T01-conectividade.png
  T02-get-a.png
  T03-head.png
  T04-404.png
  T05-405.png
  T06-travessia-literal-403.png
  T07-travessia-codificada-403.png
  T08-keep-alive.png
  T09-requisicao-malformada-400.png
  T10-http11-sem-host-400.png
  T11-timeout-5s.png
  T12-concorrencia.png
  T13-get-b.png
```

Os nomes acima são sugestões; as capturas ainda devem ser anexadas. Ao capturar telas, deixe visíveis o comando relevante e o resultado, evite cortar o status HTTP e oculte informações pessoais ou dados de rede não necessários à avaliação.

## 8. Conclusão de teste

Nos casos executados, o servidor recebeu conexões do B pela rede local, entregou arquivos existentes, retornou códigos de erro para entradas inexistentes, métodos não aceitos e caminhos proibidos, rejeitou requisições malformadas, encerrou uma conexão ociosa após cerca de cinco segundos, permitiu a reutilização observada pelo cliente e atendeu uma segunda conexão enquanto outra estava ociosa.

Os resultados demonstram o comportamento funcional previsto para esta implementação didática e para o ambiente testado. Não demonstram capacidade de produção, desempenho sob carga, compatibilidade com toda a especificação HTTP ou funcionamento em todas as redes.
