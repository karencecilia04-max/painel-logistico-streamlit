import streamlit as st

from core.auth import exigir_login
from core.data import fonte
from core.ui import ICONE, estilo

st.set_page_config(page_title="Painel Logístico",
                   page_icon=str(ICONE) if ICONE.exists() else ":material/directions_boat:", layout="wide")
estilo()
exigir_login()

paginas = {
    "Acompanhamento": [
        st.Page("paginas/navios.py", title="Atracação de navios", icon=":material/anchor:", default=True),
        st.Page("paginas/booking.py", title="Aguardando booking", icon=":material/schedule:"),
    ],
    "Indicadores": [
        st.Page("paginas/indicadores.py", title="Dashboard de agentes", icon=":material/bar_chart:"),
        st.Page("paginas/frete.py", title="Consulta de frete", icon=":material/request_quote:"),
    ],
    "Ferramentas": [
        st.Page("paginas/calculadora.py", title="Calculadora logística", icon=":material/calculate:"),
    ],
}
nav = st.navigation(paginas)

with st.sidebar:
    st.divider()
    if st.button("Atualizar dados", icon=":material/refresh:", width="stretch", help="Os dados são relidos da planilha a cada 10 min."):
        st.cache_data.clear()
        st.rerun()
    if fonte() == "demo":
        st.caption("Demonstração com dados fictícios. As datas acompanham o dia de hoje.")
    elif fonte() == "local":
        st.caption("Fonte: arquivos locais em data/, sem login.")

nav.run()
