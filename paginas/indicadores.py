"""Indicadores de desempenho dos agentes de cargas, com comparativo entre anos."""
import pandas as pd
import streamlit as st

from core import graficos
from core.data import followup, opcoes
from core.filtros import MESES, filtro_periodo
from core.graficos import Grafico, agrega
from core.relatorio import Relatorio, botao_pdf
from core.ui import SEQ, num, usd

st.title("Dashboard de agentes de cargas")
st.caption(
    "Base: follow-up **ativo + processos encerrados**, com **Data de Embarque** preenchida (cancelados excluídos). "
    "Frete internacional (col. AD) considerado **por container**, valores zerados ignorados. "
    "Com mais de um ano selecionado, os gráficos comparam os anos lado a lado."
)

df = followup()

# --- qualidade dos dados
ruins, corr = df[df["problemas"] != ""], df[df["correcoes"] != ""]
if len(ruins) or len(corr):
    with st.expander(f"Qualidade dos dados: {len(ruins)} para corrigir na planilha, {len(corr)} corrigido(s) automaticamente",
                     icon=":material/warning:"):
        if len(ruins):
            st.markdown("**Precisam de correção na planilha** (ficam fora dos cálculos de prazo):")
            st.dataframe(ruins[["ref", "base", "equipe", "problemas"]], hide_index=True, width="stretch",
                         column_config={"ref": "Ref.", "base": "Planilha", "equipe": "Equipe", "problemas": "Campo e valor encontrado"})
        if len(corr):
            st.markdown("**Corrigidos automaticamente** (confira se a interpretação está certa):")
            st.dataframe(corr[["ref", "base", "correcoes"]], hide_index=True, width="stretch",
                         column_config={"ref": "Ref.", "base": "Planilha", "correcoes": "Valor original e como foi lido"})
        st.caption("Instrução de Embarque com 'CFR'/'CIF' não é erro: o frete é do exportador e não há instrução.")

emb = df[df["dt_embarque"].notna() & ~df["cancelado"] & df["agente"].notna()].copy()

# --- filtros
mascara, desc_periodo = filtro_periodo(emb["dt_embarque"], "ind")
emb = emb[mascara]
c1, c2, c3 = st.columns([2, 2, 1.1])
agentes = c1.multiselect("Agente de cargas", opcoes(emb["agente"]), placeholder="Todos")
portos = c2.multiselect("Porto de destino", opcoes(emb["porto"]), placeholder="Todos")
granularidade = c3.segmented_control("Evolução", ["Mensal", "Anual"], default="Mensal") or "Mensal"
if agentes:
    emb = emb[emb["agente"].isin(agentes)]
if portos:
    emb = emb[emb["porto"].isin(portos)]

if emb.empty:
    st.markdown('<div class="vazio">Sem embarques para o filtro selecionado.</div>', unsafe_allow_html=True)
    st.stop()

emb["ano"] = emb["dt_embarque"].dt.year
anos = sorted(emb["ano"].unique())
cmp = len(anos) > 1  # comparativo entre anos
fcl = emb[~emb["lcl"]]
com_frete = emb[emb["frete"].fillna(0) > 0]


def resumo(d: pd.DataFrame) -> dict:
    f = d[d["frete"].fillna(0) > 0]
    return {
        "Embarques": len(d),
        "Containers": int(d.loc[~d["lcl"], "qtd_containers"].fillna(0).sum()),
        "Frete médio / container": f["frete"].mean(),
        "Confirmação média (dias)": d["dias_confirmacao"].mean(),
        "Transit time médio (dias)": d["transit_dias"].mean(),
    }


tot = resumo(emb)
kpis = [("Embarques", f"{tot['Embarques']:,}".replace(",", ".")),
        ("Containers", f"{tot['Containers']:,}".replace(",", ".")),
        ("Frete médio / container", usd(tot["Frete médio / container"])),
        ("Confirmação média", f"{num(tot['Confirmação média (dias)'], 0)} dias"),
        ("Transit time médio", f"{num(tot['Transit time médio (dias)'], 0)} dias")]
cols = st.columns(5)
ajuda = {"Confirmação média": "Dias entre a Instrução de Embarque (AE) e a Data de Embarque (M).",
         "Transit time médio": "Dias entre embarque (M) e chegada (N); usa a col. O quando as datas faltam."}
for col, (k, v) in zip(cols, kpis):
    col.metric(k, v, help=ajuda.get(k))

por_ano = None
if cmp:
    por_ano = pd.DataFrame({a: resumo(emb[emb["ano"] == a]) for a in anos}).T
    por_ano.index.name = "Ano"
    st.markdown("##### Comparativo por ano")
    st.dataframe(
        por_ano.reset_index(), hide_index=True, width="stretch",
        column_config={"Ano": st.column_config.NumberColumn(format="%d"),
                       "Frete médio / container": st.column_config.NumberColumn(format="US$ %.0f"),
                       "Confirmação média (dias)": st.column_config.NumberColumn(format="%.1f"),
                       "Transit time médio (dias)": st.column_config.NumberColumn(format="%.1f")},
    )

# --- gráficos (descritos uma vez: tela + PDF)
cor = "ano" if cmp else None
sufixo = ", comparativo por ano" if cmp else ""
G = {
    "vol_cont": Grafico("barras", agrega(fcl, "agente", "qtd_containers", "sum", cmp), "qtd_containers", "agente",
                        "Containers embarcados por agente" + sufixo, cor),
    "vol_emb": Grafico("barras", agrega(emb, "agente", "ref", "count", cmp, "embarques"), "embarques", "agente",
                       "Nº de embarques por agente" + sufixo, cor),
    "fr_ag": Grafico("barras", agrega(com_frete, "agente", "frete", "mean", cmp), "frete", "agente",
                     "Frete médio por agente (US$/container)" + sufixo, cor),
    "fr_or": Grafico("barras", agrega(com_frete, "origem", "frete", "mean", cmp), "frete", "origem",
                     "Frete médio por origem (US$/container)" + sufixo, cor),
    "fr_mapa": Grafico("mapa", com_frete, "origem", "agente", "Frete médio: agente × origem (US$/container)", valor="frete"),
    "pz_conf": Grafico("barras", agrega(emb, "agente", "dias_confirmacao", "mean", cmp), "dias_confirmacao", "agente",
                       "Tempo médio de confirmação de embarque (dias)" + sufixo, cor, ",.1f"),
    "pz_tt_ag": Grafico("barras", agrega(emb, "agente", "transit_dias", "mean", cmp), "transit_dias", "agente",
                        "Transit time médio por agente (dias)" + sufixo, cor, ",.1f"),
    "pz_tt_or": Grafico("barras", agrega(emb, "origem", "transit_dias", "mean", cmp), "transit_dias", "origem",
                        "Transit time médio por origem (dias)" + sufixo, cor, ",.1f"),
    "pz_mapa": Grafico("mapa", emb.dropna(subset=["transit_dias"]), "agente", "origem",
                       "Transit time médio: origem × agente (dias)", valor="transit_dias", extras={"cor": "#EB6834"}),
    "po_cont": Grafico("barras", agrega(fcl.dropna(subset=["porto"]), "porto", "qtd_containers", "sum", cmp),
                       "qtd_containers", "porto", "Containers por porto de destino" + sufixo, cor),
    "po_proc": Grafico("barras", agrega(emb.dropna(subset=["porto"]), "porto", "ref", "count", cmp, "processos"),
                       "processos", "porto", "Processos por porto de destino" + sufixo, cor),
}

# evolução
if granularidade == "Anual":
    G["ev_cont"] = Grafico("barras", agrega(fcl, "ano", "qtd_containers", "sum", False).astype({"ano": str}),
                           "qtd_containers", "ano", "Containers embarcados por ano")
    G["ev_frete"] = Grafico("barras", agrega(com_frete, "ano", "frete", "mean", False).astype({"ano": str}),
                            "frete", "ano", "Frete médio por ano (US$/container)")
elif cmp:  # meses no eixo x, uma linha por ano
    def por_mes(d, valor, func):
        out = d.assign(mes=d["dt_embarque"].dt.month).groupby(["ano", "mes"])[valor].agg(func).reset_index()
        return out.assign(ano=out["ano"].astype(str), mes=out["mes"].map(lambda m: MESES[m - 1]))
    G["ev_cont"] = Grafico("linhas", por_mes(fcl, "qtd_containers", "sum"), "mes", "qtd_containers",
                           "Containers embarcados por mês, comparativo por ano", "ano", extras={"ordem_x": MESES})
    G["ev_frete"] = Grafico("linhas", por_mes(com_frete, "frete", "mean"), "mes", "frete",
                            "Frete médio por mês (US$/container), comparativo por ano", "ano", extras={"ordem_x": MESES})
else:
    def mensal(d, valor, func):
        return d.assign(mes=d["dt_embarque"].dt.to_period("M").dt.to_timestamp()).groupby("mes")[valor].agg(func).reset_index()
    G["ev_cont"] = Grafico("linhas", mensal(fcl, "qtd_containers", "sum"), "mes", "qtd_containers",
                           "Containers embarcados por mês", extras={"mensal": True})
    G["ev_frete"] = Grafico("linhas", mensal(com_frete, "frete", "mean"), "mes", "frete",
                            "Frete médio por mês (US$/container)", extras={"mensal": True})

# tabela de portos
tab_portos = fcl.dropna(subset=["porto"]).groupby("porto").agg(
    processos=("ref", "count"), containers=("qtd_containers", "sum")).sort_values("containers", ascending=False).reset_index()
tab_portos["participacao"] = tab_portos["containers"] / tab_portos["containers"].sum() * 100


def mostra(*chaves):
    colunas = st.columns(len(chaves))
    for c, k in zip(colunas, chaves):
        c.plotly_chart(graficos.plotly(G[k]), width="stretch", key=f"g_{k}")


abas = st.tabs(["Volume", "Frete", "Prazos", "Portos", "Evolução"])
with abas[0]:
    mostra("vol_cont", "vol_emb")
with abas[1]:
    mostra("fr_ag", "fr_or")
    st.plotly_chart(graficos.plotly(G["fr_mapa"]), width="stretch")
with abas[2]:
    mostra("pz_conf", "pz_tt_ag")
    mostra("pz_tt_or", "pz_mapa")
with abas[3]:
    if not tab_portos.empty:
        lider = tab_portos.iloc[0]
        a, b, c = st.columns(3)
        a.metric("Porto com mais containers", lider["porto"], f"{int(lider['containers'])} containers", delta_color="off")
        mais_proc = tab_portos.sort_values("processos", ascending=False).iloc[0]
        b.metric("Porto com mais processos", mais_proc["porto"], f"{int(mais_proc['processos'])} processos", delta_color="off")
        c.metric("Participação do líder", f"{lider['participacao']:.0f}%".replace(".", ","))
    mostra("po_cont", "po_proc")
    st.dataframe(tab_portos, hide_index=True, width="stretch",
                 column_config={"porto": "Porto", "processos": "Processos",
                                "containers": st.column_config.NumberColumn("Containers", format="%d"),
                                "participacao": st.column_config.ProgressColumn("Participação (containers)", format="%.0f%%",
                                                                                min_value=0, max_value=100)})
with abas[4]:
    mostra("ev_cont")
    mostra("ev_frete")


# --- relatório PDF
filtros_txt = {"Período": desc_periodo, "Agentes": ", ".join(agentes) or "Todos", "Portos": ", ".join(portos) or "Todos"}


def montar() -> Relatorio:
    r = Relatorio("Dashboard de agentes de cargas", filtros_txt)
    r.kpis(kpis)
    if por_ano is not None:
        r.secao("Comparativo por ano")
        r.tabela(por_ano.reset_index(), formatos={
            "Ano": lambda v: str(int(v)), "Frete médio / container": usd,
            "Confirmação média (dias)": lambda v: num(v, 1), "Transit time médio (dias)": lambda v: num(v, 1)})
    for titulo, chaves in [("Volume", ["vol_cont", "vol_emb"]), ("Frete", ["fr_ag", "fr_or", "fr_mapa"]),
                           ("Prazos", ["pz_conf", "pz_tt_ag", "pz_tt_or", "pz_mapa"]),
                           ("Portos", ["po_cont", "po_proc"]), ("Evolução", ["ev_cont", "ev_frete"])]:
        r.add_page()
        r.secao(titulo)
        for k in chaves:
            r.grafico(G[k])
        if titulo == "Portos":
            r.tabela(tab_portos, {"porto": "Porto", "processos": "Processos", "containers": "Containers",
                                  "participacao": "Participação %"}, {"participacao": lambda v: f"{v:.1f}%"})
    return r


st.divider()
botao_pdf(montar, "dashboard_agentes", "ind", assinatura=repr(filtros_txt) + granularidade)
