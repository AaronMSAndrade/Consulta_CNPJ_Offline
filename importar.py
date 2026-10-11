# importar.py (v3) - fabrica 1/3: CSVs de arquivos_receita\ -> data\cnpj.db
import csv, os, sys, time, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(BASE, "arquivos_receita")
DB = os.path.join(BASE, "data", "cnpj.db")
LOTE = 100000
MARCO = 500000
t0_geral = time.time()

def achar(lista, trecho):
    return sorted([a for a in lista if trecho.upper() in a.upper()])

if not os.path.isdir(PASTA):
    print("ERRO: pasta nao encontrada: " + PASTA); sys.exit(1)
os.makedirs(os.path.dirname(DB), exist_ok=True)
arquivos = os.listdir(PASTA)

f_empre = achar(arquivos, "EMPRECSV")
f_estab = achar(arquivos, "ESTABELE")
f_simples = achar(arquivos, "SIMPLES")
f_pais = achar(arquivos, "PAISCSV")
f_quals = achar(arquivos, "QUALSCSV")
f_natju = achar(arquivos, "NATJUCSV")
f_munic = achar(arquivos, "MUNICCSV")
f_cnae = achar(arquivos, "CNAECSV")
f_moti = achar(arquivos, "MOTICSV")

erros = []
if len(f_empre) != 10: erros.append("EMPRECSV: achei %d arquivo(s), esperava 10" % len(f_empre))
if len(f_estab) != 10: erros.append("ESTABELE: achei %d arquivo(s), esperava 10" % len(f_estab))
if not f_simples: erros.append("SIMPLES: nao achei o arquivo")
for nome, lst in [("PAISCSV", f_pais), ("QUALSCSV", f_quals), ("NATJUCSV", f_natju),
                  ("MUNICCSV", f_munic), ("CNAECSV", f_cnae), ("MOTICSV", f_moti)]:
    if not lst: erros.append("Auxiliar faltando: " + nome)
if erros:
    print("PROBLEMAS COM OS ARQUIVOS EM arquivos_receita:")
    for e in erros: print("  - " + e)
    sys.exit(1)

if os.path.exists(DB):
    print("Ja existia um cnpj.db - apagando para recomecar do zero...")
    os.remove(DB)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=OFF")
cur.execute("PRAGMA synchronous=OFF")
cur.execute("PRAGMA cache_size=-65536")

cur.execute("CREATE TABLE pais (codigo TEXT, nome TEXT)")
cur.execute("CREATE TABLE qualificacao (codigo TEXT, descricao TEXT)")
cur.execute("CREATE TABLE natureza_juridica (codigo TEXT, descricao TEXT)")
cur.execute("CREATE TABLE municipio (codigo TEXT, descricao TEXT)")
cur.execute("CREATE TABLE cnae (codigo TEXT, descricao TEXT)")
cur.execute("CREATE TABLE motivo (codigo TEXT, descricao TEXT)")
cur.execute("""CREATE TABLE empresa (cnpj_basico TEXT, razao_social TEXT,
    natureza_juridica TEXT, qualificacao_responsavel TEXT, capital_social TEXT,
    porte TEXT, ente_federativo TEXT)""")
cur.execute("""CREATE TABLE estabelecimento (cnpj_basico TEXT, cnpj_ordem TEXT,
    cnpj_dv TEXT, matriz_filial TEXT, nome_fantasia TEXT,
    situacao_cadastral TEXT, data_situacao_cadastral TEXT, motivo_situacao TEXT,
    nome_cidade_exterior TEXT, pais TEXT, data_inicio_atividade TEXT,
    cnae_principal TEXT, cnaes_secundarias TEXT, tipo_logradouro TEXT,
    logradouro TEXT, numero TEXT, complemento TEXT, bairro TEXT, cep TEXT,
    uf TEXT, municipio TEXT, ddd1 TEXT, telefone1 TEXT, ddd2 TEXT,
    telefone2 TEXT, ddd_fax TEXT, fax TEXT, email TEXT,
    situacao_especial TEXT, data_situacao_especial TEXT)""")
cur.execute("""CREATE TABLE simples (cnpj_basico TEXT, opcao_simples TEXT,
    data_opcao_simples TEXT, data_exclusao_simples TEXT, opcao_mei TEXT,
    data_opcao_mei TEXT, data_exclusao_mei TEXT)""")
conn.commit()

totais = {}

def importar(caminho, sql, n_cols, rotulo):
    t0 = time.time(); total = 0; anomalias = 0; marco = 0; lote = []
    with open(caminho, "r", encoding="latin-1", newline="") as f:
        leitor = csv.reader(f, delimiter=";", quotechar='"')
        for linha in leitor:
            if not linha or (len(linha) == 1 and linha[0].strip() == ""): continue
            if len(linha) != n_cols:
                anomalias += 1
                if len(linha) < n_cols: linha = linha + [""] * (n_cols - len(linha))
                else: linha = linha[:n_cols]
            lote.append(linha); total += 1
            if len(lote) >= LOTE:
                cur.executemany(sql, lote); conn.commit(); lote = []
                if total // MARCO != marco:
                    marco = total // MARCO
                    print("   %s: %s linhas" % (rotulo, format(total, ",d").replace(",", ".")), flush=True)
    if lote:
        cur.executemany(sql, lote); conn.commit()
    print("[OK] %-16s %s linhas em %ds" % (rotulo, format(total, ",d").replace(",", "."), round(time.time() - t0)), flush=True)
    totais[rotulo] = totais.get(rotulo, 0) + total
    return anomalias

anom_total = 0
print("=== 1/4 - arquivos auxiliares ===", flush=True)
for lst, tabela in [(f_pais, "pais"), (f_quals, "qualificacao"),
                    (f_natju, "natureza_juridica"), (f_munic, "municipio"),
                    (f_cnae, "cnae"), (f_moti, "motivo")]:
    print("[..] " + lst[0], flush=True)
    anom_total += importar(os.path.join(PASTA, lst[0]),
                           "INSERT INTO " + tabela + " VALUES (?,?)", 2, tabela)

print("=== 2/4 - empresas (10 partes) ===", flush=True)
for nome in f_empre:
    print("[..] " + nome, flush=True)
    anom_total += importar(os.path.join(PASTA, nome),
                           "INSERT INTO empresa VALUES (?,?,?,?,?,?,?)", 7, "empresa")

print("=== 3/4 - estabelecimentos (10 partes) ===", flush=True)
sql_est = "INSERT INTO estabelecimento VALUES (" + ",".join(["?"] * 30) + ")"
for nome in f_estab:
    print("[..] " + nome, flush=True)
    anom_total += importar(os.path.join(PASTA, nome), sql_est, 30, "estabelecimento")

print("=== 4/4 - simples/MEI ===", flush=True)
print("[..] " + f_simples[0], flush=True)
anom_total += importar(os.path.join(PASTA, f_simples[0]),
                       "INSERT INTO simples VALUES (?,?,?,?,?,?,?)", 7, "simples")

print("=== indices basicos (etapa final) ===", flush=True)
t0 = time.time()
cur.execute("CREATE INDEX idx_empresa_cnpj ON empresa(cnpj_basico)")
cur.execute("CREATE INDEX idx_estab_cnpj ON estabelecimento(cnpj_basico)")
cur.execute("CREATE INDEX idx_simples_cnpj ON simples(cnpj_basico)")
conn.commit()
print("[OK] indices prontos em %ds" % round(time.time() - t0), flush=True)
conn.close()
print("", flush=True)
print("=========== RESUMO ===========")
for k in ["pais", "qualificacao", "natureza_juridica", "municipio", "cnae",
          "motivo", "empresa", "estabelecimento", "simples"]:
    if k in totais: print("%-16s %s" % (k, format(totais[k], ",d").replace(",", ".")))
print("linhas ajustadas: %d" % anom_total)
print("Banco gerado: %s (%.1f GB)" % (DB, os.path.getsize(DB) / 1073741824))
print("Tempo total: %d min" % round((time.time() - t0_geral) / 60))
print("PROXIMO PASSO: python preparar.py")
