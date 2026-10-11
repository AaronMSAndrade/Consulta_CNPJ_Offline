# preparar.py (v3) - fabrica 2/3: vista + busca + listas, dentro de data\cnpj.db
import os, sys, time, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data", "cnpj.db")
def fmt(n): return format(n, ",d").replace(",", ".")
t0 = time.time()
if not os.path.exists(DB):
    print("ERRO: cnpj.db nao encontrado em " + DB + " - rode importar.py primeiro."); sys.exit(1)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=OFF")
cur.execute("PRAGMA synchronous=OFF")
cur.execute("PRAGMA cache_size=-262144")
tabs = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
faltam = [t for t in ["empresa","estabelecimento","simples","municipio","cnae"] if t not in tabs]
if faltam:
    print("ERRO: tabela(s) ausente(s): " + ", ".join(faltam)); sys.exit(1)
print("Limpando pecas de app antigas (se houver)...", flush=True)
for nome in ["vista", "busca", "lista_uf_cidade"]:
    cur.execute("DROP TABLE IF EXISTS " + nome)
conn.commit()
print("[1/4] criando e enchendo VISTA (matrizes + filiais decodificadas)...", flush=True)
t1 = time.time()
cur.execute("""CREATE TABLE vista (
  cnpj_basico TEXT, cnpj_ordem TEXT, cnpj_dv TEXT,
  razao_social TEXT, nome_fantasia TEXT, situacao TEXT, mf TEXT,
  uf TEXT, municipio_cod TEXT, municipio_nome TEXT,
  cnae_cod TEXT, cnae_nome TEXT,
  ddd1 TEXT, telefone1 TEXT, email TEXT,
  tem_tel INTEGER, tem_email INTEGER,
  porte TEXT, capital REAL, abertura TEXT)""")
sql_sel = """
SELECT e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv,
       emp.razao_social, e.nome_fantasia, e.situacao_cadastral, e.matriz_filial,
       e.uf, e.municipio, m.descricao,
       e.cnae_principal, cn.descricao,
       e.ddd1, e.telefone1, e.email,
       CASE WHEN TRIM(COALESCE(e.telefone1,''))='' THEN 0 ELSE 1 END,
       CASE WHEN TRIM(COALESCE(e.email,''))='' THEN 0 ELSE 1 END,
       emp.porte,
       CAST(REPLACE(REPLACE(COALESCE(emp.capital_social,''),'.',''),',','.') AS REAL),
       e.data_inicio_atividade
FROM estabelecimento e
JOIN empresa emp ON emp.cnpj_basico = e.cnpj_basico
LEFT JOIN municipio m ON m.codigo = e.municipio
LEFT JOIN cnae cn ON cn.codigo = e.cnae_principal
"""
ins = "INSERT INTO vista VALUES (" + ",".join(["?"]*20) + ")"
rs = conn.cursor().execute(sql_sel)
lote = []; total = 0
for row in rs:
    lote.append(row)
    if len(lote) >= 200000:
        cur.executemany(ins, lote); conn.commit(); lote = []
        total += 200000
        if total % 2000000 == 0: print("   vista: %s linhas" % fmt(total), flush=True)
if lote:
    total += len(lote); cur.executemany(ins, lote); conn.commit()
print("[OK] vista: %s linhas em %d min" % (fmt(total), round((time.time()-t1)/60)), flush=True)
print("[2/4] criando o INDICE DE BUSCA por nome...", flush=True)
t1 = time.time()
cur.execute('CREATE VIRTUAL TABLE busca USING fts5(nome, tokenize = "unicode61 remove_diacritics 1")')
insb = "INSERT INTO busca(rowid, nome) VALUES (?,?)"
rs = conn.cursor().execute("SELECT rowid, TRIM(COALESCE(nome_fantasia,'')||' '||COALESCE(razao_social,'')) FROM vista")
lote = []; total = 0
for row in rs:
    lote.append(row)
    if len(lote) >= 200000:
        cur.executemany(insb, lote); lote = []; total += 200000
        if total % 4000000 == 0: print("   busca: %s" % fmt(total), flush=True)
if lote:
    total += len(lote); cur.executemany(insb, lote)
conn.commit()
print("[OK] busca: %s entradas em %d min" % (fmt(total), round((time.time()-t1)/60)), flush=True)
print("[3/4] lista de estados e cidades...", flush=True)
t1 = time.time()
cur.execute("CREATE TABLE lista_uf_cidade (uf TEXT, cidade TEXT)")
cur.execute("INSERT INTO lista_uf_cidade SELECT DISTINCT uf, municipio_nome FROM vista WHERE uf<>'' ORDER BY uf, municipio_nome")
conn.commit()
n = cur.execute("SELECT COUNT(*) FROM lista_uf_cidade").fetchone()[0]
print("[OK] lista_uf_cidade: %s pares em %d min" % (fmt(n), round((time.time()-t1)/60)), flush=True)
print("[4/4] indice de lookup do banco bruto (silencioso)...", flush=True)
t1 = time.time()
cur.execute("CREATE INDEX IF NOT EXISTS idx_vista_fila ON vista(rowid)")
cur.execute("DROP INDEX IF EXISTS idx_vista_fila")
conn.commit()
print("[OK] concluido em %d min" % round((time.time()-t1)/60), flush=True)
n_vista = cur.execute("SELECT COUNT(*) FROM vista").fetchone()[0]
n_ativas = cur.execute("SELECT COUNT(*) FROM vista WHERE situacao='02'").fetchone()[0]
n_matrizes = cur.execute("SELECT COUNT(*) FROM vista WHERE mf='1'").fetchone()[0]
print("   vista total: %s (esperado ~73.366.198)" % fmt(n_vista), flush=True)
print("   ativas: %s (esperado 28.263.127)" % fmt(n_ativas), flush=True)
print("   matrizes: %s (esperado ~70.085.594)" % fmt(n_matrizes), flush=True)
achou = 0
for (nome,) in conn.cursor().execute("SELECT v.razao_social FROM busca b JOIN vista v ON v.rowid=b.rowid WHERE busca MATCH 'padaria*' LIMIT 3"):
    print("   busca de teste 'padaria': " + (nome or ""), flush=True)
    achou += 1
print("   resultados da busca de teste: %d (esperado 3)" % achou, flush=True)
conn.close()
print("Banco: %.1f GB" % (os.path.getsize(DB)/1073741824), flush=True)
print("TEMPO TOTAL DA PREPARACAO: %d min" % round((time.time()-t0)/60), flush=True)
print("PROXIMO PASSO: python otimizar.py")
