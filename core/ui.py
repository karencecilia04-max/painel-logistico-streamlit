"""Identidade visual e helpers de formatação compartilhados pelas páginas."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TINTA = "#14213D"           # texto e títulos
AZUL = "#2A78D6"            # série principal dos gráficos
DESTAQUE = "#EB6834"        # detalhes da interface e ano mais recente
FUNDO_SUAVE = "#F3F5F8"
DESTAQUE_CLARO = "#FDEEE6"
CINZA = "#5F6673"
BORDA = "#E1E5EB"

# Cores de status, separadas das cores de série
VERDE = "#2E7D5B"
VERDE_CLARO = "#E3F1EA"
AMBAR = "#D98E04"
VERMELHO = "#B8443A"

SEQ = [AZUL, DESTAQUE, "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#6250D6", "#E34948"]

# Coloque logo.png e icone.png em assets/ para usar uma marca própria
ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo.png"
ICONE = ASSETS / "icone.png"

pio.templates["painel"] = go.layout.Template(
    layout=dict(
        font=dict(family="Montserrat, Segoe UI, sans-serif", size=13, color=TINTA),
        colorway=SEQ,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=44, b=8),
        xaxis=dict(showgrid=False, linecolor=BORDA),
        yaxis=dict(gridcolor="#ECEFF3", zeroline=False),
        hoverlabel=dict(bgcolor="white", font_color=TINTA),
        title=dict(font=dict(size=15, color=TINTA), x=0, xanchor="left"),
    )
)
pio.templates.default = "plotly_white+painel"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&display=swap');
.block-container {{padding-top: 2rem; max-width: 1400px;}}
h1, h2, h3, h4, h5, h6 {{font-family: 'Montserrat', sans-serif !important; color: {TINTA}; letter-spacing: -.01em;}}
h1 {{font-weight: 800 !important;}}
h1::after {{content: ""; display: block; width: 56px; height: 5px; background: {DESTAQUE}; border-radius: 3px; margin-top: 8px;}}
section[data-testid="stSidebar"] {{border-right: 1px solid {BORDA};}}
img[data-testid="stSidebarLogo"], img[data-testid="stLogo"] {{height: 3.4rem !important; width: auto; max-width: 210px;}}
div[data-testid="stSidebarHeader"] {{padding-top: 1.2rem; padding-bottom: 1.2rem; height: auto;}}
h3 {{font-size: 1.15rem !important; font-weight: 700 !important;}}
div[data-testid="stMetric"] {{
  background: #FFFFFF; border: 1px solid {BORDA}; border-left: 5px solid {DESTAQUE};
  border-radius: 12px; padding: 12px 14px; min-width: 0;
}}
/* sem prefixo de tag: em versões novas do Streamlit o rótulo é <label>, não <div> */
[data-testid="stMetricLabel"] p {{color: {CINZA}; font-size: .85rem;}}
[data-testid="stMetricValue"] {{color: {TINTA}; font-family: 'Montserrat', sans-serif; font-weight: 700;
  font-size: clamp(0.95rem, 1.5vw, 1.9rem) !important; line-height: 1.25;}}
/* o Streamlit corta rótulo e valor com "..." quando o card é estreito: mostra inteiro */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  overflow: visible !important; text-overflow: clip !important; line-height: 1.25;}}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{white-space: normal !important;}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{white-space: nowrap !important;}}
button[data-baseweb="tab"][aria-selected="true"] p {{font-weight: 700;}}
div[data-baseweb="tab-highlight"] {{background-color: {DESTAQUE} !important; height: 3px;}}
.chip {{display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:700; letter-spacing:.02em;}}
.chip-ok {{background:{VERDE_CLARO}; color:{VERDE};}}
.chip-esp {{background:{DESTAQUE_CLARO}; color:#9A3F12;}}
.navio {{border:1px solid {BORDA}; border-radius:12px; padding:14px 16px; margin-bottom:12px; background:#fff; overflow-x:auto;}}
.navio.atracado {{border-left:6px solid {VERDE}; background:{VERDE_CLARO};}}
.navio.esperado {{border-left:6px solid {DESTAQUE};}}
.navio h4 {{margin:0 0 4px 0; font-size:1.02rem;}}
.navio .meta {{color:{CINZA}; font-size:.85rem; margin-bottom:8px;}}
.navio table {{width:100%; font-size:.82rem; border-collapse:collapse;}}
.navio td.mono {{font-family: ui-monospace, Consolas, monospace; font-size:.78rem; white-space:nowrap;}}
.navio th {{text-align:left; color:{CINZA}; font-weight:600; border-bottom:1px solid {BORDA}; padding:4px 6px;}}
.navio td {{padding:4px 6px; border-bottom:1px solid #EEF1F4; vertical-align:top;}}
.vazio {{color:{CINZA}; padding:24px; text-align:center; border:1px dashed #C9CFD8; border-radius:12px;}}
</style>
"""


def estilo() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO.exists():
        st.logo(str(LOGO), size="large", icon_image=str(ICONE) if ICONE.exists() else None)


def brl(v) -> str:
    if v is None or pd.isna(v):
        return "-"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def usd(v) -> str:
    if v is None or pd.isna(v):
        return "-"
    return "US$ " + f"{v:,.0f}".replace(",", ".")


def num(v, casas=1) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def data_br(v) -> str:
    return "-" if v is None or pd.isna(v) else pd.Timestamp(v).strftime("%d/%m/%Y")
