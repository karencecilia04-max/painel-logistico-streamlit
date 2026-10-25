"""Filtro de período compartilhado: por anos (com meses) ou por intervalo de datas."""
import pandas as pd
import streamlit as st

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def filtro_periodo(datas: pd.Series, chave: str, todos_os_anos: bool = False) -> tuple[pd.Series, str]:
    """Desenha o filtro e devolve (máscara booleana sobre `datas`, descrição legível do período).
    todos_os_anos=True começa com todos os anos marcados (útil para histórico)."""
    validas = datas.dropna()
    if validas.empty:
        return pd.Series(False, index=datas.index), "sem dados"
    anos = sorted(validas.dt.year.unique().tolist(), reverse=True)

    c1, c2, c3 = st.columns([1.1, 1.6, 2])
    modo = c1.segmented_control("Período por", ["Anos", "Datas"], default="Anos", key=f"{chave}_modo") or "Anos"

    if modo == "Anos":
        hoje = pd.Timestamp.today().year
        padrao = anos if todos_os_anos else ([hoje] if hoje in anos else anos[:1])
        anos_sel = c2.multiselect("Anos", anos, default=padrao,
                                  key=f"{chave}_anos", placeholder="Todos os anos")
        meses = c3.select_slider("Meses", options=list(range(1, 13)), value=(1, 12),
                                 format_func=lambda m: MESES[m - 1], key=f"{chave}_meses")
        anos_ef = anos_sel or anos
        mascara = datas.dt.year.isin(anos_ef) & datas.dt.month.between(*meses)
        desc = ", ".join(str(a) for a in sorted(anos_ef))
        if meses != (1, 12):
            desc += f" ({MESES[meses[0] - 1]} a {MESES[meses[1] - 1]})"
        return mascara.fillna(False), desc

    ini_pad, fim_pad = validas.min().date(), validas.max().date()
    intervalo = c2.date_input("De / até", value=(ini_pad, fim_pad), min_value=ini_pad, max_value=fim_pad,
                              format="DD/MM/YYYY", key=f"{chave}_datas")
    c3.write("")
    if not isinstance(intervalo, (list, tuple)) or len(intervalo) < 2:
        st.info("Escolha a data final do período.")
        st.stop()
    ini, fim = pd.Timestamp(intervalo[0]), pd.Timestamp(intervalo[1])
    return datas.between(ini, fim).fillna(False), f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"
