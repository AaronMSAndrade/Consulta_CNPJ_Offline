=========================================================
CONSULTA CNPJ - GUIA DE USO
=========================================================

O QUE E ISTO?
Um sistema para consultar empresas brasileiras (base publica da
Receita Federal). Funciona SEM internet: tudo roda neste computador,
e os dados sao apenas para consulta - nao ha como modifica-los.

---------------------------------------------------------
COMO ABRIR (o dia a dia)
---------------------------------------------------------
1. Dois cliques em:  iniciar.bat
2. O navegador abre sozinho no endereco  http://localhost:8000
   (se nao abrir sozinho, copie esse endereco e cole no navegador)
3. Pronto. Nenhuma janela fica na tela - o app roda por conta propria.

Obs.: se der dois cliques e "nada acontecer", provavelmente o app
JA ESTA aberto - procure a aba do navegador (http://localhost:8000).

---------------------------------------------------------
COMO FECHAR
---------------------------------------------------------
- Dois cliques em:  encerrar.bat
- (ou simplesmente desligue o computador - nada se perde)

---------------------------------------------------------
COMO USAR
---------------------------------------------------------
- BARRA DE BUSCA (topo):
  * Digite um pedaco do nome (ex.: padaria, odontomed) e a lista filtra;
  * Se colar um CNPJ completo (com ou sem pontos), a ficha abre direto.

- FILTROS SEMPRE VISIVEIS (acima da lista):
  * Estado: ao escolher, o menu de Cidade carrega so as cidades dele;
  * Cidade: refine dentro do estado;
  * Atividade (CNAE): comece a digitar (ex.: padaria) e CLIQUE na
    sugestao que aparece.

- MAIS FILTROS (botao):
  * "so com telefone" e "so com e-mail" - otimos para listas de contato;
  * Porte (micro, pequeno, demais);
  * Capital social minima (R$) - proxy do tamanho da empresa.

- INATIVAS (barra amarela no fim):
  * Por padrao aparecem APENAS empresas ATIVAS;
  * Marcar a caixinha inclui baixadas, inaptas, suspensas e nulas.

- LISTA (esquerda):
  * Clique numa empresa para abrir a FICHA COMPLETA a direita:
    telefones (clicaveis), e-mail, endereco, atividade, porte,
    capital social, Simples/MEI e situacao com datas;
  * Os selos vermelho/verde mostram a situacao; MATRIZ/FILIAL mostra
    se o telefone e da sede ou de uma unidade.

- PAGINAS (fim da lista):
  * Numeros estilo Google: 1 2 3 ... ultima pagina. Clique para
    folhear. Mudou o filtro? Volta para a pagina 1 sozinho.
  * O contador no topo mostra quantas empresas casam com o filtro.

---------------------------------------------------------
SE ALGO DER ERRADO
---------------------------------------------------------
- O navegador diz "nao foi possivel acessar este site":
  o app foi fechado. Rode iniciar.bat de novo.
- Duas cliques no iniciar.bat nao abrem nada:
  procure a aba ja aberta no navegador (item "Obs." acima).
- Ainda nada: rode  janela_diagnostico.bat
  uma janela preta mostrara a mensagem de erro. TIRE UMA FOTO e
  envie para quem cuida do sistema. Feche essa janela com Ctrl+C.

- IMPORTANTE: nunca apague nem mova arquivos desta pasta,
  principalmente a pasta "data" - e ali que mora a base (~50 GB).

---------------------------------------------------------
AVISOS
---------------------------------------------------------
- A base e um RETRATO do lote da Receita (setembro/2026). Empresas
  abertas ou alteradas depois disso ainda nao aparecem.
- Tudo funciona sem internet; nada sai deste computador.

=========================================================
PARA O RESPONSAVEL DO SISTEMA
=========================================================
- Atualizacao mensal: coloque os novos CSVs em arquivos_receita\
  e rode no PowerShell, NESTA ORDEM, dentro da pasta do sistema:
      python importar.py     (~20 min, reconstroi o banco do zero)
      python preparar.py     (~50 min, monta as tabelas do app)
      python otimizar.py     (~15 min, indices de velocidade)
  Depois teste com iniciar.bat antes de distribuir.

- Copiar para outro computador (uso):
      servidor.py + iniciar.bat + encerrar.bat +
      janela_diagnostico.bat + READ_ME.txt + pasta data\
  O PC de destino precisa do Python (python.org) instalado com a
  opcao "Add python.exe to PATH" marcada. NAO copie importar.py,
  preparar.py, otimizar.py nem arquivos_receita\ - sao da fabrica.

- Copiar para outro computador (fabrica completa): a pasta inteira,
  incluindo arquivos_receita\ e os 3 scripts de fabrica.