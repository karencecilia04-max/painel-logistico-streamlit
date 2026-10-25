"""Painel de atracação: navios esperados/atracados em Navegantes, Itapoá e Itajaí."""
import html

import pandas as pd
import streamlit as st

from core.data import PORTOS, followup, opcoes
from core.relatorio import Relatorio, botao_pdf
from core.ui import data_br

st.title("Atracação de navios")
st.caption(
    "Previsão baseada na **Data de Chegada (col. N)** do follow-up. "
    "Status *Atracado* = data de chegada já atingida; *Esperado* = chegada futura."
)

df = followup()
hoje = pd.Timestamp.today().normalize()
inicio_semana = hoje - pd.Timedelta(days=hoje.weekday())

# --- filtros
c1, c2 = st.columns([1, 1.6])
periodo = c1.segmented_control("Período", ["Hoje", "Semana", "Próx. 14 dias"], default="Semana") or "Semana"
portos_sel = c2.pills("Porto", list(PORTOS), selection_mode="multi", default=list(PORTOS),
                      format_func=lambda p: PORTOS[p].split(" (")[0]) or list(PORTOS)
c3, c4 = st.columns([1, 1.6])
equipes = c3.multiselect("Equipe", opcoes(df["equipe"]), placeholder="Todas")
busca = c4.text_input("Buscar container / ref / cliente", placeholder="ex.: TSTU1234567").strip().upper()

if periodo == "Hoje":
    ini, fim = hoje, hoje
elif periodo == "Próx. 14 dias":
    ini, fim = hoje - pd.Timedelta(days=2), hoje + pd.Timedelta(days=14)
else:
    ini, fim = inicio_semana, inicio_semana + pd.Timedelta(days=6)

base = df[df["base"].eq("Ativo") & df["destino_chave"].isin(portos_sel) & ~df["cancelado"] & df["dt_chegada"].notna()]
if equipes:
    base = base[base["equipe"].isin(equipes)]

if busca:
    # busca ignora o período: acha a carga onde estiver
    alvo = base[
        base["containers"].map(lambda cs: any(busca in c for c in cs))
        | base["ref"].str.upper().str.contains(busca, regex=False, na=False)
        | base["cliente"].str.upper().str.contains(busca, regex=False, na=False)
    ]
else:
    alvo = base[base["dt_chegada"].between(ini, fim)]

alvo = alvo.assign(situacao=lambda d: d["dt_chegada"].le(hoje).map({True: "Atracado", False: "Esperado"}))

# --- KPIs
navios = alvo.groupby(["navio_nome", "destino_chave"], dropna=False)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Navios no período", navios.ngroups)
k_atr = alvo.loc[alvo["situacao"] == "Atracado"].groupby(["navio_nome", "destino_chave"], dropna=False).ngroups
k2.metric("Atracados", k_atr)
k3.metric("Processos", len(alvo))
k4.metric("Containers", int(alvo["qtd_containers"].fillna(0).sum()))
st.write("")

if alvo.empty:
    st.markdown('<div class="vazio">Nenhuma chegada prevista para o filtro selecionado.</div>', unsafe_allow_html=True)
    st.stop()


def cartao(navio: str, grupo: pd.DataFrame) -> str:
    atracado = (grupo["situacao"] == "Atracado").all()
    classe, chip = ("atracado", '<span class="chip chip-ok">ATRACADO</span>') if atracado \
        else ("esperado", '<span class="chip chip-esp">ESPERADO</span>')
    etas = grupo["dt_chegada"].dropna().unique()
    eta = data_br(min(etas)) + (f" a {data_br(max(etas))}" if len(etas) > 1 else "")
    misto = grupo["situacao"].nunique() > 1  # só mostra status por linha se houver mistura
    linhas = "".join(
        f"<tr><td><b>{html.escape(r.ref)}</b></td><td>{html.escape(r.cliente or '-')}</td>"
        f"<td class='mono'>{'<br>'.join(r.containers) or ('LCL' if r.lcl else '-')}</td>"
        f"<td>{html.escape((r.equipe or '-').replace('Equipe ', ''))}</td>"
        + (f"<td>{r.situacao}</td>" if misto else "") + "</tr>"
        for r in grupo.sort_values("ref").itertuples()
    )
    cab = "<th>Ref.</th><th>Cliente</th><th>Container</th><th>Equipe</th>" + ("<th></th>" if misto else "")
    qtd = int(grupo["qtd_containers"].fillna(0).sum())
    return (
        f'<div class="navio {classe}"><h4>{html.escape(navio)} {chip}</h4>'
        f'<div class="meta">Chegada: <b>{eta}</b> · {len(grupo)} processo(s) · {qtd} container(s)</div>'
        f"<table><tr>{cab}</tr>{linhas}</table></div>"
    )


colunas = st.columns(len(portos_sel) or 1)
for col, porto in zip(colunas, portos_sel):
    with col:
        sub = alvo[alvo["destino_chave"] == porto]
        st.subheader(PORTOS[porto])
        if sub.empty:
            st.markdown('<div class="vazio">Sem chegadas</div>', unsafe_allow_html=True)
            continue
        ordem = sub.assign(nav=sub["navio_nome"].fillna("Navio não informado")) \
            .groupby("nav").agg(eta=("dt_chegada", "min")).sort_values("eta").index
        for nav in ordem:
            grupo = sub[sub["navio_nome"].fillna("Navio não informado") == nav]
            st.markdown(cartao(nav, grupo), unsafe_allow_html=True)

with st.expander("Ver como tabela / exportar"):
    tabela = alvo[["ref", "cliente", "containers", "equipe", "navio", "destino", "dt_chegada", "situacao"]].copy()
    tabela["containers"] = tabela["containers"].map(", ".join)
    st.dataframe(
        tabela.sort_values("dt_chegada"), hide_index=True, width="stretch",
        column_config={
            "ref": "Ref.", "cliente": "Cliente", "containers": "Containers", "equipe": "Equipe",
            "navio": "Navio", "destino": "Porto", "situacao": "Situação",
            "dt_chegada": st.column_config.DateColumn("Chegada", format="DD/MM/YYYY"),
        },
    )

# --- relatório PDF
filtros_txt = {
    "Período": f"{periodo} ({ini:%d/%m} a {fim:%d/%m/%Y})" if not busca else f"busca: {busca}",
    "Portos": ", ".join(PORTOS[p].split(" (")[0] for p in portos_sel),
    "Equipes": ", ".join(equipes) or "Todas",
}


def montar() -> Relatorio:
    r = Relatorio("Atracação de navios", filtros_txt)
    r.kpis([("Navios no período", str(navios.ngroups)), ("Atracados", str(int(k_atr))),
            ("Processos", str(len(alvo))), ("Containers", str(int(alvo["qtd_containers"].fillna(0).sum())))])
    for porto in portos_sel:
        sub = alvo[alvo["destino_chave"] == porto]
        r.secao(PORTOS[porto])
        sub = sub.assign(navio_nome=sub["navio_nome"].fillna("Navio não informado")).sort_values(["dt_chegada", "navio_nome", "ref"])
        r.tabela(sub, {"navio_nome": "Navio", "dt_chegada": "Chegada", "situacao": "Situação", "ref": "Ref.",
                       "cliente": "Cliente", "containers": "Containers", "equipe": "Equipe"},
                 destaque=lambda l: (227, 241, 234) if l["situacao"] == "Atracado" else None)
    return r


st.divider()
botao_pdf(montar, "atracacao_navios", "navios", assinatura=repr(filtros_txt))
