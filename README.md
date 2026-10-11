# Filtro de CNPJ Offline Gratis 🇧🇷
programa pra transformar os arquivos oficiais da receita em algo mais "visualizavel" usando python

Sistema local e ultrarrápido para filtrar empresas brasileiras usando a base pública da Receita Federal. Funciona totalmente sem internet!

filtros de empresas por: Estado, cidade, CNAE, ativo/inativo e porte.

⚙️ Configuração Inicial (Importante)

Como os arquivos da Receita Federal são grandes e gerados localmente, antes de rodar os scripts de importação, você precisa criar duas pastas na raiz do diretório do projeto:

arquivos_receita : Onde você colocará os arquivos .csv originais da Receita disponiveis no link abaixo:

arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9

data : Onde o banco de dados processado será armazenado (~50 GB).

seu-repositorio/

├── arquivos_receita  <-- Crie esta pasta e coloque os CSVs aqui

├── data              <-- Crie esta pasta vazia para o banco de dados

└── ...

🚀 Como Usar no Dia a Dia

Dê dois cliques em iniciar.bat.

O navegador abrirá automaticamente em http://localhost:8000.

Para fechar, basta dar dois cliques em encerrar.bat.

🛠️ Atualização e Configuração Inicial da Base:

Coloque os arquivos CSVs na pasta arquivos_receita e execute no PowerShell:

python importar.py

python preparar.py

python otimizar.py
