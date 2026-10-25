"""Prévia de despesas logísticas usando as tabelas da planilha de tarifas."""
import pandas as pd
import streamlit as st

from core import calc
from core.data import tarifas
from core.relatorio import Relatorio, botao_pdf
from core.ui import brl

st.title("Calculadora logística")
st.caption("Prévia de despesas com base nas tabelas da planilha de tarifas. Para alterar valores, edite as abas da planilha.")

t = tarifas()
ETAPAS = ["Armazenagem no porto", "Serviços do parceiro", "Frete rodoviário"]

etapas = st.pills("Etapas da prévia", ETAPAS, selection_mode="multi", default=ETAPAS,
                  help="Escolha só o que entra no cálculo, ex.: armazenagem + serviços, sem frete.")
if not etapas:
    st.info("Selecione ao menos uma etapa para montar a prévia.")
    st.stop()
etapas = [e for e in ETAPAS if e in etapas]  # mantém a ordem

g1, g2 = st.columns(2)
qtd = g1.number_input("Quantidade de containers", min_value=1, value=1, step=1)
cif = g2.number_input("Valor CIF total (R$)", min_value=0.0, value=0.0, step=1000.0, format="%.2f",
                      help="Usado na armazenagem portuária (percentual sobre o CIF) e no ad valorem.")

totais: dict[str, float] = {}
detalhes: dict[str, dict] = {}  # para o PDF: {etapa: {"params": {...}, "linhas": [...], "extras": [...]}}


def tabela(linhas: list[dict]) -> None:
    df = pd.DataFrame(linhas)
    for c in ("nota", "alerta"):
        if c not in df:
            df[c] = None
    df["obs"] = df["alerta"].fillna(df["nota"]).fillna("")
    st.dataframe(df[["item", "valor", "obs"]], hide_index=True, width="stretch",
                 column_config={"item": "Item", "obs": "Observação",
                                "valor": st.column_config.NumberColumn("Valor por container (R$)", format="%.2f")})
    for l in linhas:
        if l.get("alerta"):
            st.warning(f"{l['item']}: {l['alerta']}")


abas = dict(zip(etapas, st.tabs([f"{i} · {e}" for i, e in enumerate(etapas, 1)])))
portos1 = list(dict.fromkeys(t["Armazenagem_Periodos"]["Porto"]))

if "Armazenagem no porto" in abas:
    with abas["Armazenagem no porto"]:
        a, b, c = st.columns(3)
        porto1 = a.selectbox("Porto / terminal", portos1, key="p1")
        dias1 = b.number_input("Dias de armazenagem", min_value=0, value=5, key="d1")
        adv = c.number_input("Ad valorem (%)", min_value=0.0, value=0.0, step=0.05, format="%.2f")
        ex = t["Armazenagem_Extras"]
        conds = ex[(ex["Porto"] == porto1) & (ex["Tipo"] == "condicional")]
        nomes_cond = dict(zip(conds["Chave"], conds["Descricao"]))
        marcados = st.pills("Adicionais condicionais", conds["Chave"].tolist(), selection_mode="multi",
                            format_func=nomes_cond.get) or []
        r1 = calc.etapa1(t, porto1, qtd, cif, dias1, marcados, adv)
        tabela(r1["linhas"])
        if r1["ad_valorem"]:
            st.write(f"Ad valorem: **{brl(r1['ad_valorem'])}**")
        if r1["critico"]:
            st.error("Prazo ultrapassa os períodos tarifados deste terminal. Consulte o terminal.")
        st.metric("Subtotal armazenagem", brl(r1["subtotal"]))
        totais["Armazenagem no porto"] = r1["subtotal"]
        detalhes["Armazenagem no porto"] = {
            "params": {"Porto": porto1, "Dias": dias1, "Ad valorem": f"{adv:.2f}%",
                       "Adicionais": ", ".join(nomes_cond[m] for m in marcados) or "nenhum"},
            "linhas": r1["linhas"], "extras": [("Ad valorem", r1["ad_valorem"])] if r1["ad_valorem"] else []}

if "Serviços do parceiro" in abas:
    with abas["Serviços do parceiro"]:
        empresas = list(dict.fromkeys(t["Parceiros_Retirada"]["Empresa"]))
        a, b, c, d = st.columns(4)
        emp = a.selectbox("Parceiro", empresas)
        locais = t["Parceiros_Retirada"].loc[t["Parceiros_Retirada"]["Empresa"] == emp, "Porto"].tolist() or portos1
        local = b.selectbox("Porto de retirada", locais)
        ops = t["Parceiros_Operacoes"][t["Parceiros_Operacoes"]["Empresa"] == emp]
        nomes_op = dict(zip(ops["Operacao_Chave"], ops["Operacao_Label"]))
        op = c.selectbox("Operação", ops["Operacao_Chave"].tolist(), format_func=nomes_op.get)
        dias2 = d.number_input("Dias no parceiro", min_value=0, value=0, key="d2")
        if op:
            r2 = calc.etapa2(t, emp, local, op, qtd, dias2)
            tabela(r2["linhas"])
            st.write(f"Imposto ({r2['imposto_pct']:.0f}%): **{brl(r2['imposto'])}**")
            st.metric("Subtotal serviços", brl(r2["subtotal"]))
            totais["Serviços do parceiro"] = r2["subtotal"]
            detalhes["Serviços do parceiro"] = {
                "params": {"Parceiro": emp, "Porto": local, "Operação": nomes_op.get(op, op), "Dias": dias2},
                "linhas": r2["linhas"], "extras": [(f"Imposto ({r2['imposto_pct']:.0f}%)", r2["imposto"])]}

if "Frete rodoviário" in abas:
    with abas["Frete rodoviário"]:
        portos3 = list(dict.fromkeys(t["Frete_Rodoviario"]["Porto"]))
        a, b, c = st.columns([1, 2, 1])
        porto3 = a.selectbox("Porto de origem", portos3, key="p3")
        dest = b.selectbox("Destino (cidade / UF)", calc.destinos(t, porto3))
        tipo = c.segmented_control("Veículo", ["container", "carreta"], default="container",
                                   format_func=str.capitalize) or "container"
        opcoes_tr = calc.transportadoras(t, porto3, dest, tipo)
        if not opcoes_tr:
            st.info("Nenhuma transportadora com tarifa para esta rota e veículo.")
        else:
            st.markdown("###### Tarifas disponíveis nesta rota (mais barata primeiro)")
            st.dataframe(pd.DataFrame(opcoes_tr)[["label", "valor"]], hide_index=True,
                         column_config={"label": "Transportadora",
                                        "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")})
            a, b = st.columns(2)
            nomes_tr = {o["chave"]: o["label"] for o in opcoes_tr}
            tr = a.selectbox("Transportadora", list(nomes_tr), format_func=nomes_tr.get)
            margem = b.number_input("Margem de segurança (%)", min_value=0.0, value=calc.margem_padrao(t), step=0.5)
            r3 = calc.etapa3(t, porto3, dest, tipo, tr, qtd, margem)
            if "erro" in r3:
                st.error(r3["erro"])
            else:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Distância", f"{r3['km']:.0f} km" if r3["km"] else "-")
                m2.metric("Valor base", brl(r3["valor_base"]))
                m3.metric("Com margem", brl(r3["valor_com_margem"]))
                m4.metric(f"Total ({r3['qtd']}x)", brl(r3["total"]))
                if r3["abaixo_minimo"]:
                    st.warning(f"Valor abaixo do frete mínimo de referência ({brl(r3['fm_ref'])}).")
                totais["Frete rodoviário"] = r3["total"]
                detalhes["Frete rodoviário"] = {
                    "params": {"Porto": porto3, "Destino": dest, "Veículo": tipo, "Transportadora": nomes_tr[tr],
                               "Distância": f"{r3['km']:.0f} km" if r3["km"] else "-", "Margem": f"{margem:.1f}%"},
                    "linhas": [{"item": "Valor base", "valor": r3["valor_base"]},
                               {"item": f"Margem de segurança ({margem:.1f}%)", "valor": r3["margem"]}],
                    "extras": []}

st.divider()
st.subheader("Resumo da prévia")
if totais:
    cols = st.columns(len(totais) + 1)
    for col, (k, v) in zip(cols, totais.items()):
        col.metric(k, brl(v))
    cols[-1].metric("TOTAL ESTIMADO", brl(sum(totais.values())))
else:
    st.info("Preencha as etapas selecionadas para ver o total.")


def montar() -> Relatorio:
    r = Relatorio("Prévia de despesas logísticas",
                  {"Etapas": ", ".join(etapas), "Containers": str(qtd), "CIF total": brl(cif)})
    r.kpis([(k, brl(v)) for k, v in totais.items()] + [("TOTAL ESTIMADO", brl(sum(totais.values())))])
    for etapa, d in detalhes.items():
        r.secao(etapa)
        r.texto("   |   ".join(f"{k}: {v}" for k, v in d["params"].items()))
        linhas = pd.DataFrame(d["linhas"]).reindex(columns=["item", "valor", "nota", "alerta"])
        linhas["obs"] = linhas["alerta"].fillna(linhas["nota"]).fillna("")
        r.tabela(linhas, {"item": "Item", "valor": "Valor por container (R$)", "obs": "Observação"}, {"valor": brl})
        for rot, v in d["extras"]:
            r.texto(f"{rot}: {brl(v)}")
        r.texto(f"Subtotal {etapa.lower()}: {brl(totais[etapa])}")
    return r


if totais:
    botao_pdf(montar, "previa_logistica", "calc",
              assinatura=repr((etapas, qtd, cif, {k: round(v, 2) for k, v in totais.items()})))
