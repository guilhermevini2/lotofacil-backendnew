"""
hibrido_score.py - Motor central de pontuacao hibrida (0 a 100).

Combina 12 criterios ponderados para gerar um score final por dezena.
Os pesos sao carregados do hibrido_pesos.py (otimizados ou iniciais).
"""

import numpy as np
from config import (
    TOTAL_DEZENAS, DEZENAS_SORTEADAS,
    GRID, MOLDURA, CENTRO, FIBONACCI, PRIMOS, MULTIPLOS3,
    FILTRO_SOMA_MIN, FILTRO_SOMA_MAX,
)
from hibrido_tendencia import classificar_todas, score_tendencia_normalizado


# -- Helpers de normalizacao --------------------------------------------------

def _norm(valores: dict) -> dict:
    mn, mx = min(valores.values()), max(valores.values())
    if mx == mn:
        return {k: 0.5 for k in valores}
    return {k: (v - mn) / (mx - mn) for k, v in valores.items()}


def _freq(historico, dezena, n):
    janela = historico[-n:] if len(historico) >= n else historico
    return sum(1 for s in janela if dezena in s) / len(janela) if janela else 0.0


def _atraso(historico, dezena):
    for i, s in enumerate(reversed(historico)):
        if dezena in s:
            return i
    return len(historico)


def _ciclo(historico, dezena):
    ap = [i for i, s in enumerate(historico) if dezena in s]
    if len(ap) < 2:
        return TOTAL_DEZENAS / DEZENAS_SORTEADAS
    return float(np.mean([ap[j] - ap[j-1] for j in range(1, len(ap))]))


# -- Criterios individuais (cada um retorna dict {dezena: score 0-1}) ---------

def _score_freq(historico, n) -> dict:
    raw = {d: _freq(historico, d, n) for d in range(1, TOTAL_DEZENAS + 1)}
    return _norm(raw)


def _score_tendencia(historico) -> dict:
    clasf = classificar_todas(historico)
    return score_tendencia_normalizado(clasf)


def _score_atraso(historico) -> dict:
    """
    Atraso 'inteligente': pontuacao alta para dezenas proximas do ciclo medio
    (nem muito frescas nem muito atrasadas alem do normal).
    """
    ciclos = {d: _ciclo(historico, d) for d in range(1, TOTAL_DEZENAS + 1)}
    atrasos = {d: _atraso(historico, d) for d in range(1, TOTAL_DEZENAS + 1)}
    raw = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        pressao = atrasos[d] / max(ciclos[d], 1.0)
        # Score maximo proxima de pressao=1.0, decai em ambos os lados
        raw[d] = 1.0 / (1.0 + abs(pressao - 1.0))
    return _norm(raw)


def _score_repeticao(historico) -> dict:
    """Dezenas que repetiram nos ultimos 2-3 concursos recebem penalizacao."""
    if len(historico) < 2:
        return {d: 0.5 for d in range(1, TOTAL_DEZENAS + 1)}
    ultimos = set(historico[-1]) | set(historico[-2]) if len(historico) >= 2 else set(historico[-1])
    return {d: 0.2 if d in ultimos else 0.8 for d in range(1, TOTAL_DEZENAS + 1)}


def _score_linhas_colunas(historico) -> dict:
    """
    Prioriza dezenas em linhas/colunas que historicamente aparecem mais.
    """
    if not historico:
        return {d: 0.5 for d in range(1, TOTAL_DEZENAS + 1)}

    janela = historico[-50:]
    freq_linha  = {r: 0 for r in range(1, 6)}
    freq_coluna = {c: 0 for c in range(1, 6)}
    for s in janela:
        for d in s:
            l, c = GRID[d]
            freq_linha[l]  += 1
            freq_coluna[c] += 1

    raw = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        l, c = GRID[d]
        raw[d] = freq_linha[l] + freq_coluna[c]
    return _norm(raw)


def _score_paridade(historico) -> dict:
    """
    Analisa distribuicao par/impar nos concursos recentes e pontua
    dezenas que equilibram a combinacao esperada.
    """
    if not historico:
        return {d: 0.5 for d in range(1, TOTAL_DEZENAS + 1)}
    janela = historico[-30:]
    media_pares = np.mean([sum(1 for x in s if x % 2 == 0) for s in janela])
    # Dezenas pares recebem bonus se media_pares < 7.5, impares se > 7.5
    scores = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        e_par = d % 2 == 0
        if media_pares < 7.0:
            scores[d] = 0.75 if e_par else 0.40
        elif media_pares > 8.0:
            scores[d] = 0.40 if e_par else 0.75
        else:
            scores[d] = 0.55
    return scores


def _score_moldura(historico) -> dict:
    """
    Analisa proporcao moldura/centro recente e pontua adequadamente.
    """
    if not historico:
        return {d: 0.5 for d in range(1, TOTAL_DEZENAS + 1)}
    janela = historico[-30:]
    media_mold = np.mean([sum(1 for x in s if x in MOLDURA) for s in janela])
    scores = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        e_mold = d in MOLDURA
        if media_mold < 8.5:
            scores[d] = 0.70 if e_mold else 0.45
        elif media_mold > 10.5:
            scores[d] = 0.40 if e_mold else 0.70
        else:
            scores[d] = 0.55
    return scores


def _score_soma_ideal(historico) -> dict:
    """
    Estima se adicionar a dezena aproxima a soma do jogo da faixa ideal.
    Usa a soma media historica como referencia.
    """
    if not historico:
        soma_alvo = (FILTRO_SOMA_MIN + FILTRO_SOMA_MAX) / 2
    else:
        janela = historico[-50:]
        soma_alvo = np.mean([sum(s) for s in janela])

    # Contribuicao de cada dezena para uma soma balanceada
    # Dezenas proximas da media de contribuicao ideal (soma_alvo/15)
    contrib_ideal = soma_alvo / DEZENAS_SORTEADAS
    raw = {d: 1.0 / (1.0 + abs(d - contrib_ideal) / contrib_ideal)
           for d in range(1, TOTAL_DEZENAS + 1)}
    return _norm(raw)


# -- Motor principal ----------------------------------------------------------

def calcular_scores(
    concursos_historico: list[dict],
    pesos: dict,
    ml_probas: dict = None,
) -> dict[int, float]:
    """
    Calcula score hibrido (0-100) para cada dezena.

    Parametros
    ----------
    concursos_historico : lista de dicts de concursos anteriores
    pesos               : dict com pesos dos 12 criterios
    ml_probas           : {dezena: probabilidade} do modelo ML (opcional)

    Retorna
    -------
    {dezena: score_0_100}
    """
    historico = [c["dezenas"] for c in concursos_historico]

    if not historico:
        return {d: 50.0 for d in range(1, TOTAL_DEZENAS + 1)}

    # Calcular todos os criterios
    c_f100 = _score_freq(historico, 100)
    c_f50  = _score_freq(historico, 50)
    c_f20  = _score_freq(historico, 20)
    c_f10  = _score_freq(historico, 10)
    c_tend = _score_tendencia(historico)
    c_atr  = _score_atraso(historico)
    c_rep  = _score_repeticao(historico)
    c_lc   = _score_linhas_colunas(historico)
    c_par  = _score_paridade(historico)
    c_mold = _score_moldura(historico)
    c_soma = _score_soma_ideal(historico)

    # ML: normalizar probabilidades se disponivel
    if ml_probas:
        mn = min(ml_probas.values())
        mx = max(ml_probas.values())
        dif = mx - mn if mx != mn else 1.0
        c_ml = {d: (ml_probas.get(d, mn) - mn) / dif
                for d in range(1, TOTAL_DEZENAS + 1)}
    else:
        # Sem ML: distribuir o peso para freq_10
        c_ml = {d: c_f10[d] for d in range(1, TOTAL_DEZENAS + 1)}

    # Combinar com pesos
    scores = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        score = (
            pesos.get("freq_100",    0.15) * c_f100.get(d, 0.5)
            + pesos.get("freq_50",   0.10) * c_f50.get(d, 0.5)
            + pesos.get("freq_20",   0.15) * c_f20.get(d, 0.5)
            + pesos.get("freq_10",   0.20) * c_f10.get(d, 0.5)
            + pesos.get("tendencia", 0.10) * c_tend.get(d, 0.5)
            + pesos.get("atraso",    0.08) * c_atr.get(d, 0.5)
            + pesos.get("repeticao", 0.05) * c_rep.get(d, 0.5)
            + pesos.get("linhas_cols",0.05) * c_lc.get(d, 0.5)
            + pesos.get("paridade",  0.03) * c_par.get(d, 0.5)
            + pesos.get("moldura",   0.03) * c_mold.get(d, 0.5)
            + pesos.get("soma_ideal",0.03) * c_soma.get(d, 0.5)
            + pesos.get("ml",        0.03) * c_ml.get(d, 0.5)
        )
        scores[d] = round(score * 100, 2)

    return scores


def ranking_hibrido(
    concursos_historico: list[dict],
    pesos: dict,
    ml_probas: dict = None,
    classificacoes: list[dict] = None,
) -> list[dict]:
    """
    Retorna lista ordenada por score hibrido com todos os detalhes por dezena.
    """
    scores = calcular_scores(concursos_historico, pesos, ml_probas)
    historico = [c["dezenas"] for c in concursos_historico]

    # Tendencias
    if classificacoes is None:
        classificacoes = classificar_todas(historico)
    clasf_map = {c["dezena"]: c for c in classificacoes}

    rows = []
    for pos, (dezena, score) in enumerate(
        sorted(scores.items(), key=lambda x: -x[1]), start=1
    ):
        c = clasf_map.get(dezena, {})
        rows.append({
            "posicao":    pos,
            "dezena":     dezena,
            "score":      score,
            "tendencia":  c.get("tendencia", "INDEFINIDA"),
            "seta":       c.get("seta", "?"),
            "label_tend": c.get("label", "?"),
            "freq_10":    round(c.get("freq_10", 0.0) * 100, 1),
            "freq_20":    round(c.get("freq_20", 0.0) * 100, 1),
            "freq_50":    round(c.get("freq_50", 0.0) * 100, 1),
            "atraso":     c.get("atraso", 0),
            "pressao":    c.get("pressao", 0.0),
            "ciclo":      c.get("ciclo", 0.0),
            "prob_ml":    round(ml_probas.get(dezena, 0.0), 4) if ml_probas else None,
        })

    return rows


def tabela_ranking(rows: list[dict], pool_set: set = None) -> str:
    linhas = [
        f"  {'#':>3}  {'Dez':>3}  {'Score':>6}  {'Tend.':>14}  "
        f"{'F10':>5}  {'F20':>5}  {'F50':>5}  {'Atraso':>7}  {'Pressao':>8}",
        "  " + "-" * 72,
    ]
    for r in rows:
        tag = "●" if (pool_set and r["dezena"] in pool_set) else " "
        linhas.append(
            f"  {r['posicao']:>3}  {r['dezena']:>2}{tag}  {r['score']:>6.1f}  "
            f"{r['label_tend']:>14}  "
            f"{r['freq_10']:>4.0f}%  {r['freq_20']:>4.0f}%  {r['freq_50']:>4.0f}%  "
            f"{r['atraso']:>7}  {r['pressao']:>8.2f}"
        )
    return "\n".join(linhas)
