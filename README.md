# Consulta CNPJ Offline 🇧🇷
programa pra transformar os arquivos da receita em algo mais "visualizavel"
Sistema local e ultrarrápido para consultar empresas brasileiras usando a base pública da Receita Federal. Funciona totalmente sem internet!

⚙️ Configuração Inicial (Importante)

Como os arquivos da Receita Federal são grandes e gerados localmente, antes de rodar os scripts de importação, você precisa criar duas pastas na raiz do diretório do projeto:

arquivos_receita: Onde você colocará os arquivos .csv originais da Receita.

data: Onde o banco de dados processado será armazenado (~50 GB).

seu-repositorio/
├── arquivos_receita/  <-- Crie esta pasta e coloque os CSVs aqui
├── data/              <-- Crie esta pasta vazia para o banco de dados
├── iniciar.bat
└── ...


🚀 Como Usar no Dia a Dia

Dê dois cliques em iniciar.bat.

O navegador abrirá automaticamente em http://localhost:8000.

Para fechar, basta dar dois cliques em encerrar.bat.

🛠️ Atualização da Base (Para administradores)

Coloque os novos CSVs na pasta arquivos_receita\ e execute no PowerShell:

python importar.py
python preparar.py
python otimizar.py
