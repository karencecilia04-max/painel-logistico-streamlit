"""Dados fictícios para a demonstração pública.

Monta as abas no mesmo formato das planilhas reais (colunas A a AF do follow-up
e as abas da planilha de tarifas), com as mesmas inconsistências que aparecem
no preenchimento manual: espaços sobrando, grafias diferentes do mesmo país,
"CFR" no lugar da data de instrução, "LCL" na quantidade de containers.

As datas são calculadas a partir de hoje, para o painel sempre ter navios
chegando, cargas aguardando booking e histórico dos últimos dois anos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEMENTE = 7
N_PROCESSOS = 760

EQUIPES = ["Equipe Azul", "Equipe Verde", "Equipe Laranja"]
CLIENTES = [f"Cliente {i:02d}" for i in range(1, 19)]
EXPORTADORES = [f"Exportador {i:02d}" for i in range(1, 26)]
MODALIDADES = (["Por Encomenda", "Impo. Própria", "Conta e Ordem"], [0.62, 0.30, 0.08])

# origem: (grafias usadas na planilha, peso, transit time médio, frete base em US$)
ORIGENS = {
    "CHINA": (["CHINA", "CHINA "], 0.34, 40, 4300),
    "INDIA": (["INDIA", "INDIA ", "ÍNDIA"], 0.22, 50, 5200),
    "VIETNA": (["VIETNA", "VIETNAM", "VIETNÃ"], 0.18, 37, 3900),
    "TAILANDIA": (["TAILANDIA"], 0.10, 42, 4600),
    "INDONESIA": (["INDONESIA", "INDONÉSIA"], 0.08, 45, 4800),
    "MALASIA": (["MALASIA", "MALÁSIA"], 0.08, 39, 4400),
}
DESTINOS = (["NAVEGANTES", "NAVEGANTES ", "ITAPOA", "ITAPOÁ", "ITAJAI", "ITAJAÍ", "SANTOS", "PECEM"],
            [0.58, 0.07, 0.07, 0.04, 0.07, 0.03, 0.09, 0.05])

# agente: (fator sobre o frete base, dias médios até confirmar o embarque)
AGENTES = {
    "Agente Atlântico": (1.00, 9),
    "Agente Boreal": (0.93, 14),
    "Agente Cais": (1.08, 6),
    "Agente Delta": (0.97, 11),
    "Agente Estuário": (1.12, 5),
    "Agente Farol": (0.95, 17),
}
NAVIOS = ["MV AURORA", "MV BOREAL", "MV CORAL", "MV DUNA", "MV ESTRELA", "MV FAROL",
          "MV GAIVOTA", "MV HORIZONTE", "MV IGUAÇU", "MV JANGADA", "MV LITORAL", "MV MARÉ"]
PREFIXOS_CONTAINER = ["DEMU", "TSTU", "FICU", "EXMU", "SMPU"]


def followup(hoje: pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (ativos, encerrados) no layout bruto: uma coluna por letra, de A (0) a AF (31)."""
    hoje = (hoje or pd.Timestamp.today()).normalize()
    rng = np.random.default_rng(SEMENTE)
    linhas = [_processo(i, hoje, rng) for i in range(N_PROCESSOS)]

    # Algumas cargas instruídas ao agente que ainda esperam booking, com idades variadas
    for j, dias in enumerate([1, 2, 3, 4, 6, 8, 9, 11, 13, 16, 19, 24, 31]):
        linhas.append(_aguardando_booking(N_PROCESSOS + j, hoje, dias, rng))

    df = pd.DataFrame(linhas)
    antigo = (df[13] < hoje - pd.Timedelta(days=150)) & (df[6] == "Concluído")
    encerrados, ativos = df[antigo].copy(), df[~antigo].copy()
    # Um processo encerrado que ficou também no follow-up ativo: a linha ativa prevalece
    ativos = pd.concat([ativos, encerrados.tail(1)], ignore_index=True)
    return ativos.reset_index(drop=True), encerrados.reset_index(drop=True)


def _vazia() -> dict:
    return {c: None for c in range(32)}


def _processo(i: int, hoje: pd.Timestamp, rng: np.random.Generator) -> dict:
    origem = rng.choice(list(ORIGENS), p=[v[1] for v in ORIGENS.values()])
    grafias, _, transit_medio, frete_base = ORIGENS[origem]
    agente = rng.choice(list(AGENTES))
    fator_agente, conf_media = AGENTES[agente]

    embarque = hoje + pd.Timedelta(days=int(rng.integers(-720, 25)))
    transit = int(max(18, rng.normal(transit_medio, 6)))
    chegada = embarque + pd.Timedelta(days=transit)
    instrucao = embarque - pd.Timedelta(days=int(max(1, rng.normal(conf_media, 3))))

    incoterm = rng.choice(["FOB", "CFR", "CIF"], p=[0.88, 0.08, 0.04])
    qtd = [1, 2, 3, 4, "LCL"][rng.choice(5, p=[0.58, 0.22, 0.10, 0.08, 0.02])]

    r = _vazia()
    r[0] = rng.choice(EQUIPES)
    r[1] = f"IMP-{1000 + i}"
    r[3] = rng.choice(CLIENTES)
    r[5] = rng.choice(MODALIDADES[0], p=MODALIDADES[1])
    r[10] = rng.choice(EXPORTADORES)
    r[15] = rng.choice(grafias)
    r[16] = rng.choice(DESTINOS[0], p=DESTINOS[1])
    r[17] = incoterm
    r[24] = qtd
    r[31] = agente

    if qtd != "LCL":
        r[25] = " ".join(_container(rng) for _ in range(qtd))

    # Frete por container: base da origem, fator do agente e alta de 6% ao ano
    if incoterm == "FOB":
        anos = (embarque - hoje).days / 365
        frete = frete_base * fator_agente * (1 + 0.06 * anos) * rng.lognormal(0, 0.12)
        r[29] = round(frete, -1) if rng.random() > 0.03 else 0
        r[30] = instrucao
    else:
        r[30] = rng.choice(["CFR", "CFR", f"CFR - {instrucao:%d/%m}"]) if incoterm == "CFR" else "CIF"

    if rng.random() < 0.03:
        r[6] = "Cancelado"
        return r

    if embarque > hoje:
        r[6] = "Mercadoria em produção"
        r[30] = None
        return r

    r[12] = embarque
    r[13] = chegada
    r[14] = transit
    semana = embarque.isocalendar().week
    r[22] = f"{NAVIOS[(semana + len(origem)) % len(NAVIOS)]} / {semana:03d}E"

    if chegada > hoje:
        r[6] = "Mercadoria em trânsito"
    elif chegada > hoje - pd.Timedelta(days=12):
        r[6] = rng.choice(["Entreposto aduaneiro", "Em desembaraço"])
    else:
        r[6] = "Concluído"

    # Erros comuns de digitação, que a limpeza precisa apontar
    if rng.random() < 0.01:
        r[12] = "a confirmar"
    return r


def _aguardando_booking(i: int, hoje: pd.Timestamp, dias: int, rng: np.random.Generator) -> dict:
    r = _processo(i, hoje + pd.Timedelta(days=400), rng)  # sorteia os campos de um processo futuro
    r[1] = f"IMP-{1000 + i}"
    r[6] = "Aguardando booking"
    r[17] = "FOB"
    r[12] = r[13] = r[14] = r[22] = r[29] = None
    r[30] = hoje - pd.Timedelta(days=dias)
    return r


def _container(rng: np.random.Generator) -> str:
    return f"{rng.choice(PREFIXOS_CONTAINER)}{rng.integers(0, 10**7):07d}"


# ----------------------------------------------------------------- tarifas
PORTOS = ["Navegantes", "Itapoa", "Itajai"]
CIDADES = [("Joinville", "SC", 70), ("Blumenau", "SC", 55), ("Florianopolis", "SC", 110),
           ("Chapeco", "SC", 560), ("Lages", "SC", 300), ("Curitiba", "PR", 200),
           ("Maringa", "PR", 620), ("Londrina", "PR", 590), ("Cascavel", "PR", 610),
           ("Porto Alegre", "RS", 560), ("Caxias do Sul", "RS", 500), ("Passo Fundo", "RS", 520),
           ("Sao Paulo", "SP", 610), ("Campinas", "SP", 680), ("Sorocaba", "SP", 560)]
DISTANCIA_EXTRA = {"Navegantes": 0, "Itapoa": -35, "Itajai": 5}
# transportadora: (R$ por km com container, R$ por km com carreta); None quando não faz o tipo
TRANSPORTADORAS = {"ALFA": (6.1, 5.0), "BETA": (5.8, 5.3), "GAMA": (None, 4.8), "DELTA": (6.5, None)}


def tarifas() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEMENTE)
    frete = []
    for porto in PORTOS:
        for cidade, uf, km in CIDADES:
            km = max(20, km + DISTANCIA_EXTRA[porto])
            linha = {"Porto": porto, "Cidade": cidade, "UF": uf, "KM": km,
                     "Frete_Min_Container": round(900 + km * 5.2, 2),
                     "Frete_Min_Carreta": round(700 + km * 4.3, 2)}
            for nome, (por_km_cont, por_km_carr) in TRANSPORTADORAS.items():
                for sufixo, por_km in (("Container", por_km_cont), ("Carreta", por_km_carr)):
                    if por_km is not None and rng.random() > 0.12:
                        linha[f"{nome}_{sufixo}"] = round((1100 + km * por_km) * rng.uniform(0.92, 1.1), 2)
            frete.append(linha)

    periodos, extras = [], []
    for porto, ajuste in zip(PORTOS, [1.0, 0.94, 1.06]):
        periodos += [
            {"Porto": porto, "Periodo": "1o periodo (1-6 dias)", "Dia_Inicio": 1, "Dia_Fim": 6,
             "Base": "periodo", "Percentual_CIF": round(0.40 * ajuste, 2), "Valor_Fixo": None,
             "Minimo_RS": round(850 * ajuste)},
            {"Porto": porto, "Periodo": "2o periodo (7-14 dias)", "Dia_Inicio": 7, "Dia_Fim": 14,
             "Base": "dia", "Percentual_CIF": round(0.30 * ajuste, 2), "Valor_Fixo": None,
             "Minimo_RS": round(300 * ajuste)},
            {"Porto": porto, "Periodo": "3o periodo (15-29 dias)", "Dia_Inicio": 15, "Dia_Fim": 29,
             "Base": "dia", "Percentual_CIF": round(0.38 * ajuste, 2), "Valor_Fixo": None,
             "Minimo_RS": round(440 * ajuste)},
            {"Porto": porto, "Periodo": "4o periodo (30+ dias)", "Dia_Inicio": 30, "Dia_Fim": None,
             "Base": "indisponivel" if porto == "Itajai" else "dia",
             "Percentual_CIF": round(0.45 * ajuste, 2), "Valor_Fixo": None, "Minimo_RS": round(520 * ajuste)},
        ]
        extras += [
            {"Porto": porto, "Tipo": "sempre", "Chave": "levante", "Descricao": "Levante",
             "Valor_RS": round(500 * ajuste)},
            {"Porto": porto, "Tipo": "sempre", "Chave": "pesagem", "Descricao": "Pesagem",
             "Valor_RS": round(170 * ajuste)},
            {"Porto": porto, "Tipo": "condicional", "Chave": "canalVermelho",
             "Descricao": "Posicionamento para vistoria (canal vermelho)", "Valor_RS": round(1350 * ajuste)},
            {"Porto": porto, "Tipo": "condicional", "Chave": "scanner",
             "Descricao": "Inspeção por scanner", "Valor_RS": round(420 * ajuste)},
        ]

    retirada = [{"Empresa": emp, "Porto": porto, "Valor_RS": valor}
                for emp, base in [("Parceiro Norte", 950), ("Parceiro Sul", 1100)]
                for porto, valor in zip(PORTOS, [base, base - 60, base + 40])]

    operacoes = pd.DataFrame([
        ["Parceiro Norte", "cross", "Crossdocking direto", None, None, None, None, None],
        ["Parceiro Norte", "desova", "Desova + armazenagem + carregamento", "diaria", 480, 10, None, 55],
        ["Parceiro Sul", "cross", "Crossdocking", "proporcional", 950, 2, 30, None],
        ["Parceiro Sul", "armaz", "Armazenagem em bloco", "bloco", 1400, 0, 15, None],
    ], columns=["Empresa", "Operacao_Chave", "Operacao_Label", "Armaz_Modelo", "Armaz_ValorBase",
                "Armaz_FreeTime_Dias", "Armaz_Periodo_Ou_Bloco_Dias", "Armaz_Dia_Excedente_RS"])

    componentes = pd.DataFrame([
        ["Parceiro Norte", "cross", "Crossdocking", 1580],
        ["Parceiro Norte", "desova", "Desova", 900],
        ["Parceiro Norte", "desova", "Carregamento", 900],
        ["Parceiro Sul", "cross", "Crossdocking", 1650],
        ["Parceiro Sul", "armaz", "Movimentação", 700],
    ], columns=["Empresa", "Operacao_Chave", "Componente_Label", "Valor_RS"])

    imposto = pd.DataFrame([
        ["Parceiro Norte", 3, "ISS de 3% sobre todos os itens"],
        ["Parceiro Sul", 0, "Valores com impostos inclusos"],
    ], columns=["Empresa", "Imposto_Pct", "Observacao"])

    parametros = pd.DataFrame([["margem_seguranca_frete", 2,
                                "Margem de segurança aplicada ao frete rodoviário (%)"]],
                              columns=["Chave", "Valor", "Descricao"])

    return {
        "Frete_Rodoviario": pd.DataFrame(frete),
        "Armazenagem_Periodos": pd.DataFrame(periodos),
        "Armazenagem_Extras": pd.DataFrame(extras),
        "Parceiros_Retirada": pd.DataFrame(retirada),
        "Parceiros_Operacoes": operacoes,
        "Parceiros_Componentes": componentes,
        "Parceiros_Imposto": imposto,
        "Parametros": parametros,
    }
