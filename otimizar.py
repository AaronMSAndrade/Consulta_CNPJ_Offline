# otimizar.py (v3) - fabrica 3/3: os 3 indices de filtro + ANALIZE (fusao do turbo + corrigir_indice)
import os, time, sqlite3
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data", "cnpj.db")
t0 = time.time()
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("PRAGMA synchronous=OFF")
cur.execute("PRAGMA cache_size=-262144")
print("Banco: " + DB, flush=True)
print("[1/3] removendo indices de filtro antigos (se houver)...", flush=True)
for idx in ["idx_vista_geo","idx_vista_cnae","idx_vista_uf_cid",
            "idx_vista_uf_nome","idx_vista_uf","idx_vista_cnae2"]:
    cur.execute("DROP INDEX IF EXISTS " + idx)
conn.commit()
planos = [
    ("idx_vista_uf_nome", "CREATE INDEX idx_vista_uf_nome ON vista(uf, municipio_nome, situacao)"),
    ("idx_vista_uf",      "CREATE INDEX idx_vista_uf      ON vista(uf, situacao)"),
    ("idx_vista_cnae2",   "CREATE INDEX idx_vista_cnae2   ON vista(cnae_cod, situacao)"),
]
for i, (nome, sql) in enumerate(planos, 1):
    t1 = time.time()
    print("[%d/3] criando %s (silencioso, varios minutos)..." % (i, nome), flush=True)
    cur.execute(sql)
    conn.commit()
    print("[OK] %s em %d min" % (nome, round((time.time() - t1) / 60)), flush=True)
print("[3/3] ANALIZE (ensina o banco a escolher a melhor rota)...", flush=True)
t1 = time.time()
cur.execute("PRAGMA analysis_limit=4000")
cur.execute("ANALYZE")
conn.commit()
print("[OK] analize em %d min" % round((time.time() - t1) / 60), flush=True)
conn.close()
print("Banco final: %.1f GB" % (os.path.getsize(DB) / 1073741824), flush=True)
print("TEMPO TOTAL: %d min" % round((time.time() - t0) / 60), flush=True)
print("OTIMIZACAO CONCLUIDA - o app esta pronto: iniciar.bat")
