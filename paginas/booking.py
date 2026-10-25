"""Cargas instruídas ao agente (col. AE) que ainda não têm data de embarque (col. M)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from core.data import followup, opcoes
from core.relatorio import Relatorio, botao_pdf
from core.ui import AMBAR, VERDE, VERMELHO

ALERTA, CRITICO = 7, 15  # dias desde a instrução

st.title("Aguardando booking")
st.caption(
    "Processos com **Instrução de Embarque (AE)** preenchida, **sem Data de Embarque (M)** "
    "e **Status (G) = Aguardando booking**. "
    f"Cores pelo tempo desde a instrução: até {ALERTA - 1} dias ok, de {ALERTA} a {CRITICO - 1} atenção, {CRITICO} ou mais crítico."
)

df = followup()
hoje = pd.Timestamp.today().normalize()
fila = df[
    df["dt_instrucao"].notna() & df["dt_embarque"].isna() & df["base"].eq("Ativo")
    & df["status_chave"].str.contains("AGUARDANDO BOOKING", na=False)
].copy()
fila["dias"] = (hoje - fila["dt_instrucao"]).dt.days
fila["faixa"] = pd.cut(fila["dias"], [-999, ALERTA - 1, CRITICO - 1, 99999], labels=["Ok", "Atenção", "Crítico"])

c1, c2 = st.columns(2)
agentes = c1.multiselect("Agente de cargas", opcoes(fila["agente"]), placeholder="Todos")
equipes = c2.multiselect("Equipe", opcoes(fila["equipe"]), placeholder="Todas")
if agentes:
    fila = fila[fila["agente"].isin(agentes)]
if equipes:
    fila = fila[fila["equipe"].isin(equipes)]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Aguardando booking", len(fila))
k2.metric("Em atenção", int((fila["faixa"] == "Atenção").sum()))
k3.metric("Críticos", int((fila["faixa"] == "Crítico").sum()))
k4.metric("Espera média", f"{fila['dias'].mean():.0f} dias" if len(fila) else "-")

if fila.empty:
    st.markdown('<div class="vazio">Nenhuma carga aguardando booking.</div>', unsafe_allow_html=True)
    st.stop()

esq, dir_ = st.columns([2.2, 1])
with esq:
    cores = {"Ok": "#E3F1EA", "Atenção": "#FBF0DA", "Crítico": "#F6E0DD"}
    tabela = fila.sort_values("dias", ascending=False)[
        ["ref", "cliente", "equipe", "agente", "dt_instrucao", "dias", "faixa", "status"]
    ]
    st.dataframe(
        tabela.style.apply(lambda r: [f"background-color:{cores[r['faixa']]}"] * len(r), axis=1),
        hide_index=True, width="stretch", height=min(640, 38 + 35 * len(tabela)),
        column_config={
            "ref": "Ref.", "cliente": "Cliente", "equipe": "Equipe", "agente": "Agente",
            "dt_instrucao": st.column_config.DateColumn("Instrução", format="DD/MM/YYYY"),
            "dias": st.column_config.NumberColumn("Dias", format="%d"),
            "faixa": "Situação", "status": "Status no follow-up",
        },
    )
with dir_:
    por_agente = fila.groupby(["agente", "faixa"], observed=True).size().reset_index(name="n")
    fig = px.bar(
        por_agente, x="n", y="agente", color="faixa", orientation="h", title="Por agente de cargas",
        color_discrete_map={"Ok": VERDE, "Atenção": AMBAR, "Crítico": VERMELHO},
        category_orders={"faixa": ["Crítico", "Atenção", "Ok"]},
    )
    fig.update_layout(yaxis=dict(title=None, categoryorder="total ascending"), xaxis_title=None,
                      legend=dict(title=None, orientation="h", y=-0.1), height=420)
    st.plotly_chart(fig, width="stretch")

# --- relatório PDF
filtros_txt = {"Agentes": ", ".join(agentes) or "Todos", "Equipes": ", ".join(equipes) or "Todas",
               "Critério": "AE preenchida, M vazia, status Aguardando booking"}
CORES_PDF = {"Ok": (227, 241, 234), "Atenção": (251, 240, 218), "Crítico": (246, 224, 221)}


def montar() -> Relatorio:
    r = Relatorio("Aguardando booking", filtros_txt)
    r.kpis([("Aguardando booking", str(len(fila))), ("Em atenção", str(int((fila["faixa"] == "Atenção").sum()))),
            ("Críticos", str(int((fila["faixa"] == "Crítico").sum()))),
            ("Espera média", f"{fila['dias'].mean():.0f} dias")])
    r.tabela(tabela, {"ref": "Ref.", "cliente": "Cliente", "equipe": "Equipe", "agente": "Agente",
                      "dt_instrucao": "Instrução", "dias": "Dias", "faixa": "Situação"},
             {"dias": lambda v: f"{v:.0f}"}, destaque=lambda l: CORES_PDF.get(l["faixa"]))
    return r


st.divider()
botao_pdf(montar, "aguardando_booking", "booking", assinatura=repr(filtros_txt))
