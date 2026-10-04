# Apoio ao relatório e à apresentação do T1-Lab-Redes

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
5. **Física:** os bits são representados e transmitidos pelo meio físico, por sinais de rádio no trecho Wi-Fi ou sinais elétricos/ópticos num trecho cabeado. A evidência coletada confirma a comunicação IP/TCP e HTTP, não uma captura ou análise dos sinais físicos.

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

## 13. Histórico do que já fizemos

Esta seção é o nosso diário de bordo. A ideia é que qualquer uma de nós consiga ver o que já foi feito, o que foi decidido e o que ainda falta.

### 13.1 Linha do tempo

| Quando | O que aconteceu |
|---|---|
| Antes de 01/10/2026 | O servidor (`server.py`) foi escrito em Python com sockets, com GET, HEAD, os códigos 200, 400, 403, 404 e 405, thread por conexão, keep-alive e timeout. Os commits estão na branch `main` e na `teste-dois-dispositivos`. |
| 01/10/2026 | Primeiro teste com dois computadores Windows na mesma rede. O A (192.168.0.11) rodou o servidor e o B (192.168.0.3) fez as requisições. Foram feitos os testes T01 a T13 do plano de testes e as capturas de tela ficaram na pasta `Anexos/`. Um acesso pelo IP da Radmin VPN (26.243.101.53) deu tempo esgotado, e o IP da rede local funcionou. |
| 01/10/2026 | O rascunho do relatório (`Relatório T1 Lab Redes.docx`) foi montado com os comandos e as respostas de cada teste. |
| 03/10/2026 | Clonamos o repositório em `Downloads\T1-Lab-Redes`, entramos na branch `teste-dois-dispositivos` e juntamos o enunciado e a pasta das aulas práticas como material de consulta. |
| 04/10/2026 | O relatório foi completado com o Claude. Também foram criados `medir.py`, `analisar_captura.py` e a página de interoperabilidade, o README foi refeito e o relatório foi enxugado para caber no limite de 8 páginas (arquivo `Relatório T1 Lab Redes - v3.docx`). Os detalhes estão logo abaixo. |

### 13.2 O que foi feito na sessão de 04/10/2026

- Lemos o enunciado inteiro e comparamos com o código e com os testes que já existiam. O servidor atende o que a Parte 1 e a Parte 2 pedem de implementação.
- Completamos o relatório (v2): problema, arquitetura, estratégia de concorrência, tabela de conformidade, demonstração de segurança, demais casos de teste, seção da Parte 2 e considerações finais. Tudo que depende de Wireshark ou de `ping` ficou marcado em amarelo como pendente, para não inventarmos número nenhum.
- Criamos o `medir.py`, o cliente que faz as 10 requisições em C1 (uma conexão por requisição) e em C2 (uma conexão só). Testamos a lógica apenas em localhost.
- Rodamos mais tentativas de travessia de diretório em localhost (`/..%2fserver.py`, `/%2e%2e%2fserver.py`, `/a.txt/../../server.py`, `/..%5cserver.py` e `/%252e%252e/server.py`). Todas deram 403, e a dupla codificação deu 404 porque vira um nome literal que não existe, sem sair da raiz. Também confirmamos em localhost que o HEAD devolve os mesmos cabeçalhos do GET, sem corpo, e que o servidor aguenta requisições coladas (pipelining) e requisições chegando byte a byte.
- Pontos que descobrimos no caminho: o README da `main` ainda citava `servidor.py` (o arquivo se chama `server.py`) e os `.txt` de teste têm BOM, por isso ficaram com 14 bytes. Decidimos não recriar os `.txt`, para os prints que já existem continuarem batendo com os arquivos.
- Criamos a página de interoperabilidade em `www/`: `index.html` com `estilo.css`, `script.js`, `banner.png` e `logo.jpg`. Abrimos a página no navegador contra o servidor e as cinco requisições (HTML, CSS, banner, logo e script) voltaram 200.
- Criamos o `analisar_captura.py`, que lê o `.pcapng` do Wireshark e calcula handshakes, pacotes, bytes, tempo, economia de C2, overhead de abrir e fechar conexões e RTTs a mais. Ele foi testado só com capturas sintéticas montadas à mão, em que os números esperados eram conhecidos, e bateu. Falta testar com uma captura de verdade.
- Refizemos o `README.md` com os argumentos, a pasta `www/`, o passo a passo das medições e o teste de interoperabilidade.
- Refizemos o relatório como `Relatório T1 Lab Redes - v3.docx`. O texto ficou mais curto e em linguagem mais direta, e os prints viraram uma grade de figuras com legenda, para caber em poucas páginas (hoje ficou em 7, contando a capa). O `ipconfig` foi recortado para mostrar só os IPv4, sem expor os endereços IPv6. Os prints originais continuam na pasta `Anexos/`.
- Esclarecemos um ponto do enunciado: o teste de concorrência que já tínhamos (uma conexão ociosa e um `curl`, os dois no dispositivo B) prova que o servidor atende em paralelo, mas o enunciado pede duas máquinas distintas. O log do servidor só mostra o IP 192.168.0.3, então falta repetir com o A e o B pedindo ao mesmo tempo.

### 13.3 O que continua faltando

A lista completa está no checklist da seção 14.1 e os passos de cada tarefa estão no arquivo `TAREFAS.md`. Em resumo: capturas do Wireshark, RTT com `ping`, medição C1 e C2 de verdade, teste com duas máquinas ao mesmo tempo, print da página de interoperabilidade no navegador, PDF do relatório e o pacote `.zip` de entrega. Esses itens dependem de rodar tudo com as duas máquinas na mesma rede.

## 14. Guia de apresentação

O professor deixou claro que a apresentação vale 25% e que o teste de interoperabilidade vale 20%, os dois feitos ao vivo. Além disso, quem não consegue explicar o código não é considerado autor dele. Então o objetivo é que as três consigam explicar qualquer parte do `server.py` com as próprias palavras.

### 14.1 Checklist do que falta (de acordo com o enunciado)

**Código e pasta de teste**
- [x] Criar uma página HTML em `www/` com imagem e CSS para o teste de interoperabilidade (feito: `index.html`, `estilo.css`, `script.js`, `banner.png` e `logo.jpg`).
- [x] Sobre o BOM dos `.txt`: decidimos manter como está (14 bytes) e explicar no relatório.
- [x] README da entrega com como rodar, argumentos (`--port`, `--root`, `--host`, `--timeout`, `--name`) e `server.py` em todos os exemplos (feito).
- [ ] Confirmar que o servidor roda na VDI sem administrador e sem instalar nada.

**Verificação antes de medir**
- [ ] Anotar o IP das duas máquinas (`ipconfig`) e testar `ping` entre elas.
- [ ] Confirmar que o Wireshark lista e captura na interface de rede.

**Parte 1 (evidências)**
- [ ] Repetir no B, pela rede, a terceira tentativa de travessia (`curl.exe --path-as-is -i "http://192.168.0.11:8080/..%2fserver.py"`) e guardar a captura de tela.
- [ ] Captura do Wireshark de um GET bem-sucedido do B ao A, marcando o handshake, o pacote da requisição, os pacotes da resposta e o encerramento.
- [ ] Evidência de duas máquinas distintas sendo atendidas ao mesmo tempo (log do servidor com dois IPs de origem em instantes próximos ou uma captura).
- [ ] Repetir o `curl -v` com `a.txt` e `b.txt` já existindo, para mostrar duas respostas 200 na mesma conexão.

**Parte 2 (medições)**
- [ ] Registrar o RTT médio com `ping` entre as máquinas.
- [ ] Rodar C1 (`python medir.py --host IP --port 8080 --path /a.txt --modo c1`) com a captura ligada e salvar `capturas/c1.pcapng`.
- [ ] Rodar C2 (`--modo c2`) com a captura ligada e salvar `capturas/c2.pcapng`.
- [ ] Extrair de cada captura: handshakes completos, total de pacotes, bytes totais e tempo total.
- [ ] Calcular a economia percentual de pacotes e de bytes.
- [ ] Quantificar quantos pacotes e bytes C1 gasta só abrindo e fechando conexões.
- [ ] Calcular quantos RTTs a mais o C1 gastou e explicar de onde vêm (o handshake de cada conexão nova).

**Relatório**
- [ ] Trocar todos os trechos amarelos do `Relatório T1 Lab Redes - v2.docx` pelos resultados reais.
- [ ] Preencher a versão do Python e o modelo dos dispositivos.
- [ ] Escrever a conclusão dizendo em que condição de rede a conexão persistente ganha ainda mais (muitas conexões e RTT alto), usando os números medidos.
- [ ] Exportar para PDF (documento único, cobrindo as duas partes) e conferir que ficou em até 8 páginas, como o professor pediu em aula. Hoje o v3 tem 7 com a capa, e ainda vão entrar as evidências novas (a seção Solução tem espaço sobrando na página 4).

**Entrega**
- [ ] Montar o `.zip` na mão para subir no Moodle: código-fonte (`server.py`, `medir.py`, `analisar_captura.py`), `README.md`, `www/`, `capturas/` e o relatório em PDF.
- [ ] Não incluir no zip a pasta `Aulas práticas`, o enunciado nem a pasta `.git`.
- [ ] Só uma pessoa do grupo faz a entrega no Moodle, antes do começo da aula de apresentação.

**Dia da apresentação**
- [ ] Combinar com o outro grupo quem testa primeiro, e trocar os IPs.
- [ ] Liberar a porta no firewall do computador que vai rodar o servidor.
- [ ] Ensaiar a explicação do código com as três presentes.

### 14.2 Roteiro sugerido (uns 10 a 15 minutos)

A divisão abaixo é só uma sugestão. Vale as três treinarem as partes umas das outras, porque o professor pode perguntar qualquer coisa para qualquer uma.

| Parte | Tempo | O que mostrar | Sugestão de quem fala |
|---|---|---|---|
| 1. Abertura | 1 min | Qual era o problema: como o TCP afeta o desempenho do HTTP, e por que testar entre máquinas diferentes. | A definir |
| 2. Arquitetura | 2 min | Passeio por `main`, `atender` e `responder`. Thread por conexão e por que escolhemos isso. | A definir |
| 3. Demonstração ao vivo | 3 min | Os comandos da seção 14.4 em um computador contra o outro. | A definir |
| 4. Segurança | 2 min | Por que `../` e `%2e%2e` dão 403. Explicar `realpath` e a checagem com `os.sep`. | A definir |
| 5. Parte 2 | 3 min | Medição C1 e C2, a tabela, a economia e a conta em RTTs. | A definir |
| 6. Fechamento | 1 min | Conclusão e limitações do servidor. | A definir |

### 14.3 Passeio pelo código (por onde começar a explicar)

Todos os números de linha são do `server.py` atual. A melhor forma de contar a história é seguir o caminho de uma requisição:

1. **`main` (linha 295):** lê os argumentos, cria o socket, faz `bind` em `0.0.0.0` e fica no `accept`. Cada conexão vira uma thread.
2. **`atender` (linha 237):** é o coração. Acumula bytes em um buffer até achar `\r\n\r\n`, separa o cabeçalho, trata o corpo e chama `responder`. Depois decide se mantém a conexão aberta. O timeout do socket está aqui.
3. **`interpretar_requisicao` (linha 186):** confere a primeira linha (método, alvo e versão) e os cabeçalhos. Se algo estiver errado, levanta `RequisicaoInvalida` e a resposta é 400.
4. **`responder` (linha 148):** decide entre 405, 400, 403, 404 e 200.
5. **`resolver_arquivo` (linha 91) e `decodificar_percent` (linha 67):** é onde mora a segurança. Decodifica, junta com a raiz, normaliza com `realpath` e confere se continua dentro da raiz.
6. **`montar_cabecalho` (linha 104), `enviar_arquivo` (linha 119) e `enviar_erro` (linha 130):** montam e mandam a resposta. No HEAD, o cabeçalho sai igual ao do GET e o corpo não é enviado.

### 14.4 Roteiro da demonstração ao vivo

No computador que roda o servidor (A):

```powershell
python .\server.py --port 8080 --root .\www
```

No outro computador (B), trocando `IP` pelo endereço do A:

```powershell
curl.exe -i http://IP:8080/a.txt
curl.exe -I http://IP:8080/a.txt
curl.exe -i http://IP:8080/nao-existe
curl.exe -i -X POST -d "x" http://IP:8080/
curl.exe --path-as-is -i "http://IP:8080/../server.py"
curl.exe --path-as-is -i "http://IP:8080/%2e%2e/server.py"
curl.exe -v http://IP:8080/a.txt http://IP:8080/b.txt
```

Dica: deixar o terminal do servidor visível na tela, porque o log mostra cada requisição chegando com o IP de origem. É uma prova bonita de que a conversa é entre duas máquinas.

### 14.5 Teste de interoperabilidade (20% da nota)

1. Conferir que a página HTML em `www/` carrega pelo menos uma imagem e um CSS. Assim o navegador faz várias requisições sozinho.
2. Subir o servidor com `--host 0.0.0.0` (já é o padrão) e liberar a porta no firewall.
3. Passar o IP e a porta para o outro grupo e pegar os deles.
4. Abrir no navegador `http://IP_DO_OUTRO_GRUPO:PORTA/` e conferir se a página aparece completa, com a imagem.
5. Se algo não carregar, olhar o log do servidor do grupo que está sendo acessado. Um `404` na imagem costuma ser nome ou pasta errada.
6. Se o navegador pedir `/favicon.ico` e o log mostrar 404, está tudo bem, isso é normal.

Cuidado: o servidor só conhece os tipos do enunciado (`.html`, `.css`, `.js`, `.json`, `.txt`, `.png`, `.jpg`, `.pdf`). Imagens em `.svg`, `.gif` ou `.webp` saem como `application/octet-stream` e o navegador pode não desenhar. Por isso, para a página de teste, o melhor é usar `.png` ou `.jpg`.

### 14.6 Perguntas que o professor pode fazer (além das da seção 10)

- **O que acontece se o `recv` devolver só metade da requisição?** O servidor continua acumulando no buffer até aparecer a linha vazia. Isso está no laço no começo de `atender`.
- **E se chegarem duas requisições juntas?** O `partition` separa a primeira e o resto fica no buffer para a próxima volta do laço.
- **Por que checar `raiz + os.sep` e não só o começo do caminho?** Para uma pasta vizinha com nome parecido (por exemplo `www2`) não passar pela checagem.
- **Por que decodificar antes de verificar o caminho?** Porque `%2e%2e` é `..`. Se checássemos antes, o ataque passaria.
- **Por que `%252e%252e` não escapa?** Decodificamos uma vez só. O resultado é o texto `%2e%2e`, que vira um nome de arquivo que não existe, e a resposta é 404.
- **O `Content-Length` do HEAD é de quanto?** É o tamanho que o corpo teria no GET, como o enunciado pede.
- **Por que uma requisição inválida fecha a conexão?** Depois de um erro de formato não dá para saber onde começa a próxima mensagem. Fechar é o jeito seguro.
- **O que o `Keep-Alive: timeout=5` quer dizer?** Avisa ao cliente que o servidor fecha a conexão depois de 5 segundos sem uso.
- **Thread por conexão aguenta 10 mil clientes?** Não muito bem, porque cada thread consome memória. Para a escala do laboratório funciona bem, e a alternativa seria I/O não bloqueante.
- **Por que o C2 pode ter mais bytes de HTTP por requisição?** Porque as respostas persistentes carregam `Connection: keep-alive` e `Keep-Alive: timeout=5`. Mesmo assim, o total de bytes na rede cai, porque não há 10 handshakes e 10 encerramentos.
- **De onde vem a diferença de tempo entre C1 e C2?** De um handshake a mais em cada conexão nova. Com 10 requisições, C1 abre 10 conexões e C2 abre 1, então esperamos cerca de 9 RTTs de diferença.

### 14.7 Antes de entrar na sala

- [ ] Servidor testado com a pasta `www` final.
- [ ] Wireshark aberto e capturas salvas.
- [ ] Relatório em PDF e zip prontos e já entregues.
- [ ] Cada uma consegue explicar `atender`, `resolver_arquivo` e `montar_cabecalho` sem olhar.
- [ ] Carregadores e adaptadores de rede à mão, caso a rede da sala isole os dispositivos (plano B: hotspot do celular).
