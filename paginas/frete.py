"""Consulta de frete médio praticado por um agente, por origem, no período escolhido."""
import pandas as pd
import streamlit as st

from core import graficos
from core.data import followup, opcoes
from core.filtros import MESES, filtro_periodo
from core.graficos import Grafico
from core.relatorio import Relatorio, botao_pdf
from core.ui import usd

st.title("Consulta de frete por agente")
st.caption("Frete internacional (col. AD) por container, pela data de embarque. Inclui o histórico de "
           "processos encerrados. Valores zerados ignorados.")

df = followup()
base = df[df["dt_embarque"].notna() & (df["frete"].fillna(0) > 0) & ~df["cancelado"] & df["agente"].notna()].copy()

c1, c2, c3 = st.columns([2, 2, 1.2])
lista = opcoes(base["agente"])
agente = c1.selectbox("Agente de cargas", lista, index=lista.index(base["agente"].value_counts().idxmax()))
granularidade = c3.segmented_control("Visão", ["Mensal", "Anual"], default="Mensal") or "Mensal"
mascara, desc_periodo = filtro_periodo(base["dt_embarque"], "frete", todos_os_anos=True)
base = base[mascara]

sel = base[base["agente"] == agente].copy()
origens = c2.multiselect("Origem", opcoes(sel["origem"]), placeholder="Todas")
if origens:
    sel = sel[sel["origem"].isin(origens)]

if sel.empty:
    st.markdown('<div class="vazio">Sem fretes registrados para este agente no período.</div>', unsafe_allow_html=True)
    st.stop()

sel["ano"] = sel["dt_embarque"].dt.year.astype(str)
sel["periodo"] = sel["dt_embarque"].dt.strftime("%Y") if granularidade == "Anual" \
    else sel["dt_embarque"].dt.to_period("M").dt.to_timestamp()
mercado = base.groupby("origem")["frete"].mean()

kpis = [("Embarques com frete", str(len(sel))), ("Frete médio", usd(sel["frete"].mean())),
        ("Menor frete", usd(sel["frete"].min())), ("Maior frete", usd(sel["frete"].max()))]
for col, (k, v) in zip(st.columns(4), kpis):
    col.metric(k, v)

resumo = sel.groupby("origem").agg(
    embarques=("ref", "count"), frete_medio=("frete", "mean"), minimo=("frete", "min"),
    maximo=("frete", "max"), ultimo_embarque=("dt_embarque", "max"),
).reset_index()
resumo["media_todos_agentes"] = resumo["origem"].map(mercado)
resumo["dif_pct"] = (resumo["frete_medio"] / resumo["media_todos_agentes"] - 1) * 100
resumo = resumo.sort_values("embarques", ascending=False)

st.markdown("##### Resumo por origem")
st.dataframe(
    resumo, hide_index=True, width="stretch",
    column_config={
        "origem": "Origem", "embarques": "Embarques",
        "frete_medio": st.column_config.NumberColumn("Frete médio (US$)", format="%.0f"),
        "minimo": st.column_config.NumberColumn("Mín.", format="%.0f"),
        "maximo": st.column_config.NumberColumn("Máx.", format="%.0f"),
        "ultimo_embarque": st.column_config.DateColumn("Último embarque", format="DD/MM/YYYY"),
        "media_todos_agentes": st.column_config.NumberColumn("Média de todos os agentes", format="%.0f"),
        "dif_pct": st.column_config.NumberColumn("vs. média", format="%+.0f%%",
                                                 help="Negativo = este agente está mais barato que a média do período."),
    },
)

# frete médio por origem em cada período (tabela) e gráfico
piv = sel.pivot_table(index="origem", columns="periodo", values="frete", aggfunc="mean").round(0)
piv.columns = [c if isinstance(c, str) else f"{MESES[c.month - 1]}/{c:%y}" for c in piv.columns]

anos = sorted(sel["ano"].unique())
if granularidade == "Anual":
    g = Grafico("barras", sel.groupby(["origem", "ano"])["frete"].mean().reset_index(), "frete", "origem",
                f"Frete médio por origem e ano, {agente} (US$/container)", "ano" if len(anos) > 1 else None)
else:
    mensal = sel.groupby(["periodo", "origem"])["frete"].mean().reset_index()
    g = Grafico("linhas", mensal, "periodo", "frete", f"Frete médio mensal, {agente} (US$/container)", "origem",
                extras={"mensal": True})
st.plotly_chart(graficos.plotly(g), width="stretch")

st.markdown(f"##### Frete médio por origem, {'ano a ano' if granularidade == 'Anual' else 'mês a mês'} (US$/container)")
st.dataframe(piv.reset_index().rename(columns={"origem": "Origem"}), hide_index=True, width="stretch")

with st.expander("Embarques considerados"):
    st.dataframe(
        sel.sort_values("dt_embarque", ascending=False)[["ref", "cliente", "origem", "destino", "dt_embarque", "qtd_containers", "frete"]],
        hide_index=True, width="stretch",
        column_config={"dt_embarque": st.column_config.DateColumn("Embarque", format="DD/MM/YYYY"),
                       "frete": st.column_config.NumberColumn("Frete (US$)", format="%.0f")},
    )

filtros_txt = {"Agente": agente, "Período": desc_periodo, "Visão": granularidade, "Origens": ", ".join(origens) or "Todas"}


def montar() -> Relatorio:
    r = Relatorio(f"Consulta de frete - {agente}", filtros_txt)
    r.kpis(kpis)
    r.secao("Resumo por origem")
    r.tabela(resumo, {"origem": "Origem", "embarques": "Embarques", "frete_medio": "Frete médio (US$)", "minimo": "Mín.",
                      "maximo": "Máx.", "ultimo_embarque": "Último embarque", "media_todos_agentes": "Média geral",
                      "dif_pct": "vs. média"}, {"dif_pct": lambda v: "-" if pd.isna(v) else f"{v:+.0f}%"})
    r.grafico(g)
    r.secao("Frete médio por origem e período (US$/container)")
    r.tabela(piv.reset_index().rename(columns={"origem": "Origem"}))
    r.add_page()
    r.secao("Embarques considerados")
    r.tabela(sel.sort_values("dt_embarque", ascending=False),
             {"ref": "Ref.", "cliente": "Cliente", "origem": "Origem", "destino": "Destino", "dt_embarque": "Embarque",
              "qtd_containers": "Containers", "frete": "Frete (US$)"})
    return r


st.divider()
botao_pdf(montar, f"frete_{agente}", "frete", assinatura=repr(filtros_txt))
