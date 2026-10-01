# Apoio ao relatório e à apresentação — T1-Lab-Redes

Este documento reúne a descrição do funcionamento do servidor, os procedimentos e resultados dos testes realizados entre dois computadores Windows e explicações para apoiar o relatório e a apresentação. Adapte a redação às regras da disciplina e confirme os dados de ambiente que não foram registrados durante os testes.

## 1. Objetivo

O projeto implementa um servidor HTTP básico em Python usando sockets TCP. Um computador atua como servidor (A), disponibilizando arquivos de uma pasta configurada. Outro computador atua como cliente (B), envia requisições pela rede e recebe arquivos ou respostas de erro.

**Objetivo sugerido para o relatório:**

> Implementar e testar um servidor HTTP básico em Python, capaz de receber requisições TCP de clientes, validar mensagens HTTP, disponibilizar arquivos de uma raiz configurada e retornar códigos de resposta apropriados. Avaliar também a proteção contra caminhos externos à raiz, o timeout de conexões ociosas, a persistência de conexão e o atendimento de conexões simultâneas.

## 2. Ambiente de teste observado

- **Servidor A:** Windows, endereço IPv4 local `192.168.0.11`.
- **Cliente B:** Windows, endereço de origem observado `192.168.0.3`.
- **Transporte:** TCP.
- **Porta do servidor:** `8080`.
- **Implementação:** Python, arquivo `server.py`.
- **Pasta servida:** `www`.
- **Identificação HTTP do servidor:** `Grupo-PySock/1.0`.
- **Timeout configurado por padrão:** 5 segundos.
- **Conexão:** dispositivos na mesma rede local.

O A também tinha o endereço `26.243.101.53` no adaptador Radmin VPN. Esse não foi o endereço usado no teste bem-sucedido: a comunicação entre os dispositivos ocorreu pelo IP local do Wi-Fi, `192.168.0.11`.

> Antes de finalizar o relatório, confirme a versão exata do Python instalada no A e registre, se exigido, o modelo dos dispositivos e a rede usada. Esses dados não foram anotados.

## 3. Conceitos fundamentais em linguagem simples

- **Cliente:** programa que pede um recurso. Neste teste, o B usou `curl.exe`.
- **Servidor:** programa que espera pedidos e responde. O A executou `server.py`.
- **IP:** endereço que identifica um dispositivo numa rede. O B alcançou o servidor pelo IP local `192.168.0.11`.
- **Porta:** número que identifica um serviço dentro do dispositivo. O servidor aguardou conexões na porta `8080`.
- **TCP:** protocolo de transporte que estabelece uma conexão e entrega os dados em sequência confiável.
- **HTTP:** protocolo de aplicação que define como clientes pedem recursos e como servidores respondem.
- **Socket:** interface de programação usada para enviar e receber dados pela rede.
- **Requisição:** mensagem enviada pelo cliente, contendo método, caminho, versão HTTP e, possivelmente, cabeçalhos e corpo.
- **Resposta:** mensagem devolvida pelo servidor, com status, cabeçalhos e, normalmente, o conteúdo pedido ou uma mensagem de erro.
- **Cabeçalho HTTP:** metadados da mensagem. Por exemplo, `Content-Type` indica o tipo de conteúdo; `Content-Length` informa seu tamanho em bytes.
- **`GET`:** método usado para solicitar um recurso.
- **`HEAD`:** parecido com `GET`, mas solicita somente os cabeçalhos, sem o corpo da resposta.
- **Keep-alive:** possibilidade de reutilizar a mesma conexão HTTP para mais requisições.
- **Thread:** fluxo de execução independente. O programa cria uma thread por conexão aceita, para que uma conexão esperando dados não impeça o atendimento de outra.
- **Raiz servida:** pasta definida na inicialização (neste teste, `www`). Os caminhos pedidos devem permanecer dentro dela.
- **Travessia de diretório:** tentativa de escapar de uma pasta usando sequências como `../`; neste servidor, caminhos que saem da raiz devem ser bloqueados.

## 4. Fluxo de funcionamento do programa

O código está em [`server.py`](./server.py).

1. **Inicialização (`main`)**
   Lê os parâmetros de linha de comando, transforma a pasta raiz em um caminho real, cria o socket TCP, associa-o ao endereço e à porta e começa a aguardar conexões. O host padrão é `0.0.0.0`, que permite escutar nas interfaces IPv4 disponíveis.

2. **Aceitação de conexão (`main`)**
   Quando um cliente se conecta, o servidor cria uma thread para atendê-lo e volta ao laço de aceitação. Assim, outra conexão pode ser aceita sem esperar necessariamente o cliente anterior terminar.

3. **Leitura da mensagem (`atender`)**
   A função recebe bytes em blocos e acumula os dados até encontrar `\r\n\r\n`, separador entre os cabeçalhos HTTP e o corpo. Há um limite de 16 KiB para o cabeçalho.

4. **Interpretação e validação (`interpretar_requisicao`)**
   A primeira linha é separada em método, alvo (caminho solicitado) e versão. O código verifica a estrutura da linha, aceita HTTP/1.0 ou HTTP/1.1 e exige `Host` em HTTP/1.1. Cabeçalhos malformados causam erro de requisição.

5. **Validação do corpo (`tamanho_do_corpo`)**
   Interpreta `Content-Length`, rejeita valores inválidos ou acima de 1 MiB e rejeita `Transfer-Encoding`, que não é implementado por este servidor.

6. **Escolha do recurso ou erro (`responder`)**
   Aceita `GET` e `HEAD`. Outros métodos recebem `405 Method Not Allowed` e o cabeçalho `Allow: GET, HEAD`. Para métodos aceitos, resolve o caminho e verifica se o arquivo pode ser servido.

7. **Decodificação e segurança do caminho (`decodificar_percent` e `resolver_arquivo`)**
   `decodificar_percent` converte sequências percent-encoded; por exemplo, `%2e` representa `.`. `resolver_arquivo` remove query string e fragmento, decodifica o caminho, normaliza o caminho real e verifica se ele está dentro da raiz. Se sair da raiz, o servidor responde `403 Forbidden`.

8. **Resposta com arquivo (`tipo_mime`, `montar_cabecalho` e `enviar_arquivo`)**
   `tipo_mime` escolhe o tipo de conteúdo pela extensão. `montar_cabecalho` cria a linha de status e os cabeçalhos. `enviar_arquivo` transmite o cabeçalho e depois o arquivo em blocos de 64 KiB. Para `HEAD`, o corpo não é enviado.

9. **Resposta de erro (`enviar_erro`)**
   Monta um corpo HTML simples contendo o código e a descrição do erro, calcula o tamanho e envia os cabeçalhos e, salvo no caso de `HEAD`, o corpo.

10. **Persistência e fechamento (`deve_fechar` e `atender`)**
    Para HTTP/1.1, a conexão fica aberta por padrão, a menos que o cabeçalho `Connection` peça `close`. A função `atender` pode então processar mais de uma requisição nessa conexão.

11. **Timeout e log**
    Cada socket de cliente recebe o timeout configurado (5 segundos por padrão). O log registra horário, IP e porta do cliente, requisição e status. Um lock protege a escrita concorrente no log.

## 5. Códigos de resposta observados e significado

- **`200 OK`:** o pedido foi atendido. Foi observado para `a.txt` e, depois de o arquivo ser criado, para `b.txt`.
- **`400 Bad Request`:** a requisição não tem formato aceitável ou falta informação obrigatória. Foi observado para a mensagem `LIXO` e para HTTP/1.1 sem `Host`.
- **`403 Forbidden`:** o caminho tenta acessar algo fora da raiz servida. Foi observado para as duas tentativas de travessia.
- **`404 Not Found`:** o caminho não foi bloqueado por sair da raiz, mas não há arquivo correspondente. Foi observado para `nao-existe` e inicialmente para `b.txt`, antes de o arquivo ser criado.
- **`405 Method Not Allowed`:** o método existe no protocolo, mas não é aceito por esta implementação. Foi observado com `POST`; a resposta incluiu `Allow: GET, HEAD`.

**Distinção importante para a apresentação:** `403` e `404` não significam a mesma coisa. `403` é uma recusa de acesso ao caminho; `404` indica que o recurso não foi encontrado no local permitido.

## 6. Procedimento reproduzível no Windows

### 6.1 Preparar e iniciar o A

No PowerShell do A, a partir da pasta do projeto:

```powershell
Set-Location 'C:\Users\laris\Downloads\Faculdade\T1-Lab-Redes'
New-Item -ItemType Directory -Force .\www | Out-Null
Set-Content .\www\index.html '<h1>ola</h1>' -Encoding utf8
Set-Content .\www\a.txt 'arquivo a' -Encoding utf8
Set-Content .\www\b.txt 'arquivo b' -Encoding utf8
python .\server.py --port 8080 --root .\www
```

Deixe o terminal do servidor aberto. Se o comando `python` não estiver disponível, verifique a instalação do Python no A; em algumas instalações do Windows, o iniciador é `py`.

Descubra o IPv4 local do A com `ipconfig`. Se o firewall bloquear a porta, uma pessoa com permissão administrativa pode autorizar TCP 8080 para o perfil de rede adequado. O comando abaixo cria uma regra para qualquer perfil, então só deve ser usado quando apropriado para o ambiente:

```powershell
New-NetFirewallRule -DisplayName "T1 Lab HTTP 8080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 -Profile Any
```

### 6.2 Testes HTTP básicos no B

Substitua `192.168.0.11` pelo IPv4 atual do A:

```powershell
Test-NetConnection 192.168.0.11 -Port 8080
curl.exe -i http://192.168.0.11:8080/a.txt
curl.exe -I http://192.168.0.11:8080/a.txt
curl.exe -i http://192.168.0.11:8080/nao-existe
curl.exe -i -X POST -d "x" http://192.168.0.11:8080/
curl.exe --path-as-is -i "http://192.168.0.11:8080/../server.py"
curl.exe --path-as-is -i "http://192.168.0.11:8080/%2e%2e/server.py"
curl.exe -v http://192.168.0.11:8080/a.txt http://192.168.0.11:8080/b.txt
```

Use `curl.exe` no Windows PowerShell para chamar o programa curl, evitando o alias `curl` de algumas versões do PowerShell.

### 6.3 Requisições malformadas

Para testar uma linha inválida:

```powershell
$c = New-Object System.Net.Sockets.TcpClient
$c.Connect("192.168.0.11", 8080)
$s = $c.GetStream()
$d = [Text.Encoding]::ASCII.GetBytes("LIXO`r`n`r`n")
$s.Write($d, 0, $d.Length)
$s.ReadTimeout = 3000
$b = New-Object byte[] 512
$n = $s.Read($b, 0, $b.Length)
[Text.Encoding]::ASCII.GetString($b, 0, $n)
$c.Close()
```

Para testar especificamente a ausência de `Host` em HTTP/1.1:

```powershell
$c = New-Object System.Net.Sockets.TcpClient
$c.Connect("192.168.0.11", 8080)
$s = $c.GetStream()
$s.ReadTimeout = 3000
$d = [Text.Encoding]::ASCII.GetBytes("GET / HTTP/1.1`r`n`r`n")
$s.Write($d, 0, $d.Length)
$b = New-Object byte[] 512
$n = $s.Read($b, 0, $b.Length)
[Text.Encoding]::ASCII.GetString($b, 0, $n)
$c.Close()
```

Nos dois casos, espera-se `400 Bad Request`. No teste sem `Host`, a resposta observada também indicou `Connection: close`.

### 6.4 Timeout de conexão ociosa

Este bloco conecta ao A sem enviar uma requisição e mede quanto tempo demora até o servidor fechar a conexão:

```powershell
$c = New-Object System.Net.Sockets.TcpClient
$c.Connect("192.168.0.11", 8080)
$s = $c.GetStream()
$s.ReadTimeout = 8000
$b = New-Object byte[] 512
$timer = [Diagnostics.Stopwatch]::StartNew()
$n = $s.Read($b, 0, $b.Length)
$timer.Stop()
"Bytes recebidos: $n; tempo: $([math]::Round($timer.Elapsed.TotalSeconds, 1)) segundos"
$c.Close()
```

Resultado observado: `Bytes recebidos: 0; tempo: 5 segundos`. O valor zero significa que a conexão foi encerrada sem resposta HTTP, pois o cliente não havia enviado uma requisição.

### 6.5 Concorrência entre conexões

Abra **dois terminais PowerShell no B**. No primeiro, estabeleça uma conexão TCP e deixe-a sem enviar dados por 15 segundos:

```powershell
$c = New-Object System.Net.Sockets.TcpClient
$c.Connect("192.168.0.11", 8080)
"Conexão ociosa aberta; teste agora na outra janela."
Start-Sleep -Seconds 15
$c.Close()
```

Enquanto esse bloco estiver aguardando, execute no segundo terminal:

```powershell
curl.exe -i http://192.168.0.11:8080/a.txt
```

Resultado observado: o segundo terminal recebeu `200 OK` enquanto a conexão ociosa ainda estava aberta. Isso demonstra que a conexão sem dados não impediu o servidor de atender outra conexão.

### 6.6 Persistência da mesma conexão

O comando com duas URLs:

```powershell
curl.exe -v http://192.168.0.11:8080/a.txt http://192.168.0.11:8080/b.txt
```

mostrou `Reusing existing connection` na saída detalhada de curl. Isso comprova que o **cliente** reutilizou a conexão TCP/HTTP para o segundo pedido. Na primeira execução, `b.txt` ainda não existia e respondeu `404`; após criá-lo em `www`, uma requisição separada a `b.txt` respondeu `200 OK`. Para repetir a verificação com ambos os recursos existentes, rode novamente o comando acima depois de preparar os dois arquivos.

## 7. Registro dos resultados efetivamente observados

| Verificação | Resultado observado | Conclusão |
|---|---|---|
| `Test-NetConnection` ao IPv4 local do A, porta 8080 | `TcpTestSucceeded : True` | A conexão TCP do B ao serviço no A foi estabelecida. |
| `GET /a.txt` | `200 OK`, conteúdo `arquivo a` | O servidor localizou e transmitiu o arquivo. |
| `HEAD /a.txt` | `200 OK`, sem corpo | O servidor transmitiu os cabeçalhos sem o conteúdo do arquivo. |
| `GET /nao-existe` | `404 Not Found` | O servidor informou que não localizou o recurso. |
| `POST /` | `405 Method Not Allowed`, `Allow: GET, HEAD` | O método não é implementado; o servidor informou os métodos permitidos. |
| Caminho `/../server.py` | `403 Forbidden` | Tentativa de sair da raiz foi bloqueada. |
| Caminho `/%2e%2e/server.py` | `403 Forbidden` | A mesma tentativa codificada também foi bloqueada após decodificação. |
| Duas URLs no curl detalhado | `Reusing existing connection`; segunda URL inicialmente `404` | O cliente reutilizou a conexão; naquele momento `b.txt` ainda não estava disponível. |
| Requisição `LIXO` | `400 Bad Request` | A requisição inválida foi rejeitada. |
| HTTP/1.1 sem `Host` | `400 Bad Request`, `Connection: close` | O cabeçalho obrigatório foi validado. |
| Conexão sem envio de dados | 0 bytes após 5 segundos | O timeout encerrou a conexão ociosa. |
| Conexão ociosa mais outro pedido em paralelo | `200 OK` durante a espera da primeira | O servidor atendeu uma segunda conexão enquanto a primeira aguardava. |
| `GET /b.txt` após criação do arquivo | `200 OK`, conteúdo `arquivo b` | O servidor entregou o segundo arquivo de teste. |

## 8. Observação sobre a codificação dos arquivos

Os arquivos de texto de teste foram criados no Windows PowerShell usando `Set-Content -Encoding utf8`. Essa forma de criação pode incluir um BOM UTF-8 no início do arquivo. Por isso, a saída exibiu um caractere estranho antes de `arquivo a` e `arquivo b`, e os arquivos apareceram com 14 bytes. Isso é uma característica dos arquivos de teste e não uma falha na conexão ou no servidor.

## 9. Onde os dados ficam salvos e como atravessam a rede

No A, os arquivos originais de teste ficaram armazenados no disco dentro da pasta `www`: `www\a.txt`, `www\b.txt` e `www\index.html`. O processo Python abriu os arquivos e leu seus bytes para enviá-los ao cliente.

No B, os testes feitos com `curl.exe -i` exibiram a resposta no terminal. Não foi usado um comando de download para gravar `a.txt` ou `b.txt` em um arquivo no disco do B. Mesmo assim, os dados recebidos passaram temporariamente pela memória do B enquanto eram processados e exibidos. Portanto, **receber e mostrar no terminal não significa que uma cópia permanente foi salva**.

Uma forma simples de relacionar o experimento ao modelo OSI:

1. **Aplicação (HTTP):** `curl.exe` construiu o pedido `GET /a.txt`; `server.py` interpretou o pedido e montou a resposta `HTTP/1.1 200 OK` com o conteúdo.
2. **Transporte (TCP):** o socket entregou o fluxo de bytes ao TCP. O TCP transportou os bytes de forma confiável entre as portas dos dispositivos. No servidor, a aplicação escutou na porta `8080`; no cliente, o sistema operacional usou uma porta temporária.
3. **Rede (IP):** o endereçamento IP identificou o destino na rede local: o B enviou os dados ao A, no endereço `192.168.0.11`.
4. **Enlace (Wi-Fi/Ethernet):** a rede local levou os dados entre os dispositivos usando a tecnologia de enlace disponível. O teste registrou a interface `Ethernet` para a rota do B e o adaptador Wi-Fi do A; esses nomes de interface, por si só, não demonstram o meio físico exato usado em todo o percurso.
5. **Física:** os bits são representados e transmitidos pelo meio físico — por sinais de rádio no trecho Wi-Fi ou sinais elétricos/ópticos num trecho cabeado. A evidência coletada confirma a comunicação IP/TCP e HTTP, não uma captura ou análise dos sinais físicos.

Em termos didáticos, o envio percorre as camadas em direção ao meio de comunicação e a recepção faz o caminho inverso. O **socket é uma interface de programação entre a aplicação e os serviços de transporte do sistema operacional**; não é uma camada física, nem é onde os arquivos ficam guardados. O **TCP transporta os bytes**, mas não decide salvar o arquivo. Nesse teste, a leitura do original foi feita pelo servidor no disco do A; o armazenamento permanente de uma cópia no B exigiria uma opção explícita de download, que não foi utilizada.

> Para afirmar que o B gravou uma cópia, seria necessário executar, por exemplo, `curl.exe -o .\a-recebido.txt http://192.168.0.11:8080/a.txt` no B e depois verificar o arquivo criado. Esse teste adicional não faz parte dos resultados observados até agora.

## 10. Perguntas prováveis na apresentação

### Como vocês provaram que os dois dispositivos se comunicaram?

O B executou `Test-NetConnection` para `192.168.0.11` na porta `8080` e recebeu `TcpTestSucceeded : True`. Em seguida, recebeu respostas HTTP e conteúdo dos arquivos hospedados no A.

### Qual é a diferença entre IP e porta?

O IP identifica o dispositivo na rede; a porta identifica o serviço dentro dele. Neste experimento, `192.168.0.11` identifica o A e `8080` identifica a porta do servidor HTTP.

### Qual é a diferença entre persistência e concorrência?

Persistência significa fazer mais de uma requisição pela mesma conexão. Concorrência significa atender conexões diferentes ao mesmo tempo. O `curl -v` mostrou a reutilização da conexão; o teste de duas janelas mostrou uma nova requisição sendo atendida enquanto outra conexão estava ociosa.

### O que significa usar uma thread por conexão?

Cada conexão aceita recebe um fluxo de execução próprio. Se uma thread estiver esperando dados de um cliente, outra pode trabalhar em uma conexão distinta. A abordagem é adequada para demonstrar concorrência neste projeto didático, mas tem custos e limites de escalabilidade em servidores com grande volume de conexões.

### Por que `../` e `%2e%2e` retornam 403?

`../` representa subir um nível na estrutura de pastas. `%2e` é uma codificação percentual do caractere ponto. O servidor decodifica e normaliza o caminho antes de verificar se permanece dentro da raiz; se escapar dela, bloqueia o pedido com `403`.

### Por que o servidor retorna 403 para um caminho e 404 para outro?

`403` indica que o caminho foi considerado fora da área permitida. `404` indica que o recurso não foi encontrado dentro do escopo permitido. São situações diferentes.

### Por que `HEAD` tem status 200, mas não mostra o arquivo?

Essa é a finalidade de `HEAD`: receber os mesmos metadados principais de uma resposta `GET`, sem transferir o corpo. No servidor, `enviar_arquivo` envia o cabeçalho e retorna antes de transmitir os bytes do arquivo.

### Por que `POST` retorna 405?

O método `POST` é válido no HTTP em geral, mas esta implementação só aceita `GET` e `HEAD`. O status `405` indica que o servidor não permite aquele método nessa implementação; o cabeçalho `Allow` informa as opções aceitas.

### O que o teste de timeout demonstra?

Uma conexão TCP foi aberta sem enviar uma requisição. O servidor fechou a conexão depois de cerca de 5 segundos; o cliente observou fim da conexão lendo zero bytes. Como não houve requisição HTTP, não havia resposta HTTP a enviar.

### O servidor está pronto para produção?

Não. É um projeto didático para estudar sockets, HTTP, validação de entrada e concorrência. Ele não implementa HTTPS, autenticação, todos os recursos do HTTP, nem as proteções, limites operacionais e testes necessários a um serviço de produção.

## 11. Limitações e cuidados ao redigir a conclusão

- O teste foi executado numa rede local específica; não prova funcionamento em todas as redes ou sistemas operacionais.
- Os resultados observados devem ser distinguidos dos resultados esperados em testes ainda não executados.
- O primeiro pedido a `b.txt` no teste de keep-alive retornou `404` porque o arquivo ainda não existia naquele momento. Depois de criado, o pedido separado foi bem-sucedido.
- O teste de persistência comprovou a reutilização pelo cliente conforme a saída do curl; não é uma medição de desempenho.
- O teste de concorrência comprovou atendimento de uma segunda conexão enquanto outra estava ociosa; não mede quantas conexões simultâneas o servidor suporta.
- O tratamento de HTTP é deliberadamente parcial e deve ser descrito como implementação didática, não como um servidor HTTP completo.

## 12. Estrutura sugerida para o relatório

1. **Introdução e objetivo:** problema estudado e finalidade do servidor.
2. **Fundamentação teórica:** IP, porta, TCP, sockets e estrutura básica de HTTP.
3. **Ambiente experimental:** dispositivos, sistema operacional, rede, Python, IP e porta.
4. **Implementação:** fluxo das funções principais e decisões do código.
5. **Metodologia:** preparação do servidor, comandos de teste e critérios esperados.
6. **Resultados:** tabela de testes, códigos observados e capturas de tela legíveis.
7. **Discussão:** o que cada resultado comprova, diferenças entre esperado e observado e explicação de ocorrências como o `404` inicial de `b.txt`.
8. **Limitações:** escopo didático e funcionalidades que não foram implementadas.
9. **Conclusão:** síntese do que foi aprendido e do que os resultados permitem afirmar.

Ao inserir capturas de tela, identifique cada uma com número, legenda e referência no texto. Evite mostrar informações pessoais ou dados de rede que não sejam necessários ao relatório.
