# T1-Lab-Redes

funcionamento dos metodos principais:

decodificar_percent: Percorre o texto byte a byte: quando acha um %, lê os dois bytes seguintes, interpreta como hexadecimal e junta o byte decodificado no resultado

resolver_string: Corta query string e fragment, decodifica percent-encoding, tira a / inicial e junta com a raiz.

montar_cabecalho: Monta os cabeçalhos de uma resposta HTTP como texto

enviar_arquivo: Manda o cabeçalho pelo socket. Se for uma requisição HEAD, para por aí. Senão, abre o arquivo em modo binário e vai lendo em blocos de 64 KB, mandando cada bloco pelo socket.

enviar_erro:Mesma lógica para respostas de erro, monta um corpo HTML simples com o código e a descrição, gera o cabeçalho via montar_cabecalho e manda os dois pelo socket.

responder: É o "roteador" que decide o que fazer com a requisição já interpretada.

interpretar_requisicao: Recebe os bytes brutos do cabeçalho e extrai método, alvo e versão.

tamanho_do_corpo: Lê o Content-Length dos cabeçalhos para saber quantos bytes de corpo vêm depois do cabeçalho.

deve_fechar: Olha o cabeçalho Connection e verifica se um dos valores é close.

atender: Roda em loop, atendendo uma requisição por vez na mesma conexão
