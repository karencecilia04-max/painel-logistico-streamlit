"""Gráficos descritos uma vez (Grafico) e desenhados na tela (Plotly) e no PDF (matplotlib).

Quando o filtro tem mais de um ano, os gráficos agrupam por ano com uma cor por ano.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.ui import AZUL, DESTAQUE, FUNDO_SUAVE, SEQ

TOP_PDF = 15  # máximo de categorias por gráfico no PDF
CORES_ANO = [DESTAQUE, AZUL, "#1BAF7A", "#EDA100", "#6250D6"]


def cores_por_ano(anos) -> dict[str, str]:
    """Ano mais recente na cor de destaque, os anteriores nas cores seguintes da paleta."""
    return {str(a): CORES_ANO[i % len(CORES_ANO)] for i, a in enumerate(sorted({str(a) for a in anos}, reverse=True))}


@dataclass
class Grafico:
    tipo: str            # "barras" (horizontal), "linhas" ou "mapa" (calor)
    dados: pd.DataFrame
    x: str               # barras: valor; linhas: eixo x; mapa: colunas
    y: str               # barras: categoria; linhas: valor; mapa: linhas
    titulo: str
    cor: str | None = None   # coluna de agrupamento (ex.: "ano")
    fmt: str = ",.0f"
    valor: str | None = None  # só para mapa
    extras: dict = field(default_factory=dict)

    @property
    def grupos(self) -> list[str]:
        if not self.cor or self.cor not in self.dados:
            return []
        return sorted(self.dados[self.cor].astype(str).unique().tolist())


def agrega(df: pd.DataFrame, cat: str, valor: str, func: str, por_ano: bool, nome: str | None = None) -> pd.DataFrame:
    """Agrupa por categoria (e ano, se for comparativo)."""
    chaves = [cat, "ano"] if por_ano else [cat]
    if func == "count":
        out = df.groupby(chaves).size().reset_index(name=nome or valor)
    else:
        out = df.dropna(subset=[valor]).groupby(chaves)[valor].agg(func).reset_index()
        if nome:
            out = out.rename(columns={valor: nome})
    if por_ano:
        out["ano"] = out["ano"].astype(str)
    return out


# ----------------------------------------------------------------- tela (Plotly)
def plotly(g: Grafico) -> go.Figure:
    d = g.dados
    if g.tipo == "barras":
        ordem = d.groupby(g.y)[g.x].sum().sort_values().index.tolist()
        if g.grupos and len(g.grupos) > 1:
            fig = px.bar(d, x=g.x, y=g.y, color=g.cor, barmode="group", orientation="h", text=g.x,
                         color_discrete_map=cores_por_ano(g.grupos), category_orders={g.y: ordem[::-1], g.cor: g.grupos[::-1]})
            fig.update_traces(texttemplate=f"%{{text:{g.fmt}}}", textposition="outside", cliponaxis=False)
            altura = max(300, 22 * len(ordem) * len(g.grupos) + 110)
            fig.update_layout(legend=dict(title=None, orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        else:
            fig = go.Figure(go.Bar(x=d[g.x], y=d[g.y], orientation="h", marker_color=AZUL, text=d[g.x],
                                   texttemplate=f"%{{text:{g.fmt}}}", textposition="outside", cliponaxis=False,
                                   hovertemplate=f"%{{y}}: %{{x:{g.fmt}}}<extra></extra>"))
            fig.update_yaxes(categoryorder="array", categoryarray=ordem)
            altura = max(260, 30 * len(ordem) + 90)
        # margem à direita para o rótulo de valor da barra mais longa não ser cortado
        fig.update_layout(title=g.titulo, height=altura, xaxis=dict(visible=False), yaxis_title=None, separators=",.",
                          margin=dict(r=56))
        return fig

    if g.tipo == "linhas":
        mapa_cor = cores_por_ano(g.grupos) if g.cor == "ano" else None
        fig = px.line(d, x=g.x, y=g.y, color=g.cor, markers=True, title=g.titulo,
                      color_discrete_map=mapa_cor, color_discrete_sequence=SEQ,
                      category_orders={g.x: g.extras.get("ordem_x")} if g.extras.get("ordem_x") else None)
        fig.update_layout(xaxis_title=None, yaxis_title=None, separators=",.",
                          legend=dict(title=None, orientation="h", y=-0.15))
        if g.extras.get("mensal"):
            fig.update_xaxes(dtick="M1", tickformat="%b/%y")
        return fig

    # mapa de calor
    piv = d.pivot_table(index=g.y, columns=g.x, values=g.valor, aggfunc="mean").round(0)
    fig = px.imshow(piv, text_auto=g.fmt.replace(",", "") if "." in g.fmt else ",.0f", aspect="auto",
                    color_continuous_scale=[FUNDO_SUAVE, g.extras.get("cor", AZUL)])
    fig.update_layout(title=g.titulo, height=max(320, 30 * len(piv) + 130), coloraxis_showscale=False,
                      xaxis_title=None, yaxis_title=None, separators=",.")
    return fig


# ----------------------------------------------------------------- PDF (matplotlib)
def png(g: Grafico, largura_pol: float = 10.5) -> bytes | None:
    """Imagem PNG do gráfico para o relatório. Mapas de calor viram tabela no PDF (retorna None)."""
    if g.tipo == "mapa" or g.dados.empty:
        return None
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = g.dados
    titulo = g.titulo
    plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans"})
    if g.tipo == "barras":
        ordem = d.groupby(g.y)[g.x].sum().sort_values().index.tolist()
        if len(ordem) > TOP_PDF:  # no papel, só os maiores
            ordem = ordem[-TOP_PDF:]
            titulo += f" (top {TOP_PDF})"
        grupos = g.grupos if len(g.grupos) > 1 else [None]
        n = len(ordem)
        fig, ax = plt.subplots(figsize=(largura_pol, min(4.6, max(1.6, 0.17 * n * len(grupos) + 0.9))))
        alt = 0.8 / len(grupos)
        cores = cores_por_ano(g.grupos)
        for gi, grp in enumerate(grupos):
            sub = d if grp is None else d[d[g.cor].astype(str) == grp]
            vals = sub.groupby(g.y)[g.x].sum().reindex(ordem)
            pos = [i - 0.4 + alt * (gi + 0.5) for i in range(n)]
            barras = ax.barh(pos, vals.fillna(0), height=alt * 0.92, color=cores.get(grp, AZUL), label=grp)
            for b, v in zip(barras, vals):
                if pd.notna(v):
                    ax.text(b.get_width(), b.get_y() + b.get_height() / 2, " " + _fmt(v, g.fmt), va="center", fontsize=7)
        ax.set_yticks(range(n), ordem)
        ax.xaxis.set_visible(False)
        if grupos[0] is not None:
            ax.legend(frameon=False, fontsize=7, loc="lower right")
    else:  # linhas
        fig, ax = plt.subplots(figsize=(largura_pol, 3.4))
        series = d.groupby(g.cor) if g.cor else [(None, d)]
        cores = cores_por_ano(g.grupos) if g.cor == "ano" else {}
        ordem_x = g.extras.get("ordem_x")
        for i, (nome, sub) in enumerate(series):
            sub = sub.set_index(g.x)[g.y]
            if ordem_x:
                sub = sub.reindex(ordem_x)
            else:
                sub = sub.sort_index()
            ax.plot([str(x)[:7] if not ordem_x else x for x in sub.index], sub.values, marker="o", markersize=3,
                    color=cores.get(str(nome), SEQ[i % len(SEQ)]), label=nome)
        if g.cor:
            ax.legend(frameon=False, fontsize=7, ncol=6)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(axis="y", color="#EEF0F2")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_title(titulo, loc="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    return buf.getvalue()


def _fmt(v, fmt: str) -> str:
    casas = 1 if ".1f" in fmt else 0
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
