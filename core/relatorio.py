"""Relatório PDF das telas (A4 paisagem): cabeçalho com filtros, indicadores, gráficos e tabelas."""
from __future__ import annotations

import io
import re
from typing import Callable

import pandas as pd
import streamlit as st
from fpdf import FPDF

from core import graficos
from core.graficos import Grafico

from core.ui import LOGO

TINTA = (20, 33, 61)
DESTAQUE = (235, 104, 52)
CINZA = (95, 102, 115)
BORDA = (225, 229, 235)
FUNDO = (243, 245, 248)
TEXTO = TINTA
ALTURA_MAX_GRAFICO = 72  # mm: cabem 2 gráficos por página


def _t(txt) -> str:
    """Fontes padrão do PDF só aceitam latin-1: troca o que não couber (emojis, travessões)."""
    s = "" if txt is None or (isinstance(txt, float) and pd.isna(txt)) else str(txt)
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2192", "->").replace("·", "|").replace("×", "x")
    s = re.sub(r"[\u2190-\u2bff\U0001F000-\U0001FFFF\ufe0f]", "", s)
    return s.encode("latin-1", "replace").decode("latin-1").strip()


class Relatorio(FPDF):
    def __init__(self, titulo: str, filtros: dict[str, str]):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.titulo, self.filtros = titulo, filtros
        self.set_auto_page_break(True, margin=14)
        self.set_margins(12, 12, 12)
        self.add_page()

    # ------------------------------------------------------------- estrutura
    def header(self):
        larg_logo = 34
        if LOGO.exists():
            self.image(str(LOGO), x=self.w - self.r_margin - larg_logo, y=9, w=larg_logo)
        util = self.w - self.l_margin - self.r_margin - larg_logo - 6
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*TINTA)
        self.cell(util, 8, _t(f"Plataforma Logística - {self.titulo}"), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*CINZA)
        filtros = "   |   ".join(f"{k}: {v}" for k, v in self.filtros.items() if v)
        self.multi_cell(util, 4.5, _t(f"Gerado em {pd.Timestamp.now():%d/%m/%Y %H:%M}   |   {filtros}"),
                        new_x="LMARGIN", new_y="NEXT")
        y = max(self.get_y(), 24) + 1.5
        self.set_fill_color(*DESTAQUE)
        self.rect(self.l_margin, y, self.w - self.l_margin - self.r_margin, 1.2, style="F")
        self.set_y(y + 5)
        self.set_text_color(*TEXTO)

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*CINZA)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")

    _secao_pendente: str | None = None

    def _cabe(self, altura: float):
        """Garante espaço para o próximo bloco; o título de seção pendente vai junto com ele."""
        extra = 9 if self._secao_pendente else 0
        if self.get_y() + altura + extra > self.h - self.b_margin:
            self.add_page()
        if self._secao_pendente:
            self.ln(2)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*TINTA)
            self.cell(0, 7, _t(self._secao_pendente), new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*TEXTO)
            self._secao_pendente = None

    def secao(self, titulo: str):
        self._secao_pendente = titulo

    def texto(self, txt: str):
        self._cabe(6)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, _t(txt), new_x="LMARGIN", new_y="NEXT")

    # ------------------------------------------------------------- blocos
    def kpis(self, itens: list[tuple[str, str]]):
        if not itens:
            return
        self._cabe(20)
        larg = (self.w - self.l_margin - self.r_margin - 3 * (len(itens) - 1)) / len(itens)
        y = self.get_y()
        for i, (rotulo, valor) in enumerate(itens):
            x = self.l_margin + i * (larg + 3)
            self.set_fill_color(*FUNDO)
            self.set_draw_color(*BORDA)
            self.rect(x, y, larg, 16, style="DF")
            self.set_xy(x + 3, y + 2)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*CINZA)
            self.cell(larg - 6, 4, _t(rotulo))
            self.set_xy(x + 3, y + 7)
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*TEXTO)
            self.cell(larg - 6, 7, _t(valor))
        self.set_y(y + 20)

    def tabela(self, df: pd.DataFrame, colunas: dict[str, str] | None = None, formatos: dict[str, Callable] | None = None,
               destaque: Callable[[pd.Series], tuple | None] | None = None, max_linhas: int = 400):
        """colunas: {coluna: título}; formatos: {coluna: função}; destaque(linha) devolve a cor RGB de fundo ou None."""
        if df.empty:
            self.texto("Sem dados para o filtro selecionado.")
            return
        colunas = colunas or {c: str(c) for c in df.columns}
        formatos = formatos or {}
        dados = df[list(colunas)].head(max_linhas)
        textos = dados.apply(lambda col: col.map(formatos.get(col.name, _fmt_padrao)))
        util = self.w - self.l_margin - self.r_margin
        pesos = [max(len(_t(t)) for t in [colunas[c]] + textos[c].astype(str).head(60).tolist()) for c in colunas]
        pesos = [min(max(p, 5), 45) for p in pesos]
        largs = [util * p / sum(pesos) for p in pesos]

        def cabecalho():
            self.set_font("Helvetica", "B", 7.5)
            self.set_fill_color(*TINTA)
            self.set_text_color(255, 255, 255)
            for c, l in zip(colunas, largs):
                self.cell(l, 6, _t(colunas[c])[:40], border=0, fill=True)
            self.ln()
            self.set_text_color(*TEXTO)

        self._cabe(14)
        cabecalho()
        self.set_font("Helvetica", "", 7.5)
        for i, (idx, linha) in enumerate(textos.iterrows()):
            linhas_txt = [_t(linha[c]).split("\n") for c in colunas]
            # quebra textos longos em várias linhas
            partes = [self.multi_cell(l, 4.2, "\n".join(t), dry_run=True, output="LINES") for l, t in zip(largs, linhas_txt)]
            alt = 4.2 * max(len(p) for p in partes) + 1
            if self.get_y() + alt > self.h - self.b_margin:
                self.add_page()
                cabecalho()
                self.set_font("Helvetica", "", 7.5)
            cor = destaque(dados.loc[idx]) if destaque else None
            self.set_fill_color(*(cor or ((249, 250, 251) if i % 2 else (255, 255, 255))))
            y, x = self.get_y(), self.l_margin
            self.rect(x, y, util, alt, style="F")
            for l, p in zip(largs, partes):
                self.set_xy(x, y + 0.5)
                self.multi_cell(l, 4.2, "\n".join(p))
                x += l
            self.set_xy(self.l_margin, y + alt)
        if len(df) > max_linhas:
            self.texto(f"... {len(df) - max_linhas} linha(s) omitidas.")
        self.ln(2)

    def grafico(self, g: Grafico):
        if g.tipo == "mapa":  # no papel vira tabela com as linhas/colunas mais frequentes
            d = g.dados
            linhas = d[g.y].value_counts().head(12).index
            colunas = d[g.x].value_counts().head(12).index
            d = d[d[g.y].isin(linhas) & d[g.x].isin(colunas)]
            piv = d.pivot_table(index=g.y, columns=g.x, values=g.valor, aggfunc="mean").round(0)
            self.secao(g.titulo + " (12 mais frequentes)")
            self.tabela(piv.reset_index(), formatos={c: _fmt_num for c in piv.columns})
            return
        img = graficos.png(g)
        if not img:
            return
        from PIL import Image
        w_px, h_px = Image.open(io.BytesIO(img)).size
        larg = self.w - self.l_margin - self.r_margin
        alt = larg * h_px / w_px
        if alt > ALTURA_MAX_GRAFICO:
            alt = ALTURA_MAX_GRAFICO
            larg = alt * w_px / h_px
        self._cabe(alt + 3)
        self.image(io.BytesIO(img), x=self.l_margin, w=larg, h=alt)
        self.ln(3)

    def bytes(self) -> bytes:
        self.alias_nb_pages()
        return bytes(self.output())


def _fmt_num(v) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.0f}".replace(",", ".")


def _fmt_padrao(v) -> str:
    if isinstance(v, list):
        return "\n".join(map(str, v))
    if isinstance(v, pd.Timestamp):
        return "-" if pd.isna(v) else f"{v:%d/%m/%Y}"
    if isinstance(v, float):
        return "-" if pd.isna(v) else (f"{v:,.0f}".replace(",", ".") if abs(v) >= 100 or v == int(v) else f"{v:.1f}".replace(".", ","))
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "-"
    return str(v)


def botao_pdf(montar: Callable[[], Relatorio], nome_arquivo: str, chave: str, assinatura: str = "") -> None:
    """Botão que gera o PDF sob demanda e oferece o download.
    `assinatura` resume os filtros: se mudarem, o PDF antigo é descartado."""
    c1, c2, _ = st.columns([1.6, 1.4, 3.4])
    if c1.button("Gerar relatório PDF", icon=":material/picture_as_pdf:", key=f"pdf_{chave}", width="stretch"):
        with st.spinner("Montando relatório…"):
            st.session_state[f"pdf_bytes_{chave}"] = (assinatura, montar().bytes())
    sig, dados = st.session_state.get(f"pdf_bytes_{chave}", ("", None))
    if dados and sig == assinatura:
        c2.download_button("Baixar PDF", dados, icon=":material/download:", type="primary", width="stretch", mime="application/pdf",
                           file_name=f"{nome_arquivo}_{pd.Timestamp.now():%Y%m%d_%H%M}.pdf", key=f"dl_{chave}",
                           on_click=lambda: st.session_state.pop(f"pdf_bytes_{chave}", None))
