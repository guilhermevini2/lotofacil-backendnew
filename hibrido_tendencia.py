"""
hibrido_tendencia.py - Classificacao de tendencia de cada dezena.

Identifica:
  ESQUENTANDO   - frequencia crescente nas janelas recentes
  ESFRIANDO     - frequencia caindo nas janelas recentes
  ESTAVEL       - frequencia consistente ao longo do tempo
  CICLO_RETORNO - atrasada alem do ciclo medio (provavel retorno)
  SATURADA      - saiu nos ultimos concursos, acima da media
  INDEFINIDA    - historico insuficiente
"""

import numpy as np
from config import TOTAL_DEZENAS, DEZENAS_SORTEADAS


# -- Helpers ------------------------------------------------------------------

def _freq(historico: list[list[int]], dezena: int, n: int) -> float:
    janela = historico[-n:] if len(historico) >= n else historico
    return sum(1 for s in janela if dezena in s) / len(janela) if janela else 0.0


def _atraso(historico: list[list[int]], dezena: int) -> int:
    for i, s in enumerate(reversed(historico)):
        if dezena in s:
            return i
    return len(historico)


def _ciclo_medio(historico: list[list[int]], dezena: int) -> float:
    aparicoes = [i for i, s in enumerate(historico) if dezena in s]
    if len(aparicoes) < 2:
        return DEZENAS_SORTEADAS / TOTAL_DEZENAS * TOTAL_DEZENAS / DEZENAS_SORTEADAS
    gaps = [aparicoes[j] - aparicoes[j-1] for j in range(1, len(aparicoes))]
    return float(np.mean(gaps))


# -- Classificador principal --------------------------------------------------

LABELS = {
    "ESQUENTANDO":   "↑ Esquentando",
    "ESFRIANDO":     "↓ Esfriando",
    "ESTAVEL":       "→ Estável",
    "CICLO_RETORNO": "⟳ Ciclo retorno",
    "SATURADA":      "▪ Saturada",
    "INDEFINIDA":    "? Indefinida",
}

SETAS = {
    "ESQUENTANDO":   "↑",
    "ESFRIANDO":     "↓",
    "ESTAVEL":       "→",
    "CICLO_RETORNO": "⟳",
    "SATURADA":      "▪",
    "INDEFINIDA":    "?",
}


def classificar_dezena(
    historico: list[list[int]],
    dezena: int,
) -> dict:
    """
    Classifica a tendencia de uma dezena e retorna metricas detalhadas.
    """
    if len(historico) < 10:
        return {
            "dezena":    dezena,
            "tendencia": "INDEFINIDA",
            "label":     LABELS["INDEFINIDA"],
            "seta":      SETAS["INDEFINIDA"],
            "score_tend": 0.0,
            "freq_10":   0.0,
            "freq_20":   0.0,
            "freq_50":   0.0,
            "atraso":    0,
            "ciclo":     0.0,
            "pressao":   0.0,
        }

    f10  = _freq(historico, dezena, 10)
    f20  = _freq(historico, dezena, 20)
    f50  = _freq(historico, dezena, 50)
    f100 = _freq(historico, dezena, 100)
    atr  = _atraso(historico, dezena)
    ciclo = _ciclo_medio(historico, dezena)
    pressao = atr / max(ciclo, 1.0)

    # Score de tendencia: diferencas entre janelas
    # Positivo = acelerando, Negativo = desacelerando
    delta_curto  = f10  - f20   # janela curta vs media
    delta_medio  = f20  - f50   # janela media vs longa
    delta_longo  = f50  - f100  # janela longa vs historica

    # Tendencia ponderada
    score_tend = 0.5 * delta_curto + 0.35 * delta_medio + 0.15 * delta_longo
    esperado = DEZENAS_SORTEADAS / TOTAL_DEZENAS  # ~0.60

    # Classificacao
    if pressao >= 2.0:
        tendencia = "CICLO_RETORNO"
    elif f10 > esperado * 1.25 and score_tend > 0.02:
        tendencia = "ESQUENTANDO"
    elif f10 < esperado * 0.75 and score_tend < -0.02:
        tendencia = "ESFRIANDO"
    elif atr == 0 and f10 > esperado * 1.20:
        tendencia = "SATURADA"
    elif abs(score_tend) <= 0.03 and abs(f10 - esperado) < 0.10:
        tendencia = "ESTAVEL"
    elif score_tend > 0.01:
        tendencia = "ESQUENTANDO"
    elif score_tend < -0.01:
        tendencia = "ESFRIANDO"
    else:
        tendencia = "ESTAVEL"

    return {
        "dezena":     dezena,
        "tendencia":  tendencia,
        "label":      LABELS[tendencia],
        "seta":       SETAS[tendencia],
        "score_tend": round(score_tend, 4),
        "freq_10":    round(f10,  4),
        "freq_20":    round(f20,  4),
        "freq_50":    round(f50,  4),
        "freq_100":   round(f100, 4),
        "atraso":     atr,
        "ciclo":      round(ciclo, 2),
        "pressao":    round(pressao, 2),
    }


def classificar_todas(historico: list[list[int]]) -> list[dict]:
    """Classifica todas as 25 dezenas."""
    return [classificar_dezena(historico, d) for d in range(1, TOTAL_DEZENAS + 1)]


def score_tendencia_normalizado(classificacoes: list[dict]) -> dict[int, float]:
    """
    Converte classificacoes em score normalizado [0,1] para uso no motor hibrido.
    ESQUENTANDO/CICLO_RETORNO recebem scores altos.
    ESFRIANDO/SATURADA recebem scores baixos.
    """
    mapa_base = {
        "ESQUENTANDO":   0.85,
        "CICLO_RETORNO": 0.75,
        "ESTAVEL":       0.55,
        "INDEFINIDA":    0.50,
        "ESFRIANDO":     0.30,
        "SATURADA":      0.25,
    }

    scores = {}
    for c in classificacoes:
        base = mapa_base.get(c["tendencia"], 0.5)
        # Ajustar pelo score de tendencia (intensidade)
        ajuste = np.clip(c["score_tend"] * 2.0, -0.25, 0.25)
        # Ajustar pela pressao (ciclo de retorno mais urgente)
        pressao_bonus = np.clip((c["pressao"] - 1.0) * 0.1, 0.0, 0.15)
        scores[c["dezena"]] = float(np.clip(base + ajuste + pressao_bonus, 0.0, 1.0))

    return scores


def resumo_tendencias(classificacoes: list[dict]) -> str:
    contagem = {}
    for c in classificacoes:
        t = c["tendencia"]
        contagem[t] = contagem.get(t, 0) + 1

    linhas = [
        "=" * 55,
        "  TENDENCIAS DAS 25 DEZENAS",
        "=" * 55,
    ]
    for t, label in LABELS.items():
        n = contagem.get(t, 0)
        if n > 0:
            dezenas = [c["dezena"] for c in classificacoes if c["tendencia"] == t]
            linhas.append(f"  {label:<20} {n:2d}x — " +
                          " ".join(f"{d:02d}" for d in dezenas))
    linhas.append("=" * 55)
    return "\n".join(linhas)


def tabela_tendencias(classificacoes: list[dict], pool_set: set = None) -> str:
    """Tabela formatada para exibicao no terminal."""
    linhas = [
        f"  {'Dez':>4}  {'Score':>7}  {'Tend.':>6}  {'F10':>6}  {'F20':>6}  "
        f"{'F50':>6}  {'Atraso':>7}  {'Pressao':>8}  {'Ciclo':>6}",
        "  " + "-" * 72,
    ]
    for c in sorted(classificacoes, key=lambda x: -x.get("score_tend", 0)):
        pool_tag = "●" if (pool_set and c["dezena"] in pool_set) else " "
        linhas.append(
            f"  {c['dezena']:>2}{pool_tag}   {c['score_tend']:>+6.3f}  "
            f"{c['seta']:>6}  "
            f"{c['freq_10']*100:>5.1f}%  {c['freq_20']*100:>5.1f}%  "
            f"{c['freq_50']*100:>5.1f}%  {c['atraso']:>7}  "
            f"{c['pressao']:>8.2f}  {c['ciclo']:>6.1f}"
        )
    return "\n".join(linhas)
