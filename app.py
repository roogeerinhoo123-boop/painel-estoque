from __future__ import annotations
import csv, io, unicodedata
from datetime import datetime
from typing import Any
import streamlit as st
from supabase import Client, create_client

TABELA = "estoque"

st.set_page_config(page_title="Tecnor | Painel de Estoque", page_icon="📦", layout="wide")

def normalizar(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold().strip()

def segredo(nome: str) -> str:
    valor = st.secrets.get(nome, "")
    if not valor:
        st.error(f"Configuração ausente: {nome}")
        st.stop()
    return str(valor)

@st.cache_resource
def conectar() -> Client:
    return create_client(segredo("SUPABASE_URL"), segredo("SUPABASE_KEY"))

def carregar() -> list[dict]:
    r = (conectar().table(TABELA)
         .select("id,produto,prateleira,local,quantidade,cliente,data_cadastro")
         .order("produto").execute())
    return r.data or []

def csv_download(registros: list[dict]) -> bytes:
    b = io.StringIO()
    campos = ["produto","prateleira","local","quantidade","cliente"]
    w = csv.DictWriter(b, fieldnames=campos, extrasaction="ignore")
    w.writeheader(); w.writerows(registros)
    return b.getvalue().encode("utf-8-sig")

st.markdown("""
<style>
:root{--tecnor:#082a73;--fundo:#f4f7fb;--borda:#d8e2ef}
.stApp{background:var(--fundo)}
.block-container{padding-top:1.1rem;max-width:1450px}
.tecnor-header{display:flex;align-items:center;gap:24px;padding:18px 24px;border-radius:22px;
background:linear-gradient(135deg,#061d55,#0b347d 55%,#123f8f);box-shadow:0 10px 28px rgba(8,42,115,.18);margin-bottom:18px}
.tecnor-logo-box{min-width:250px;height:88px;display:flex;align-items:center;justify-content:center;background:#07266d;border-radius:6px}
.tecnor-wordmark{color:white;font-size:48px;font-weight:700;letter-spacing:-3px;font-family:Arial,Helvetica,sans-serif}
.tecnor-title{color:white;font-size:2rem;font-weight:800;line-height:1.08}
.tecnor-subtitle{color:rgba(255,255,255,.86);font-size:1rem;margin-top:8px}
[data-testid="stMetric"]{background:white;border:1px solid var(--borda);padding:14px 16px;border-radius:16px;box-shadow:0 4px 16px rgba(3,26,77,.06)}
[data-testid="stMetric"] *{color:#082a73 !important}
[data-testid="stMetricLabel"]{color:#5c6f91 !important}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:#082a73 !important;font-weight:800 !important}
div[data-baseweb="tab-list"]{gap:8px;background:white;border:1px solid var(--borda);border-radius:14px;padding:6px}
button[data-baseweb="tab"]{border-radius:10px;padding-left:18px;padding-right:18px}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{border-radius:11px;min-height:42px;font-weight:700}
@media(max-width:800px){.tecnor-header{flex-direction:column;align-items:flex-start}.tecnor-logo-box{min-width:100%;width:100%}}
</style>
""", unsafe_allow_html=True)

def cabecalho():
    st.markdown("""
    <div class="tecnor-header">
      <div class="tecnor-logo-box"><div class="tecnor-wordmark">tecnor</div></div>
      <div>
        <div class="tecnor-title">Painel Interativo de Estoque</div>
        <div class="tecnor-subtitle">Produtos, localização, clientes e quantidades em uma base online compartilhada</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def autenticar():
    if st.session_state.get("autenticado"): return
    cabecalho()
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar no painel", type="primary", use_container_width=True):
        if senha == segredo("SENHA_PAINEL"):
            st.session_state.autenticado = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()

autenticar()
cabecalho()

if st.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

try:
    registros = carregar()
except Exception as erro:
    st.error(f"Não foi possível consultar o banco de dados: {erro}")
    st.stop()

aba_busca, aba_novo, aba_gerenciar = st.tabs(["🔎 Buscar produtos","➕ Novo cadastro","✏️ Gerenciar"])

with aba_busca:
    st.subheader("Consulta de produtos")
    st.caption("Pesquise por produto, cliente, local ou prateleira.")
    termo = st.text_input("Pesquisar", placeholder="Digite o produto, cliente, local ou prateleira")

    clientes = sorted({str(r.get("cliente") or "").strip() for r in registros if r.get("cliente")})
    locais = sorted({str(r.get("local") or r.get("prateleira") or "").strip()
                     for r in registros if r.get("local") or r.get("prateleira")})

    f1,f2,f3 = st.columns([1.1,1.1,1.1])
    with f1: cliente_sel = st.selectbox("Cliente", ["Todos"] + clientes)
    with f2: local_sel = st.selectbox("Local", ["Todos"] + locais)
    with f3: somente_estoque = st.toggle("Somente com estoque", value=False)

    filtrados=[]
    t=normalizar(termo)
    for r in registros:
        produto=str(r.get("produto") or "")
        prateleira=str(r.get("prateleira") or "")
        local=str(r.get("local") or "")
        cliente=str(r.get("cliente") or "")
        qtd=int(r.get("quantidade") or 0)
        if t and t not in normalizar(" ".join([produto,prateleira,local,cliente])): continue
        if cliente_sel!="Todos" and cliente!=cliente_sel: continue
        if local_sel!="Todos" and local_sel not in {local,prateleira}: continue
        if somente_estoque and qtd<=0: continue
        filtrados.append(r)

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Produtos encontrados", len(filtrados))
    m2.metric("Quantidade total", sum(int(r.get("quantidade") or 0) for r in filtrados))
    m3.metric("Locais", len({str(r.get("local") or r.get("prateleira") or "").strip() for r in filtrados if r.get("local") or r.get("prateleira")}))
    m4.metric("Clientes", len({str(r.get("cliente") or "").strip() for r in filtrados if r.get("cliente")}))

    tabela=[]
    for r in filtrados:
        pr=str(r.get("prateleira") or "").strip()
        lo=str(r.get("local") or "").strip()
        localizacao=f"{pr} — {lo}" if pr and lo and normalizar(pr)!=normalizar(lo) else (pr or lo)
        tabela.append({"PRODUTO":r.get("produto",""),"LOCALIZAÇÃO":localizacao,"CLIENTE":r.get("cliente",""),"QUANTIDADE":int(r.get("quantidade") or 0)})
    st.dataframe(tabela, use_container_width=True, hide_index=True, height=420)
    st.download_button("Baixar resultado em CSV", data=csv_download(filtrados),
                       file_name=f"estoque_tecnor_{datetime.now():%Y%m%d_%H%M}.csv", mime="text/csv")

with aba_novo:
    st.subheader("Novo cadastro")
    with st.form("form_novo", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            produto=st.text_input("Produto *")
            prateleira=st.text_input("Prateleira")
            cliente=st.text_input("Cliente")
        with c2:
            local=st.text_input("Local")
            quantidade=st.number_input("Quantidade", min_value=0, step=1, value=0)
        salvar=st.form_submit_button("Salvar cadastro", type="primary", use_container_width=True)
    if salvar:
        if not produto.strip():
            st.warning("Informe o produto.")
        else:
            try:
                conectar().table(TABELA).insert({
                    "produto":produto.strip().upper(),
                    "prateleira":prateleira.strip().upper(),
                    "local":local.strip().upper(),
                    "quantidade":int(quantidade),
                    "cliente":cliente.strip().upper(),
                    "data_cadastro":datetime.now().isoformat(),
                }).execute()
                st.success("Cadastro realizado com sucesso.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível cadastrar: {erro}")

with aba_gerenciar:
    st.subheader("Gerenciar cadastros")
    if not registros:
        st.info("Nenhum cadastro disponível.")
    else:
        opcoes={f"{r.get('produto','')} | {r.get('prateleira') or r.get('local') or ''} | {r.get('cliente','')}":r for r in registros}
        escolha=st.selectbox("Selecione um cadastro", list(opcoes.keys()))
        atual=opcoes[escolha]

        with st.form("form_editar"):
            a,b=st.columns(2)
            with a:
                e_produto=st.text_input("Produto", value=str(atual.get("produto") or ""))
                e_prateleira=st.text_input("Prateleira", value=str(atual.get("prateleira") or ""))
                e_cliente=st.text_input("Cliente", value=str(atual.get("cliente") or ""))
            with b:
                e_local=st.text_input("Local", value=str(atual.get("local") or ""))
                e_quantidade=st.number_input("Quantidade", min_value=0, step=1, value=int(atual.get("quantidade") or 0))
            alterar=st.form_submit_button("Salvar alterações", type="primary", use_container_width=True)

        if alterar:
            try:
                conectar().table(TABELA).update({
                    "produto":e_produto.strip().upper(),
                    "prateleira":e_prateleira.strip().upper(),
                    "local":e_local.strip().upper(),
                    "quantidade":int(e_quantidade),
                    "cliente":e_cliente.strip().upper(),
                }).eq("id", atual["id"]).execute()
                st.success("Cadastro atualizado.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível atualizar: {erro}")

        st.divider()
        confirmar=st.checkbox("Confirmo a exclusão deste cadastro")
        if st.button("🗑️ Excluir cadastro", disabled=not confirmar):
            try:
                conectar().table(TABELA).delete().eq("id", atual["id"]).execute()
                st.success("Cadastro excluído.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível excluir: {erro}")
