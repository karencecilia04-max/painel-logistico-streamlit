"""Carga e limpeza dos dados das planilhas.

A fonte é escolhida nesta ordem:
1. Google Sheets, pela conta de serviço em st.secrets["gcp_service_account"];
2. arquivos .xlsx em data/, que nunca vão para o repositório;
3. dados fictícios gerados em core/demo.py.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from core import demo

# Os IDs das planilhas ficam em st.secrets["planilhas"], nunca no código:
#   [planilhas]  followup = "..."  encerrados = "..."  tarifas = "..."
FOLLOWUP_ABA = "Consolidado"
ENCERRADOS_ABA = "CONCLUIDOS"  # histórico de processos encerrados, com as mesmas colunas do Consolidado
TARIFAS_ABAS = [
    "Frete_Rodoviario", "Armazenagem_Periodos", "Armazenagem_Extras",
    "Parceiros_Retirada", "Parceiros_Operacoes", "Parceiros_Componentes",
    "Parceiros_Imposto", "Parametros",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_TTL = 600  # 10 min

# Letra da coluna no follow-up -> nome interno
COLUNAS = {
    "A": "equipe", "B": "ref", "D": "cliente", "F": "modalidade", "G": "status",
    "K": "exportador", "M": "dt_embarque", "N": "dt_chegada", "O": "transit_time",
    "P": "origem", "Q": "destino", "R": "incoterm", "W": "navio",
    "Y": "qtd_containers", "Z": "containers", "AD": "frete", "AE": "dt_instrucao",
    "AF": "agente",
}

# Portos acompanhados no painel de atracação
PORTOS = {
    "NAVEGANTES": "Navegantes (Portonave)",
    "ITAPOA": "Itapoá (Porto Itapoá)",
    "ITAJAI": "Itajaí (Porto de Itajaí)",
}

NOME_PORTO = {"ITAPOA": "Itapoá", "ITAJAI": "Itajaí", "PECEM": "Pecém", "VITORIA": "Vitória"}

ORIGEM_ALIAS ={"VIETNA": "VIETNA", "VIETNAM": "VIETNA", "VIETNAN": "VIETNA", "MALASIA": "MALASIA"}
# Grafias diferentes do mesmo agente, ex.: {"AGENTE X LTDA": "Agente X"}
AGENTE_ALIAS: dict[str, str] = {}
STATUS_FECHADOS = {"CONCLUIDO", "CANCELADO"}
LIXO = {"", "CARREGANDO DADOS...", "X", "-", "N/A"}


def _letra_para_indice(letra: str) -> int:
    n = 0
    for ch in letra:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def _chave(v) -> str:
    """Normaliza texto para comparação: sem acento, maiúsculo, espaços únicos."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", " ", sem_acento(str(v))).strip().upper()


def _texto(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if _chave(s) in LIXO else s


def _numero(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    if "," in s:  # formato BR: 1.600,00
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


ANO_MIN, ANO_MAX = 2015, 2035


# Textos que aparecem na Instrução de Embarque quando o frete é do exportador: não é erro
NAO_SE_APLICA = {"CFR", "CIF", "CPT", "CIP", "DAP", "DDP"}
RE_DIA_MES = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def _data_info(v, ano_ref=None) -> tuple:
    """Converte uma célula de data. Devolve (data, situação):
    ''          ok ou vazia
    'corrigida' valor ajustado automaticamente (ex.: ano 206 vira 2026, 'CFR - 16/03')
    'n/a'       não se aplica (ex.: 'CFR' na instrução de embarque)
    'invalida'  preenchida com algo que não é data
    """
    if v is None or (not isinstance(v, str) and pd.isna(v)) or _chave(v) in LIXO:
        return pd.NaT, ""
    if isinstance(v, str):
        chave = _chave(v)
        if chave in NAO_SE_APLICA:
            return pd.NaT, "n/a"
        m = RE_DIA_MES.search(v)
        if m and not re.fullmatch(r"[\d/\s:.-]+", v.strip()):  # data no meio de um texto: 'CFR - 16/03'
            dia, mes, ano = int(m[1]), int(m[2]), m[3]
            if ano:
                ano = int(ano) + (2000 if len(ano) == 2 else 0)
            else:
                ano = int(ano_ref) if ano_ref and not pd.isna(ano_ref) else pd.Timestamp.today().year
            try:
                return pd.Timestamp(ano, mes, dia), "corrigida"
            except (ValueError, TypeError):
                return pd.NaT, "invalida"
    try:
        if hasattr(v, "year"):
            ts = pd.Timestamp(v)
        elif isinstance(v, (int, float)):  # serial do Sheets
            if v <= 0:
                return pd.NaT, "invalida"
            ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(v))
        else:
            ts = pd.to_datetime(str(v).strip(), dayfirst=True)
    except (ValueError, OverflowError, TypeError):
        return pd.NaT, "invalida"
    if 200 <= ts.year <= 209:  # digitou '206' em vez de '2026'
        return ts.replace(year=2020 + ts.year - 200).normalize(), "corrigida"
    if ANO_MIN <= ts.year <= ANO_MAX:
        return ts.normalize(), ""
    return pd.NaT, "invalida"


def _data(v):
    return _data_info(v)[0]


# ----------------------------------------------------------------- leitura bruta
def _cliente_gspread():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(creds)


def _falha_google(nome: str, aba: str | None, erro: Exception):
    """Mostra o motivo real da falha (o Streamlit Cloud esconde o traceback) e para a página."""
    import gspread

    # o gspread 6 transforma o 403 da API num PermissionError vazio; o motivo real fica na causa
    if isinstance(erro, PermissionError) and isinstance(erro.__cause__, Exception):
        erro = erro.__cause__

    try:
        conta = st.secrets["gcp_service_account"].get("client_email", "?")
    except Exception:
        conta = "?"
    if isinstance(erro, gspread.exceptions.SpreadsheetNotFound):
        motivo = (f"Planilha '{nome}' não encontrada. Confira o ID em Secrets, seção [planilhas], e compartilhe "
                  f"a planilha com **{conta}** (Leitor).")
    elif isinstance(erro, gspread.exceptions.WorksheetNotFound):
        motivo = f"A planilha '{nome}' não tem a aba **{aba}** (o nome precisa ser idêntico)."
    elif isinstance(erro, gspread.exceptions.APIError):
        codigo = getattr(erro, "code", "?")
        texto = str(erro)
        if "has not been used" in texto or "is disabled" in texto:
            motivo = "A **Google Sheets API** não está ativada no projeto da conta de serviço (Google Cloud, menu APIs)."
        elif "not supported for this document" in texto:
            motivo = (f"A planilha '{nome}' é um arquivo **.xlsx** no Drive, não uma Planilha Google. "
                      "Abra e use Arquivo > Salvar como Planilhas Google, e use o ID da nova.")
        elif codigo == 403:
            motivo = f"Sem permissão na planilha '{nome}'. Compartilhe com **{conta}** (Leitor)."
        else:
            motivo = f"Erro da API do Google ({codigo}) na planilha '{nome}'."
    elif isinstance(erro, (ValueError, KeyError)) or "google.auth" in type(erro).__module__:
        motivo = ("Credencial da conta de serviço inválida em Secrets, seção [gcp_service_account] "
                  "(confira private_key com os \\n e o client_email). Gere de novo com gerar_secrets.py.")
    else:
        motivo = f"Falha ao ler a planilha '{nome}'."
    st.error(f"{motivo}\n\nDetalhe técnico: `{type(erro).__name__}: {str(erro)[:300]}`")
    st.stop()


def _abrir(nome: str):
    try:
        return _cliente_gspread().open_by_key(planilha_id(nome))
    except Exception as e:  # noqa: BLE001  qualquer falha vira mensagem legível
        _falha_google(nome, None, e)


def _valores(sh, nome: str, aba: str) -> list[list]:
    try:
        return sh.worksheet(aba).get_all_values(value_render_option="UNFORMATTED_VALUE")
    except Exception as e:  # noqa: BLE001
        _falha_google(nome, aba, e)


def usa_credencial() -> bool:
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


def fonte() -> str:
    """"google", "local" ou "demo"."""
    if usa_credencial():
        return "google"
    if (DATA_DIR / "followup.xlsx").exists():
        return "local"
    return "demo"


def planilha_id(nome: str) -> str:
    """ID da planilha guardado nos secrets ([planilhas] followup / encerrados / tarifas)."""
    try:
        return st.secrets["planilhas"][nome]
    except (KeyError, FileNotFoundError):
        st.error(f"Falta o ID da planilha '{nome}' em Secrets, seção [planilhas]. Veja o README.")
        st.stop()


def _aba_bruta(nome: str, aba: str, arquivo_local: str, obrigatoria: bool = True) -> pd.DataFrame:
    if usa_credencial():
        try:
            st.secrets["planilhas"][nome]
        except KeyError:
            if not obrigatoria:  # planilha opcional não configurada: segue sem ela
                return pd.DataFrame()
        valores = _valores(_abrir(nome), nome, aba)
        return pd.DataFrame(valores[1:])
    arq = DATA_DIR / arquivo_local
    if not arq.exists():
        if not obrigatoria:
            return pd.DataFrame()
        st.error(f"Sem credencial do Google e sem arquivo local em data/{arquivo_local}. Veja o README.")
        st.stop()
    # o .xlsx pode levar ~40 s para abrir; guarda uma cópia rápida e só relê se o .xlsx mudar
    rapido = arq.with_suffix(".cache.pkl")
    if rapido.exists() and rapido.stat().st_mtime >= arq.stat().st_mtime:
        return pd.read_pickle(rapido)
    df = pd.read_excel(arq, sheet_name=aba, header=None, skiprows=1)
    df.to_pickle(rapido)
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner="Lendo follow-up e processos encerrados…")
def _followup_bruto() -> pd.DataFrame:
    if fonte() == "demo":
        ativos, encerrados = demo.followup()
    else:
        ativos = _aba_bruta("followup", FOLLOWUP_ABA, "followup.xlsx")
        encerrados = _aba_bruta("encerrados", ENCERRADOS_ABA, "encerrados.xlsx", obrigatoria=False)
    ativos = ativos.assign(_base="Ativo")
    if encerrados.empty:
        return ativos
    # alinha pelas colunas comuns (A..última do menor) e marca a origem
    n = min(ativos.shape[1] - 1, encerrados.shape[1])  # -1 tira a coluna _base já adicionada
    ativos = ativos.iloc[:, list(range(n)) + [-1]]
    encerrados = encerrados.iloc[:, :n].assign(_base="Encerrado")
    ativos.columns = encerrados.columns = list(range(n)) + ["_base"]
    return pd.concat([ativos, encerrados], ignore_index=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner="Lendo tabelas de tarifas…")
def tarifas() -> dict[str, pd.DataFrame]:
    if usa_credencial():
        sh = _abrir("tarifas")
        out = {}
        for aba in TARIFAS_ABAS:
            vals = _valores(sh, "tarifas", aba)
            out[aba] = pd.DataFrame(vals[1:], columns=vals[0]).replace("", None)
        return out
    arq = DATA_DIR / "tarifas.xlsx"
    if not arq.exists():
        return demo.tarifas()
    return {aba: pd.read_excel(arq, sheet_name=aba) for aba in TARIFAS_ABAS}


# ----------------------------------------------------------------- follow-up limpo
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def followup() -> pd.DataFrame:
    bruto = _followup_bruto()
    df = pd.DataFrame({
        nome: bruto.iloc[:, _letra_para_indice(letra)] if _letra_para_indice(letra) < bruto.shape[1] else None
        for letra, nome in COLUNAS.items()
    })
    df["base"] = bruto["_base"].values

    for c in ["equipe", "ref", "cliente", "modalidade", "status", "exportador", "origem",
              "destino", "incoterm", "navio", "agente"]:
        df[c] = df[c].map(_texto)
    df = df[df["ref"].notna()].copy()
    # ref repetida: vale a do Consolidado (mais atual); entre encerrados, a última linha
    df["_ordem"] = df["base"].eq("Ativo").astype(int)
    df = df.sort_values("_ordem", kind="stable").drop_duplicates("ref", keep="last").drop(columns="_ordem")

    # datas: guarda o valor original para mostrar ao time o que estava na célula
    problemas, corrigidas = [""] * len(df), [""] * len(df)
    for c, rotulo in [("dt_embarque", "Data de Embarque (M)"), ("dt_chegada", "Data de Chegada (N)"),
                      ("dt_instrucao", "Instrução de Embarque (AE)")]:
        anos_ref = df["dt_embarque"].map(lambda d: d.year if isinstance(d, pd.Timestamp) and pd.notna(d) else None) \
            if c == "dt_instrucao" else [None] * len(df)
        convertidos, situacoes = zip(*[_data_info(v, a) for v, a in zip(df[c], anos_ref)]) if len(df) else ((), ())
        for i, (sit, orig) in enumerate(zip(situacoes, df[c])):
            if sit == "invalida":
                problemas[i] += f"{rotulo}: '{str(orig).strip()[:25]}'; "
            elif sit == "corrigida":
                corrigidas[i] += f"{rotulo}: '{str(orig).strip()[:25]}' lido como {convertidos[i]:%d/%m/%Y}; "
        df[c] = pd.to_datetime(pd.Series(convertidos, index=df.index))
    df["problemas"] = [p.rstrip("; ") for p in problemas]
    df["correcoes"] = [p.rstrip("; ") for p in corrigidas]
    for c in ["transit_time", "frete"]:
        df[c] = df[c].map(_numero)

    df["lcl"] = df["qtd_containers"].map(_chave).eq("LCL")
    df["qtd_containers"] = df["qtd_containers"].map(_numero)
    df["containers"] = df["containers"].map(
        lambda v: [c for c in re.split(r"[\s,;/]+", str(v).upper()) if re.fullmatch(r"[A-Z]{4}\d{6,7}", c)]
        if _texto(v) else []
    )
    # se a quantidade não foi preenchida mas há números de container, usa a contagem
    sem_qtd = df["qtd_containers"].isna() & df["containers"].map(len).gt(0)
    # astype(float): no pandas 3, atribuir a série vazia (dtype object) numa coluna float dá TypeError
    df.loc[sem_qtd, "qtd_containers"] = df.loc[sem_qtd, "containers"].map(len).astype(float)

    df["status_chave"] = df["status"].map(_chave)
    df["destino_chave"] = df["destino"].map(_chave)
    df["porto"] = df["destino_chave"].map(lambda k: NOME_PORTO.get(k, k.title()) if k else None)
    df["origem"] = df["origem"].map(lambda v: ORIGEM_ALIAS.get(_chave(v), _chave(v)) or None)
    df["agente"] = df["agente"].map(lambda v: AGENTE_ALIAS.get(_chave(v), v) if v else None)
    df["navio_nome"] = df["navio"].map(lambda v: _chave(v).split(" / ")[0].strip() or None if v else None)

    df["cancelado"] = df["status_chave"].str.contains("CANCELADO", na=False)
    df["aberto"] = df["base"].eq("Ativo") & ~df["status_chave"].isin(STATUS_FECHADOS) & ~df["cancelado"]

    # indicadores derivados
    df["dias_confirmacao"] = (df["dt_embarque"] - df["dt_instrucao"]).dt.days
    df.loc[~df["dias_confirmacao"].between(0, 365), "dias_confirmacao"] = None
    tt_calc = (df["dt_chegada"] - df["dt_embarque"]).dt.days
    tt_col = df["transit_time"].where(df["transit_time"].between(1, 150))
    df["transit_dias"] = tt_calc.where(tt_calc.between(1, 150), tt_col)
    return df.reset_index(drop=True)


def opcoes(serie: pd.Series) -> list[str]:
    return sorted(serie.dropna().unique().tolist(), key=_chave)
