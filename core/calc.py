"""Calculadora de custos de importação, portada do Apps Script da planilha de tarifas.

As tarifas vêm sempre das abas da planilha, nunca ficam fixas aqui.
"""
from __future__ import annotations

import math

import pandas as pd

# Na aba Frete_Rodoviario, cada transportadora tem colunas <NOME>_Container e/ou <NOME>_Carreta
SUFIXOS = {"_Container": "container", "_Carreta": "carreta"}


def colunas_transportadoras(frete: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for col in frete.columns:
        for sufixo, tipo in SUFIXOS.items():
            nome = str(col)[: -len(sufixo)]
            if str(col).endswith(sufixo) and nome != "Frete_Min":
                out.setdefault(nome, {"label": nome.replace("_", " ").title()})[tipo] = col
    return out


def num_or_none(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _rows(df: pd.DataFrame, **filtros) -> list[dict]:
    for k, v in filtros.items():
        df = df[df[k] == v]
    return df.to_dict("records")


def margem_padrao(t: dict) -> float:
    r = _rows(t["Parametros"], Chave="margem_seguranca_frete")
    return float(r[0]["Valor"]) if r else 2.0


# ===================== ETAPA 1: ARMAZENAGEM NO PORTO =====================
def etapa1(t: dict, porto: str, qtd: int, cif_total: float, dias: int,
           condicionais: list[str], ad_valorem_pct: float) -> dict:
    periodos = _rows(t["Armazenagem_Periodos"], Porto=porto)
    extras = _rows(t["Armazenagem_Extras"], Porto=porto)
    qtd = qtd or 1
    cif_unit = (cif_total or 0) / qtd
    dias = (dias or 0) + 1  # mesmo critério do script original (dia de entrada conta)

    linhas, sub_cont, crit = [], 0.0, False
    for p in periodos:
        ini, fim = int(p["Dia_Inicio"]), num_or_none(p["Dia_Fim"])
        if dias < ini:
            continue
        if p["Base"] == "indisponivel":
            crit = True
            linhas.append({"item": p["Periodo"], "valor": 0.0, "alerta": "Período sem tarifa na fonte"})
            continue
        fim_ef = dias if fim is None else min(dias, fim)
        dias_per = int(fim_ef - ini + 1)
        if dias_per <= 0:
            continue
        pct = (num_or_none(p["Percentual_CIF"]) or 0) / 100
        minimo = num_or_none(p["Minimo_RS"]) or 0
        if p["Base"] == "periodo":
            valor = max(cif_unit * pct, minimo)
        elif p["Base"] == "fixo_periodo":
            valor = num_or_none(p["Valor_Fixo"]) or 0
        else:  # 'dia'
            valor = max(cif_unit * pct, minimo) * dias_per
        rotulo = p["Periodo"] + (f", {dias_per} dia(s)" if p["Base"] == "dia" else "")
        linhas.append({"item": rotulo, "valor": valor})
        sub_cont += valor

    extras_total = 0.0
    for e in extras:
        if e["Tipo"] == "sempre" or (e["Tipo"] == "condicional" and e["Chave"] in condicionais):
            v = num_or_none(e["Valor_RS"]) or 0
            linhas.append({"item": e["Descricao"], "valor": v})
            extras_total += v

    ad_val = (cif_total or 0) * (ad_valorem_pct or 0) / 100
    subtotal = sub_cont * qtd + extras_total * qtd + ad_val
    return {"linhas": linhas, "qtd": qtd, "ad_valorem": ad_val, "subtotal": subtotal, "critico": crit}


# ===================== ETAPA 2: CUSTOS LOGÍSTICOS (PARCEIRO) =====================
def etapa2(t: dict, empresa: str, local: str, operacao: str, qtd: int, dias: int) -> dict:
    qtd = qtd or 1
    dias = dias or 0
    imp = _rows(t["Parceiros_Imposto"], Empresa=empresa)
    imposto_pct = num_or_none(imp[0]["Imposto_Pct"]) or 0 if imp else 0

    linhas, sub_cont = [], 0.0
    ret = _rows(t["Parceiros_Retirada"], Empresa=empresa, Porto=local)
    ret_val = num_or_none(ret[0]["Valor_RS"]) if ret else None
    if ret_val is not None:
        linhas.append({"item": "Retirada e devolução de container", "valor": ret_val})
        sub_cont += ret_val
    else:
        linhas.append({"item": "Retirada e devolução de container", "valor": 0.0,
                       "alerta": "Não informado nesta fonte para este porto"})

    for c in _rows(t["Parceiros_Componentes"], Empresa=empresa, Operacao_Chave=operacao):
        v = num_or_none(c["Valor_RS"]) or 0
        linhas.append({"item": c["Componente_Label"], "valor": v})
        sub_cont += v

    ops = _rows(t["Parceiros_Operacoes"], Empresa=empresa, Operacao_Chave=operacao)
    op = ops[0] if ops else None
    modelo = op and op.get("Armaz_Modelo")
    if isinstance(modelo, str) and modelo:
        free = num_or_none(op["Armaz_FreeTime_Dias"]) or 0
        base = num_or_none(op["Armaz_ValorBase"]) or 0
        valor, nota = 0.0, ""
        if dias > free:
            if modelo == "proporcional":
                per = num_or_none(op["Armaz_Periodo_Ou_Bloco_Dias"]) or 1
                valor = dias / per * base
                if dias > per:
                    nota = f"proporcional estendido além de {per:.0f} dias, não confirmado na fonte"
            elif modelo == "bloco":
                bloco = num_or_none(op["Armaz_Periodo_Ou_Bloco_Dias"]) or 1
                n = math.ceil(dias / bloco)
                valor = n * base
                nota = f"{n} bloco(s) cheio(s) de {bloco:.0f} dias, sem proporcionalidade"
            elif modelo == "diaria":
                exc = num_or_none(op["Armaz_Dia_Excedente_RS"]) or 0
                valor = base + (dias - free) * exc
                nota = f"base + {dias - free:.0f} dia(s) excedente(s)"
            linhas.append({"item": "Armazenagem no parceiro", "valor": valor, "nota": nota})
            sub_cont += valor
        else:
            linhas.append({"item": "Armazenagem no parceiro", "valor": 0.0,
                           "nota": f"dentro do tempo livre ({free:.0f} dia(s))"})

    total_serv = sub_cont * qtd
    imposto = total_serv * imposto_pct / 100
    return {"linhas": linhas, "qtd": qtd, "imposto_pct": imposto_pct, "imposto": imposto,
            "subtotal": total_serv + imposto}


# ===================== ETAPA 3: TRANSPORTE RODOVIÁRIO =====================
def _linha_frete(t: dict, porto: str, cidade_uf: str) -> dict | None:
    alvo = cidade_uf.strip().lower()
    for r in _rows(t["Frete_Rodoviario"], Porto=porto):
        if f"{r['Cidade']} / {r['UF']}".strip().lower() == alvo:
            return r
    return None


def destinos(t: dict, porto: str) -> list[str]:
    fr = t["Frete_Rodoviario"]
    fr = fr[fr["Porto"] == porto]
    return sorted({f"{c} / {u}" for c, u in zip(fr["Cidade"], fr["UF"])}, key=str.lower)


def transportadoras(t: dict, porto: str, cidade_uf: str, tipo: str) -> list[dict]:
    row = _linha_frete(t, porto, cidade_uf)
    if not row:
        return []
    out = []
    for k, cfg in colunas_transportadoras(t["Frete_Rodoviario"]).items():
        v = num_or_none(row.get(cfg.get(tipo)))
        if v is not None:
            out.append({"chave": k, "label": cfg["label"], "valor": v})
    return sorted(out, key=lambda x: x["valor"])


def etapa3(t: dict, porto: str, cidade_uf: str, tipo: str, transportadora: str, qtd: int, margem_pct: float) -> dict:
    row = _linha_frete(t, porto, cidade_uf)
    if not row:
        return {"erro": "Destino não encontrado nesta tabela."}
    col = colunas_transportadoras(t["Frete_Rodoviario"]).get(transportadora, {}).get(tipo)
    base = num_or_none(row.get(col)) if col else None
    if base is None:
        return {"erro": "Transportadora sem valor para este tipo de veículo nesta rota."}
    qtd = qtd or 1
    margem = base * (margem_pct or 0) / 100
    fm_ref = num_or_none(row.get("Frete_Min_Container" if tipo == "container" else "Frete_Min_Carreta"))
    return {
        "km": num_or_none(row.get("KM")), "valor_base": base, "margem": margem,
        "valor_com_margem": base + margem, "total": (base + margem) * qtd, "qtd": qtd,
        "fm_ref": fm_ref, "abaixo_minimo": fm_ref is not None and base < fm_ref,
    }
