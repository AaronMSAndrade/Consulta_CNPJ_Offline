# -*- coding: utf-8 -*-
# servidor.py (v3) - App web LOCAL, somente-leitura, portatil.
# Estrutura: banco em data\cnpj.db (mesma pasta deste arquivo).
import os, re, sys, json, socket, sqlite3, threading, webbrowser
from urllib.parse import urlparse, parse_qs, quote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PASTA = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PASTA, "data", "cnpj.db")
PIDFILE = os.path.join(PASTA, "servidor.pid")
PORTA = 8000

SITUACAO = {"01":"Nula","02":"Ativa","03":"Suspensa","04":"Inapta","08":"Baixada"}
PORTE = {"00":"Nao informado","01":"Microempresa","03":"Pequeno porte","05":"Demais tamanhos"}
MF = {"1":"MATRIZ","2":"FILIAL"}
AUX = {"cnae":{},"municipio":{},"natureza":{},"qualificacao":{},"motivo":{},"pais":{}}
CNAE_LISTA = []; UF_LISTA = []; UF_CIDADES = {}
_cache_total = {}; _cache_ordem = []

def log(*a, **k):
    try: print(*a, flush=True)
    except Exception: pass

def conectar():
    p = DB.replace("\\","/")
    if not p.startswith("/"): p = "/" + p
    uri = "file:" + quote(p, safe="/:.") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def S(x): return (x or "").strip()

def fdata(s):
    s = S(s)
    if len(s)==8 and s.isdigit(): return s[6:8]+"/"+s[4:6]+"/"+s[0:4]
    return s

def fcapital(x):
    try: x = float(x)
    except (TypeError, ValueError): return ""
    s = "{:,.2f}".format(x)
    return "R$ " + s.replace(",","X").replace(".",",").replace("X",".")

def fcep(c):
    c = S(c)
    if len(c)==8 and c.isdigit(): return c[:5]+"-"+c[5:]
    return c

def fcnpj(b,o,dv):
    b,o,dv = S(b),S(o),S(dv)
    if len(b)==8 and len(o)==4 and len(dv)==2:
        return b[:2]+"."+b[2:5]+"."+b[5:]+"/"+o+"-"+dv
    return b+o+dv

def fts_query(q):
    toks = [t for t in re.split(r"\W+", q) if t]
    toks = [t for t in toks if t.upper() not in ("AND","OR","NOT","NEAR")][:8]
    return " AND ".join(t+"*" for t in toks)

def checar():
    con = conectar()
    tabs = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    falta = [t for t in ["vista","busca","lista_uf_cidade","empresa","estabelecimento",
                         "simples","cnae","municipio","natureza_juridica","qualificacao","motivo","pais"] if t not in tabs]
    if falta:
        log("Falta no banco: " + ", ".join(falta))
        log("Rode importar.py e depois preparar.py nesta pasta primeiro."); sys.exit(1)

def carregar_memoria():
    global CNAE_LISTA, UF_LISTA, UF_CIDADES
    con = conectar()
    AUX["cnae"] = {r[0]:r[1] for r in con.execute("SELECT codigo,descricao FROM cnae")}
    AUX["municipio"] = {r[0]:r[1] for r in con.execute("SELECT codigo,descricao FROM municipio")}
    AUX["natureza"] = {r[0]:r[1] for r in con.execute("SELECT codigo,descricao FROM natureza_juridica")}
    AUX["qualificacao"] = {r[0]:r[1] for r in con.execute("SELECT codigo,descricao FROM qualificacao")}
    AUX["motivo"] = {r[0]:r[1] for r in con.execute("SELECT codigo,descricao FROM motivo")}
    AUX["pais"] = {r[0]:r[1] for r in con.execute("SELECT codigo,nome FROM pais")}
    CNAE_LISTA = [{"c":c,"n":n} for c,n in con.execute("SELECT codigo,descricao FROM cnae ORDER BY descricao")]
    UF_CIDADES = {}
    for uf, nome in con.execute("SELECT uf, cidade FROM lista_uf_cidade WHERE uf<>'' AND cidade<>'' ORDER BY uf, cidade"):
        UF_CIDADES.setdefault(uf, []).append(nome)
    UF_LISTA = sorted(UF_CIDADES.keys())
    con.close()

def filtros(qs):
    def g(k,d=""):
        v = qs.get(k); return v[0] if v else d
    conds, args = [], []
    if g("inat") != "1": conds.append("v.situacao='02'")
    uf = g("uf").upper()[:2]
    if uf: conds.append("v.uf=?"); args.append(uf)
    cid = g("cidade")
    if cid: conds.append("v.municipio_nome=?"); args.append(cid)
    cn = g("cnae")
    if re.match(r"^\d{5,7}$", cn): conds.append("v.cnae_cod=?"); args.append(cn)
    if g("tel")=="1": conds.append("v.tem_tel=1")
    if g("mail")=="1": conds.append("v.tem_email=1")
    po = g("porte")
    if po in ("00","01","03","05"): conds.append("v.porte=?"); args.append(po)
    cap = g("capmin").replace(",",".")
    if cap:
        try: conds.append("v.capital>=?"); args.append(float(cap))
        except ValueError: pass
    try: off = max(0, int(g("off","0")))
    except ValueError: off = 0
    return conds, args, g("q"), off

def linha_json(r):
    tel = (S(r["ddd1"])+" "+S(r["telefone1"])).strip()
    return {"d": S(r["cnpj_basico"])+S(r["cnpj_ordem"])+S(r["cnpj_dv"]),
            "dfmt": fcnpj(r["cnpj_basico"],r["cnpj_ordem"],r["cnpj_dv"]),
            "rs": S(r["razao_social"]), "nf": S(r["nome_fantasia"]),
            "st": SITUACAO.get(S(r["situacao"]), S(r["situacao"]) or "-"),
            "mf": MF.get(S(r["mf"]), S(r["mf"]) or "-"),
            "uf": S(r["uf"]), "cid": S(r["municipio_nome"]),
            "tel": tel, "em": S(r["email"]),
            "cnae": S(r["cnae_nome"])[:60]}

def api_empresas(qs):
    conds, args, q, off = filtros(qs)
    ftq = fts_query(q)
    W = (" AND " + " AND ".join(conds)) if conds else ""
    con = conectar()
    if ftq:
        try:
            rows = con.execute("SELECT v.rowid AS rid, v.* FROM busca b JOIN vista v ON v.rowid=b.rowid WHERE busca MATCH ?"+W+" ORDER BY b.rank LIMIT 100 OFFSET ?", [ftq]+args+[off]).fetchall()
        except sqlite3.OperationalError:
            rows = con.execute("SELECT v.rowid AS rid, v.* FROM busca b JOIN vista v ON v.rowid=b.rowid WHERE busca MATCH ?"+W+" LIMIT 100 OFFSET ?", [ftq]+args+[off]).fetchall()
    else:
        rows = con.execute("SELECT v.rowid AS rid, v.* FROM vista v"+(" WHERE "+" AND ".join(conds) if conds else "")+" LIMIT 100 OFFSET ?", args+[off]).fetchall()
    con.close()
    return {"linhas":[linha_json(r) for r in rows]}

def total_contado(conds, args, ftq):
    chave = (ftq, tuple(conds), tuple(str(a) for a in args))
    if chave in _cache_total: return _cache_total[chave]
    W = (" AND " + " AND ".join(conds)) if conds else ""
    con = conectar()
    if ftq:
        n = con.execute("SELECT COUNT(*) FROM busca b JOIN vista v ON v.rowid=b.rowid WHERE busca MATCH ?"+W, [ftq]+args).fetchone()[0]
    else:
        n = con.execute("SELECT COUNT(*) FROM vista v"+(" WHERE "+" AND ".join(conds) if conds else ""), args).fetchone()[0]
    con.close()
    _cache_total[chave] = n
    _cache_ordem.append(chave)
    if len(_cache_ordem) > 80:
        velha = _cache_ordem.pop(0)
        _cache_total.pop(velha, None)
    return n

def api_total(qs):
    conds, args, q, off = filtros(qs)
    return {"n": total_contado(conds, args, fts_query(q))}

def api_empresa(d):
    d = re.sub(r"\D","",d or "")
    if len(d)!=14: return {"erro":"CNPJ invalido (precisa de 14 digitos)"}
    b,o,dv = d[:8],d[8:12],d[12:14]
    con = conectar()
    e = con.execute("SELECT * FROM estabelecimento WHERE cnpj_basico=? AND cnpj_ordem=? AND cnpj_dv=?",(b,o,dv)).fetchone()
    if not e:
        con.close(); return {"erro":"CNPJ nao encontrado na base"}
    emp = con.execute("SELECT * FROM empresa WHERE cnpj_basico=? LIMIT 1",(b,)).fetchone()
    sp  = con.execute("SELECT * FROM simples WHERE cnpj_basico=?",(b,)).fetchone()
    con.close()
    st = S(e["situacao_cadastral"])
    tel1 = (S(e["ddd1"])+" "+S(e["telefone1"])).strip()
    tel2 = (S(e["ddd2"])+" "+S(e["telefone2"])).strip()
    fax  = (S(e["ddd_fax"])+" "+S(e["fax"])).strip()
    mcode = S(e["municipio"])
    sec, seen = [], set()
    raw = S(e["cnaes_secundarias"])
    parts = []
    if raw:
        if "," in raw: parts = [p.strip() for p in raw.split(",") if p.strip()]
        elif raw.isdigit() and len(raw)%7==0: parts = [raw[i:i+7] for i in range(0,len(raw),7)]
        for p in parts:
            if p and p not in seen and p != S(e["cnae_principal"]):
                seen.add(p); sec.append({"c":p,"n":AUX["cnae"].get(p,"")})
            if len(sec)>=15: break
    j = {"cnpj":fcnpj(b,o,dv), "tipo":MF.get(S(e["matriz_filial"]), S(e["matriz_filial"]) or "-"),
         "razao":S(emp["razao_social"]) if emp else "", "fantasia":S(e["nome_fantasia"]),
         "situacao":SITUACAO.get(st, st or "-"), "data_situacao":fdata(e["data_situacao_cadastral"]),
         "motivo":AUX["motivo"].get(S(e["motivo_situacao"]),""), "abertura":fdata(e["data_inicio_atividade"]),
         "sit_esp":S(e["situacao_especial"]), "data_esp":fdata(e["data_situacao_especial"]),
         "nj":AUX["natureza"].get(S(emp["natureza_juridica"]),"") if emp else "",
         "qualif":AUX["qualificacao"].get(S(emp["qualificacao_responsavel"]),"") if emp else "",
         "porte":PORTE.get(S(emp["porte"]),"") if emp else "",
         "capital":fcapital(emp["capital_social"]) if emp else "",
         "ente":S(emp["ente_federativo"]) if emp else "",
         "cnae_p":{"c":S(e["cnae_principal"]),"n":AUX["cnae"].get(S(e["cnae_principal"]),"")},
         "cnae_s":sec,
         "logr":" ".join([x for x in [S(e["tipo_logradouro"]),S(e["logradouro"])] if x]),
         "numero":S(e["numero"]), "compl":S(e["complemento"]), "bairro":S(e["bairro"]),
         "cidade":AUX["municipio"].get(mcode,""), "uf":S(e["uf"]), "cep":fcep(e["cep"]),
         "ext":S(e["nome_cidade_exterior"]),
         "pais":AUX["pais"].get(S(e["pais"]),"") if S(e["pais"]) and S(e["pais"])!="0" else "",
         "tel1":tel1, "tel2":tel2, "fax":fax, "email":S(e["email"])}
    if sp:
        def op(x): return {"S":"Sim","N":"Nao"}.get(S(x).upper(), S(x))
        j["simples"] = {"simples":op(sp["opcao_simples"]), "d_s":fdata(sp["data_opcao_simples"]),
                        "x_s":fdata(sp["data_exclusao_simples"]), "mei":op(sp["opcao_mei"]),
                        "d_m":fdata(sp["data_opcao_mei"]), "x_m":fdata(sp["data_exclusao_mei"])}
    return j

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consulta CNPJ</title><style>
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:14px;background:#eef1f5;color:#111}
#topo{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#1e3a5f;color:#fff}
#topo .logo{font-weight:700;white-space:nowrap}
#q{flex:1;padding:9px 12px;border:0;border-radius:8px;font-size:14px;min-width:140px}
#corpo{display:flex;height:calc(100vh - 54px)}
#esq{flex:2;display:flex;flex-direction:column;min-width:0}
#dir{flex:1;border-left:1px solid #d5dbe3;background:#fff;overflow-y:auto}
#filtros{display:flex;gap:8px;padding:10px 14px;background:#fff;border-bottom:1px solid #e2e6ec;flex-wrap:wrap;align-items:center}
#filtros select,#filtros input,#mf select,#mf input{padding:8px 10px;border:1px solid #c6cdd6;border-radius:8px;font-size:14px;background:#fff}
#uf{max-width:130px}#cidade{max-width:220px}#cnae{flex:1;min-width:170px;max-width:330px}
#btnmf,#limpar{padding:8px 12px;border:1px solid #c6cdd6;background:#f6f8fa;border-radius:8px;cursor:pointer}
#mf{display:flex;gap:14px;padding:10px 14px;background:#f8fafc;border-bottom:1px solid #e2e6ec;flex-wrap:wrap;align-items:center}
#mf label{display:flex;gap:6px;align-items:center;white-space:nowrap}
#barrainat{padding:8px 14px;background:#fff8e6;border-bottom:1px solid #f0e3bd}
#barrainat label{display:flex;gap:6px;align-items:center}
#reshead{padding:8px 14px;color:#475569;font-size:13px}
#lista{flex:1;overflow-y:auto;background:#fff}
.item{padding:10px 14px;border-bottom:1px solid #edf0f4;cursor:pointer}
.item:hover{background:#f2f7ff}.item.sel{background:#e3edff}
.l1{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.nome{font-weight:600}.l2{color:#333;margin-top:2px}.dim{color:#7b8794}
.l3{color:#555;margin-top:2px;font-size:13px}.l4{color:#2563eb;margin-top:3px;font-size:12.5px;font-weight:600;letter-spacing:.4px}
.b{font-size:11px;padding:1px 8px;border-radius:9px;white-space:nowrap}
.bA{background:#dcfce7;color:#166534}.bI{background:#fee2e2;color:#991b1b}
.bM{background:#dbeafe;color:#1e40af}.bF{background:#e5e7eb;color:#374151}
#rodape{padding:10px 12px 14px;text-align:center;background:#fff;border-top:1px solid #e2e6ec}
#paginacao{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;align-items:center}
.pg{min-width:36px;padding:7px 10px;border:1px solid #c6cdd6;border-radius:8px;background:#f6f8fa;cursor:pointer;font-size:13.5px;color:#111}
.pg:hover{background:#eef4ff}
.pg.cur{background:#1e3a5f;color:#fff;border-color:#1e3a5f;font-weight:700}
.pts{color:#7b8794;padding:0 2px}
#paginfo{font-size:12px;margin-top:6px}
.oculto{display:none!important}
.carregando,.erro,.placeholder{padding:26px;text-align:center;color:#7b8794}.erro{color:#b91c1c}
#card{padding:16px}
.chead .cnpjbox{display:flex;gap:8px;align-items:center;font-weight:700;font-size:16px;color:#2563eb;letter-spacing:.5px;flex-wrap:wrap}
.chead h2{margin:8px 0 2px;font-size:17px;line-height:1.3}.fant{color:#475569;margin-bottom:6px}
.sec{margin-top:14px;border-top:1px solid #edf0f4;padding-top:10px}
.sec h3{margin:0 0 8px;font-size:11.5px;text-transform:uppercase;color:#7b8794;letter-spacing:.8px}
.kv{display:grid;grid-template-columns:150px 1fr;gap:3px 10px;margin-bottom:4px}
.kv span{color:#6b7280}.kv b{font-weight:600;word-break:break-word}
.linha{margin-bottom:3px}
#sug{position:fixed;display:none;background:#fff;border:1px solid #c6cdd6;border-radius:8px;box-shadow:0 8px 22px rgba(0,0,0,.12);z-index:50;max-height:280px;overflow:auto;cursor:pointer}
#sug div{padding:8px 10px;border-bottom:1px solid #f1f3f6}#sug div:hover{background:#eef4ff}
a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}
@media(max-width:920px){#corpo{flex-direction:column;height:auto}#dir{border-left:0;border-top:1px solid #d5dbe3;max-height:55vh}#lista{max-height:50vh}}
</style></head><body>
<div id="topo"><span class="logo">Consulta CNPJ</span>
<input id="q" placeholder="Buscar por nome do negocio... ou cole um CNPJ (com ou sem pontos) para abrir a ficha direto"></div>
<div id="corpo"><div id="esq">
 <div id="filtros">
  <select id="uf"><option value="">Estado: todos</option></select>
  <select id="cidade" disabled><option value="">Cidade: todas</option></select>
  <input id="cnae" placeholder="Atividade (CNAE): digite p.ex. padaria" autocomplete="off">
  <button id="btnmf">mais filtros ▸</button>
 </div>
 <div id="mf" class="oculto">
  <label><input type="checkbox" id="ftel"> só com telefone</label>
  <label><input type="checkbox" id="fmail"> só com e-mail</label>
  <select id="porte"><option value="">Porte: todos</option><option value="01">Microempresa</option><option value="03">Pequeno porte</option><option value="05">Demais</option></select>
  <input id="capmin" type="number" min="0" placeholder="Capital social mínimo (R$)" style="max-width:200px">
  <button id="limpar">limpar filtros</button>
 </div>
 <div id="barrainat"><label><input type="checkbox" id="inat"> mostrar também as inativas (baixadas, inaptas, suspensas, nulas)</label></div>
 <div id="reshead"><span id="total"></span></div>
 <div id="lista"><div class="carregando">carregando…</div></div>
 <div id="rodape"><div id="paginacao"></div><div id="paginfo" class="dim oculto"></div><span id="fimlista" class="oculto dim">— fim da lista —</span></div>
</div>
<div id="dir"><div id="card"><div class="placeholder">Clique em uma empresa na lista para abrir a ficha completa.<br><br>Dica: cole um CNPJ na busca de cima para abrir a ficha direto.</div></div></div>
</div>
<div id="sug"></div>
<script>
const $=i=>document.getElementById(i);
let CN=[],cnaeCod="",cnaeSelTxt="",pag=1,TOTAL=null,PAGES=0,busy=false;
const esc=s=>(s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const norm=s=>(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const digits=t=>(t||"").replace(/\D/g,"");
async function jget(u){const r=await fetch(u);const j=await r.json();if(!r.ok)throw new Error(j.erro||("HTTP "+r.status));return j;}
function qsBase(){const p=new URLSearchParams();const q=$("q").value.trim();
 if(q&&digits(q).length!==14)p.set("q",q);
 if($("uf").value)p.set("uf",$("uf").value);
 if($("cidade").value)p.set("cidade",$("cidade").value);
 if(cnaeCod)p.set("cnae",cnaeCod);
 if($("ftel").checked)p.set("tel","1");
 if($("fmail").checked)p.set("mail","1");
 if($("porte").value)p.set("porte",$("porte").value);
 if($("capmin").value)p.set("capmin",$("capmin").value);
 if($("inat").checked)p.set("inat","1");
 return p.toString();}
async function carregar(){if(busy)return;busy=true;
 try{const off=(pag-1)*100;
  const j=await jget("/api/empresas?"+qsBase()+"&off="+off);
  $("lista").innerHTML=j.linhas.map(itemHTML).join("");
  $("fimlista").classList.toggle("oculto",j.linhas.length===100);
 }catch(e){$("lista").innerHTML='<div class="erro">Erro: '+esc(e.message)+'</div>';}
 busy=false;}
async function contar(){$("total").textContent="contando…";
 try{const j=await jget("/api/total?"+qsBase());
  TOTAL=j.n;PAGES=Math.max(1,Math.ceil(TOTAL/100));
  $("total").textContent=TOTAL.toLocaleString("pt-BR")+" empresas encontradas";
  renderPag();
 }catch(e){TOTAL=null;PAGES=0;$("total").textContent="";}}
function renderPag(){const el=$("paginacao");
 if(!PAGES||PAGES<=1){el.innerHTML="";$("paginfo").classList.add("oculto");return;}
 let nums=[];const add=n=>{if(!nums.includes(n)&&n>=1&&n<=PAGES)nums.push(n);};
 add(1);add(PAGES);for(let n=pag-2;n<=pag+2;n++)add(n);
 nums.sort((a,b)=>a-b);
 let html="",prev=0;
 for(const n of nums){if(prev&&n-prev>1)html+='<span class="pts">…</span>';
  html+='<button class="pg'+(n===pag?' cur':'')+'" data-p="'+n+'">'+n.toLocaleString("pt-BR")+'</button>';prev=n;}
 el.innerHTML=html;
 const pi=$("paginfo");pi.textContent="página "+pag.toLocaleString("pt-BR")+" de "+PAGES.toLocaleString("pt-BR");pi.classList.remove("oculto");}
async function recarregar(){pag=1;TOTAL=null;PAGES=0;$("fimlista").classList.add("oculto");
 $("total").textContent="";$("paginacao").innerHTML="";$("paginfo").classList.add("oculto");
 $("lista").innerHTML='<div class="carregando">carregando…</div>';
 await carregar();contar();}
function itemHTML(r){const stA=r.st==="Ativa";
 return '<div class="item" data-d="'+r.d+'">'
 +'<div class="l1"><span class="nome">'+esc(r.rs)+'</span>'
 +'<span class="b '+(stA?"bA":"bI")+'">'+esc(r.st)+'</span>'
 +'<span class="b '+(r.mf==="MATRIZ"?"bM":"bF")+'">'+esc(r.mf)+'</span></div>'
 +(r.nf?'<div class="l2">'+esc(r.nf)+' · <span class="dim">'+esc(r.cnae)+'</span></div>':'<div class="l2 dim">'+esc(r.cnae)+'</div>')
 +'<div class="l3">'+esc([r.cid&&r.uf?(r.cid+" - "+r.uf):(r.uf||""),r.tel,r.em].filter(Boolean).join("  ·  "))+'</div>'
 +'<div class="l4">'+esc(r.dfmt)+'</div></div>';}
async function abrir(d){document.querySelectorAll(".item").forEach(x=>x.classList.toggle("sel",x.dataset.d===d));
 $("card").innerHTML='<div class="carregando">abrindo ficha…</div>';
 try{const j=await jget("/api/empresa?d="+encodeURIComponent(d));$("card").innerHTML=cardHTML(j);$("dir").scrollTop=0;}
 catch(e){$("card").innerHTML='<div class="erro">Erro: '+esc(e.message)+'</div>';}}
function kv(k,v){return (v&&String(v).length)?'<div class="kv"><span>'+k+'</span><b>'+esc(v)+'</b></div>':"";}
function kvr(k,h){return h?'<div class="kv"><span>'+k+'</span><b>'+h+'</b></div>':"";}
function sec(t,h){return h?'<div class="sec"><h3>'+t+'</h3>'+h+'</div>':"";}
function cardHTML(j){if(j.erro)return '<div class="erro">'+esc(j.erro)+'</div>';
 const stA=j.situacao==="Ativa";
 let h='<div class="chead"><div class="cnpjbox">'+esc(j.cnpj)
 +'<span class="b '+(stA?"bA":"bI")+'">'+esc(j.situacao||"—")+'</span>'
 +'<span class="b '+(j.tipo==="MATRIZ"?"bM":"bF")+'">'+esc(j.tipo||"")+'</span></div>'
 +'<h2>'+esc(j.razao||"(sem razao social)")+'</h2>'
 +(j.fantasia?'<div class="fant">Nome de fantasia: <b>'+esc(j.fantasia)+'</b></div>':"")+'</div>';
 h+=sec("Contato",kvr("Telefone 1",j.tel1?'<a href="tel:'+esc(j.tel1.replace(/\s+/g,""))+'">'+esc(j.tel1)+'</a>':"")
 +kvr("Telefone 2",j.tel2?'<a href="tel:'+esc(j.tel2.replace(/\s+/g,""))+'">'+esc(j.tel2)+'</a>':"")
 +kv("Fax",j.fax)
 +kvr("E-mail",j.email?'<a href="mailto:'+esc(j.email)+'">'+esc(j.email)+'</a>':""));
 const end=[];
 if(j.logr)end.push(esc(j.logr)+(j.numero?", "+esc(j.numero):"")+(j.compl?" - "+esc(j.compl):""));
 if(j.bairro)end.push(esc(j.bairro));
 if(j.ext){end.push(esc(j.ext)+(j.pais?" - "+esc(j.pais):""));}
 else if(j.cidade||j.uf){end.push(esc([j.cidade,j.uf].filter(Boolean).join(" - ")));}
 if(j.cep)end.push(esc(j.cep));
 h+=sec("Endereço",end.length?end.map(x=>'<div class="linha">'+x+'</div>').join(""):'<div class="dim">sem endereco informado</div>');
 h+=sec("Atividade",kvr("CNAE principal",(j.cnae_p&&(j.cnae_p.c||j.cnae_p.n))?(esc(j.cnae_p.c)+(j.cnae_p.n?" - "+esc(j.cnae_p.n):"")):"")
 +(j.cnae_s&&j.cnae_s.length?kvr("Secundários",j.cnae_s.map(x=>esc(x.n||x.c)).join(" · ")):""));
 h+=sec("Enquadramento",kv("Natureza jurídica",j.nj)+kv("Qualificação do responsável",j.qualif)
 +kv("Porte",j.porte)+kv("Capital social",j.capital)+kv("Ente federativo",j.ente));
 h+=sec("Situação",kv("Data da situação",j.data_situacao)+kv("Motivo",j.motivo)+kv("Início da atividade",j.abertura)
 +(j.sit_esp?kv("Situação especial",j.sit_esp+(j.data_esp?" em "+j.data_esp:"")):""));
 let sp="";
 if(j.simples){const f1=j.simples.simples?(j.simples.simples+(j.simples.d_s?" desde "+j.simples.d_s:"")+(j.simples.x_s?" (saiu em "+j.simples.x_s+")":"")):"";
 const f2=j.simples.mei?(j.simples.mei+(j.simples.d_m?" desde "+j.simples.d_m:"")+(j.simples.x_m?" (saiu em "+j.simples.x_m+")":"")):"";
 sp=kv("Simples Nacional",f1)+kv("MEI",f2);}
 else sp='<div class="dim">sem registro na tabela Simples/MEI</div>';
 h+=sec("Simples / MEI",sp);
 return h;}
 $("lista").addEventListener("click",e=>{const it=e.target.closest(".item");if(it)abrir(it.dataset.d);});
 $("paginacao").addEventListener("click",e=>{const b=e.target.closest("button.pg");if(!b||busy)return;
 pag=parseInt(b.dataset.p,10);renderPag();
 $("lista").innerHTML='<div class="carregando">carregando…</div>';
 $("lista").scrollTop=0;$("fimlista").classList.add("oculto");
 carregar();});
 $("uf").addEventListener("change",async()=>{const uf=$("uf").value;const sel=$("cidade");
 let html='<option value="">Cidade: todas</option>';
 if(uf){try{const j=await jget("/api/cidades?uf="+encodeURIComponent(uf));
  html+=j.cidades.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join("");}catch(e){}}
 sel.innerHTML=html;sel.disabled=!uf;recarregar();});
 $("cidade").addEventListener("change",recarregar);
const sug=document.getElementById("sug");
 $("cnae").addEventListener("input",()=>{const v=$("cnae").value;
 if(cnaeCod&&v!==cnaeSelTxt){cnaeCod="";recarregar();}
 if(!v){sug.style.display="none";return;}
 const m=CN.filter(c=>norm(c.n).indexOf(norm(v))>=0).slice(0,8);
 if(!m.length){sug.style.display="none";return;}
 sug.innerHTML=m.map(c=>'<div data-c="'+c.c+'"><b>'+c.c+'</b> '+esc(c.n)+'</div>').join("");
 const r=$("cnae").getBoundingClientRect();
 sug.style.left=r.left+"px";sug.style.top=r.bottom+"px";sug.style.width=r.width+"px";sug.style.display="block";});
sug.addEventListener("mousedown",e=>{const d=e.target.closest("[data-c]");if(!d)return;
 const c=CN.find(x=>x.c===d.dataset.c);cnaeCod=c.c;cnaeSelTxt=c.c+" - "+c.n;$("cnae").value=cnaeSelTxt;
 sug.style.display="none";recarregar();});
 $("cnae").addEventListener("blur",()=>setTimeout(()=>sug.style.display="none",150));
 $("btnmf").onclick=()=>{$("mf").classList.toggle("oculto");
 $("btnmf").textContent=$("mf").classList.contains("oculto")?"mais filtros ▸":"menos filtros ▴";};
["ftel","fmail","porte","capmin","inat"].forEach(id=>$(id).addEventListener("change",recarregar));
 $("limpar").onclick=()=>{$("q").value="";$("uf").value="";
 const s=$("cidade");s.innerHTML='<option value="">Cidade: todas</option>';s.disabled=true;
 $("cnae").value="";cnaeCod="";cnaeSelTxt="";$("ftel").checked=false;$("fmail").checked=false;
 $("porte").value="";$("capmin").value="";$("inat").checked=false;recarregar();};
let deb=null;
 $("q").addEventListener("input",()=>{clearTimeout(deb);deb=setTimeout(()=>{
 const d=digits($("q").value);
 if(d.length===14&&digits($("q").value.trim()).length===14){abrir(d);}
 else recarregar();},350);});
(async function boot(){try{
 const ju=await jget("/api/ufs");
 $("uf").innerHTML='<option value="">Estado: todos</option>'+ju.ufs.map(u=>'<option value="'+esc(u)+'">'+esc(u)+'</option>').join("");
 const jc=await jget("/api/cnaes");CN=jc.cnaes;
 recarregar();
}catch(e){$("total").textContent="Erro ao iniciar: "+e.message;}})();
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
    def do_GET(self):
        try:
            u = urlparse(self.path); p = u.path; qs = parse_qs(u.query)
            if p in ("/", "/index.html"):
                self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif p == "/api/ufs": self._json({"ufs": UF_LISTA})
            elif p == "/api/cidades": self._json({"cidades": UF_CIDADES.get(((qs.get("uf") or [""])[0]).upper()[:2], [])})
            elif p == "/api/cnaes": self._json({"cnaes": CNAE_LISTA})
            elif p == "/api/empresas": self._json(api_empresas(qs))
            elif p == "/api/total": self._json(api_total(qs))
            elif p == "/api/empresa": self._json(api_empresa((qs.get("d") or [""])[0]))
            else: self._json({"erro":"rota desconhecida"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as ex:
            try: self._json({"erro": type(ex).__name__ + ": " + str(ex)}, 500)
            except Exception: pass

def porta_viva():
    for p in range(PORTA, PORTA + 20):
        s = socket.socket(); s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", p)); s.close(); return p
        except Exception:
            try: s.close()
            except Exception: pass
    return None

def achar_servidor():
    p = PORTA
    while p < PORTA + 20:
        try: return ThreadingHTTPServer(("127.0.0.1", p), H), p
        except OSError: p += 1
    log("Sem porta livre entre %d e %d" % (PORTA, PORTA + 19)); sys.exit(1)

if __name__ == "__main__":
    if not os.path.exists(DB):
        log("ERRO: cnpj.db nao encontrado em: " + DB); sys.exit(1)
    viva = porta_viva()
    if viva:
        log("Ja existe um app rodando na porta %d - abrindo o navegador nele." % viva)
        webbrowser.open("http://localhost:%d" % viva)
        sys.exit(0)
    checar()
    log("Carregando listas em memoria...")
    carregar_memoria()
    srv, porta = achar_servidor()
    url = "http://localhost:%d" % porta
    try:
        with open(PIDFILE, "w") as f: f.write(str(os.getpid()))
    except Exception: pass
    log("=" * 50)
    log(" App CNPJ rodando (local, sem internet) - v3")
    log(" Endereco no navegador: " + url)
    log(" Banco: " + DB)
    log(" Encerrar: Ctrl+C (aqui) ou encerrar.bat (modo oculto)")
    log("=" * 50)
    threading.Thread(target=total_contado, args=(["v.situacao='02'"], [], ""), daemon=True).start()
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("\nEncerrado.")
    finally:
        try: os.remove(PIDFILE)
        except Exception: pass
