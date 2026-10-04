# Tarefas pendentes do T1

Este arquivo guarda o que ainda falta fazer e o passo a passo de cada tarefa. A **A** é a máquina do servidor (192.168.0.11) e a **B** é a máquina do cliente (192.168.0.3). Antes de qualquer tarefa, confira os IPs com `ipconfig`, porque eles podem mudar de rede para rede.

## Para amanhã

### Tarefa 1: provar que duas máquinas são atendidas ao mesmo tempo

**Por que:** o teste que já fizemos usou só o B (uma conexão ociosa e um `curl` em outra janela). O log do servidor mostra apenas o IP 192.168.0.3. O enunciado pede duas máquinas distintas, e a evidência é um log (ou captura) com dois IPs de origem atendidos ao mesmo tempo.

**Como fazer**
1. No A, suba o servidor e deixe o terminal visível:
   ```powershell
   python .\server.py --port 8080 --root .\www
   ```
2. Nas duas máquinas, ao mesmo tempo, rode este laço apontando para o IP do A:
   ```powershell
   1..30 | ForEach-Object { curl.exe -s -o NUL http://192.168.0.11:8080/a.txt; Start-Sleep -Milliseconds 100 }
   ```
3. O log do servidor deve mostrar linhas de 192.168.0.3 e de 192.168.0.11 intercaladas, com horários iguais ou muito próximos. Tire um print.

**Onde entra no relatório:** seção Solução e Exemplos (nova figura) e a frase da seção Casos de Teste que diz "falta repetir com duas máquinas".

## Evidências que dependem da rede

### Tarefa 2: terceira tentativa de travessia, pela rede

No B, com o servidor rodando no A:

```powershell
curl.exe --path-as-is -i "http://192.168.0.11:8080/..%2fserver.py"
```

O `%2f` é a barra `/` codificada, e o `--path-as-is` impede o curl de arrumar o caminho antes de enviar. A resposta esperada é `HTTP/1.1 403 Forbidden`. Tire um print do terminal do B. Na tabela de segurança do relatório, troque o "repetir no B" da tentativa 3 por "No B, pela rede".

### Tarefa 3: RTT entre as máquinas

No B:

```powershell
ping -n 20 192.168.0.11
```

Anote Mínimo, Máximo e Média e tire um print. Se a média vier como `<1ms` ou `1ms`, o ping é grosso demais. Nesse caso, use o `tcp.analysis.initial_rtt` do handshake na captura do Wireshark.

### Tarefa 4: instalar o Wireshark

Baixe o Wireshark e marque a instalação do **Npcap** quando o instalador oferecer. Sem o Npcap o Wireshark não lista as interfaces de rede.

### Tarefa 5: capturas de C1 e C2

C1 é uma conexão nova por requisição e C2 é uma conexão persistente para as 10 requisições. As duas rodam entre as máquinas, com o `medir.py` no B.

**Capturar C1**
1. Abra o Wireshark no B e escolha a interface que tem o IP 192.168.0.x (Wi-Fi ou Ethernet, a que está com o gráfico mexendo). Não use a de loopback.
2. Antes de iniciar, no campo de filtro de captura (abaixo da lista de interfaces) escreva `tcp port 8080`. Assim a captura guarda só o tráfego do servidor.
3. Dê duplo clique na interface para iniciar e, no PowerShell do B, rode:
   ```powershell
   python .\medir.py --host 192.168.0.11 --port 8080 --path /a.txt --modo c1
   ```
4. Pare a captura (quadrado vermelho) e salve com Ctrl+S como `capturas\c1.pcapng`.
5. Confira: no filtro de exibição digite `tcp.flags.syn==1 && tcp.flags.ack==0`. Devem aparecer **10** pacotes.

**Capturar C2**
1. Inicie uma captura nova. Se o Wireshark perguntar se quer salvar a anterior, escolha continuar sem salvar, porque ela já foi salva.
2. Rode a mesma linha com `--modo c2`.
3. Pare e salve como `capturas\c2.pcapng`.
4. A conferência com o mesmo filtro deve mostrar **1** pacote.

Se o B não tiver Python, o `medir.py` não roda lá. Nesse caso dá para fazer C1 e C2 só com `curl`, ou instalar o Python no B.

### Tarefa 6: captura de um GET completo

1. Inicie outra captura no B (com o filtro `tcp port 8080`).
2. Rode `curl.exe -i http://192.168.0.11:8080/a.txt`.
3. No Wireshark, marque o handshake (SYN, SYN/ACK, ACK), o pacote com a requisição, os pacotes da resposta e o FIN. Dica: botão direito em um pacote, **Follow > TCP Stream**, mostra a conversa inteira.
4. Tire um print com essas partes identificadas.

### Tarefa 7: gerar os números das medições

Com `c1.pcapng` e `c2.pcapng` salvos na pasta `capturas/` (troque `3.5` pela média do ping, em ms):

```bash
python analisar_captura.py capturas/c1.pcapng capturas/c2.pcapng --port 8080 --rtt 3.5
```

O analisador mostra handshakes, pacotes, bytes, tempo, a economia de C2, quanto C1 gasta só abrindo e fechando conexões e quantos RTTs a mais o C1 gasta. A tabela sai pronta para colar no relatório.

### Tarefa 8: teste de interoperabilidade

Com o servidor rodando no A, abra no navegador do B `http://192.168.0.11:8080/`. A página deve aparecer completa, com o banner e o logo. Tire um print da página e, se possível, do log do servidor com as cinco requisições (HTML, CSS, banner, logo e script) com status 200. No dia da aula o teste é feito com o servidor de outro grupo.

## Fechamento

- [ ] Preencher os campos em amarelo do relatório com os resultados reais (RTT, tabela C1 vs C2, overhead, RTTs a mais, versão do Python e modelo dos dispositivos).
- [ ] Escrever a conclusão com os números medidos.
- [ ] Exportar o relatório para PDF e conferir que ficou com no máximo 8 páginas, como o professor pediu em aula.
- [ ] Montar o `.zip` para o Moodle, na mão: `server.py`, `medir.py`, `analisar_captura.py`, `README.md`, `www/`, `capturas/` e o relatório em PDF. Sem binários, arquivos temporários ou de build.
- [ ] Só uma pessoa do grupo faz a entrega, antes do começo da aula de apresentação.
- [ ] Ensaiar a explicação do código com as três presentes, usando a seção 14 do `RELATORIO-APOIO.md`.
