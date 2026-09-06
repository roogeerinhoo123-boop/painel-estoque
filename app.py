from __future__ import annotations

import csv
import hashlib
import hmac
import io
import unicodedata

import streamlit as st
from supabase import Client, create_client

TABELA = "estoque"


def normalizar(valor: object) -> str:
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


def autenticar() -> None:
    if st.session_state.get("autenticado"):
        return
    st.title("🔐 Painel de Estoque")
    with st.form("login"):
        senha = st.text_input("Senha de acesso", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        esperado = segredo("SENHA_PAINEL")
        if hmac.compare_digest(
            hashlib.sha256(senha.encode()).digest(),
            hashlib.sha256(esperado.encode()).digest(),
        ):
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


def carregar() -> list[dict]:
    resposta = conectar().table(TABELA).select("id,produto,prateleira,local,quantidade,cliente,data_cadastro").order("produto").execute()
    return resposta.data or []


def csv_download(registros: list[dict]) -> bytes:
    buffer = io.StringIO()
    campos = ["produto", "prateleira", "local", "quantidade", "cliente"]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(registros)
    return buffer.getvalue().encode("utf-8-sig")


st.set_page_config(page_title="Painel de Estoque", page_icon="📦", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.3rem;max-width:1450px}
h1,h2,h3{color:#1d4f91}
[data-testid="stMetric"]{background:#f6f9ff;border:1px solid #c9d9f3;padding:14px;border-radius:14px}
.stButton>button{border-radius:10px}
</style>
""", unsafe_allow_html=True)

autenticar()
topo1, topo2 = st.columns([8, 1])
topo1.title("📦 Painel Interativo de Estoque")
topo1.caption("Produtos, localização, clientes e quantidades em uma base online compartilhada")
if topo2.button("Sair"):
    st.session_state.clear()
    st.rerun()

try:
    dados = carregar()
except Exception as erro:
    st.error(f"Não foi possível consultar o banco de dados: {erro}")
    st.stop()

busca, cadastro, gerenciar = st.tabs(["🔎 Buscar produtos", "➕ Novo cadastro", "✏️ Gerenciar"])

with busca:
    termo = st.text_input("Pesquisar", placeholder="Digite o produto, cliente, local ou prateleira")
    c1, c2, c3 = st.columns(3)
    clientes = sorted({str(r.get("cliente") or "") for r in dados if r.get("cliente")})
    locais = sorted({str(r.get("local") or "") for r in dados if r.get("local")})
    cliente = c1.selectbox("Cliente", ["Todos"] + clientes)
    local = c2.selectbox("Local", ["Todos"] + locais)
    disponivel = c3.toggle("Somente com estoque", value=False)

    filtrados = dados
    if termo.strip():
        alvo = normalizar(termo)
        filtrados = [r for r in filtrados if any(alvo in normalizar(r.get(c)) for c in ("produto", "cliente", "local", "prateleira"))]
    if cliente != "Todos":
        filtrados = [r for r in filtrados if r.get("cliente") == cliente]
    if local != "Todos":
        filtrados = [r for r in filtrados if r.get("local") == local]
    if disponivel:
        filtrados = [r for r in filtrados if int(r.get("quantidade") or 0) > 0]

    exibicao = [{
        "PRODUTO": r.get("produto", ""),
        "LOCALIZAÇÃO": f"PRATELEIRA {r.get('prateleira', '')} — {r.get('local', '')}",
        "CLIENTE": r.get("cliente", ""),
        "QUANTIDADE": int(r.get("quantidade") or 0),
    } for r in filtrados]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Produtos encontrados", len(filtrados))
    m2.metric("Quantidade total", sum(int(r.get("quantidade") or 0) for r in filtrados))
    m3.metric("Locais", len({r.get("local") for r in filtrados}))
    m4.metric("Clientes", len({r.get("cliente") for r in filtrados}))
    st.dataframe(exibicao, use_container_width=True, hide_index=True, height=470)
    st.download_button("⬇️ Baixar resultado", csv_download(filtrados), "resultado_estoque.csv", "text/csv")

with cadastro:
    st.subheader("Cadastrar novo produto")
    with st.form("novo", clear_on_submit=True):
        a, b = st.columns(2)
        produto = a.text_input("Produto *", placeholder="Ex.: PC-078")
        cliente_novo = b.text_input("Nome do cliente *")
        prateleira = a.text_input("Prateleira *", placeholder="Ex.: 2")
        local_novo = b.text_input("Local *", placeholder="Ex.: B2")
        quantidade = a.number_input("Quantidade *", min_value=0, step=1)
        incluir = st.form_submit_button("💾 Salvar cadastro", type="primary", use_container_width=True)
    if incluir:
        campos = [produto, cliente_novo, prateleira, local_novo]
        if not all(v.strip() for v in campos):
            st.error("Preencha todos os campos marcados com *.")
        elif any(normalizar(r.get("produto")) == normalizar(produto) for r in dados):
            st.error("Este produto já está cadastrado.")
        else:
            try:
                conectar().table(TABELA).insert({
                    "produto": produto.strip().upper(),
                    "prateleira": prateleira.strip().upper(),
                    "local": local_novo.strip().upper(),
                    "quantidade": int(quantidade),
                    "cliente": cliente_novo.strip().upper(),
                }).execute()
                st.success("Cadastro salvo no banco de dados online.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível salvar: {erro}")

with gerenciar:
    st.subheader("Alterar ou excluir cadastro")
    if not dados:
        st.info("Não existem registros.")
    else:
        opcoes = {f"{r['produto']} — {r['cliente']} — {r['local']}": r for r in dados}
        escolhido = st.selectbox("Escolha o produto", list(opcoes))
        atual = opcoes[escolhido]
        with st.form("editar"):
            a, b = st.columns(2)
            e_produto = a.text_input("Produto", value=str(atual["produto"]))
            e_cliente = b.text_input("Cliente", value=str(atual["cliente"]))
            e_prateleira = a.text_input("Prateleira", value=str(atual["prateleira"]))
            e_local = b.text_input("Local", value=str(atual["local"]))
            e_quantidade = a.number_input("Quantidade", min_value=0, step=1, value=int(atual["quantidade"]))
            alterar = st.form_submit_button("Salvar alterações", type="primary")
        if alterar:
            try:
                conectar().table(TABELA).update({
                    "produto": e_produto.strip().upper(),
                    "prateleira": e_prateleira.strip().upper(),
                    "local": e_local.strip().upper(),
                    "quantidade": int(e_quantidade),
                    "cliente": e_cliente.strip().upper(),
                }).eq("id", atual["id"]).execute()
                st.success("Cadastro atualizado.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível atualizar: {erro}")

        st.divider()
        confirmar = st.checkbox("Confirmo a exclusão deste cadastro")
        if st.button("🗑️ Excluir cadastro", disabled=not confirmar):
            try:
                conectar().table(TABELA).delete().eq("id", atual["id"]).execute()
                st.success("Cadastro excluído.")
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível excluir: {erro}")

