"""
ranking.py — Score inteligente com decaimento exponencial e pares/trios quentes.
"""

from collections import Counter
from itertools import combinations
from config import TOTAL_DEZENAS, JANELAS_TENDENCIA, DECAY_FACTOR, TOP_PARES, TOP_TRIOS


# -- Pesos dos criterios ------------------------------------------------------
PESOS = {
    "freq_decaimento": 0.30,   # frequencia com peso maior para concursos recentes
    "tendencia_10":    0.20,   # frequencia nos ultimos 10
    "tendencia_20":    0.12,   # frequencia nos ultimos 20
    "tendencia_50":    0.08,   # frequencia nos ultimos 50
    "atraso_inverso":  0.15,   # atraso moderado e favoravel
    "pares_quentes":   0.10,   # dezena aparece em pares frequentes
    "trios_quentes":   0.05,   # dezena aparece em trios frequentes
}


def _normalizar(valores: dict) -> dict:
    mn, mx = min(valores.values()), max(valores.values())
    if mx == mn:
        return {d: 0.5 for d in valores}
    return {d: (v - mn) / (mx - mn) for d, v in valores.items()}


# -- Decaimento exponencial ---------------------------------------------------

def frequencia_com_decaimento(concursos: list[dict]) -> dict[int, float]:
    """
    Conta frequencia dando peso exponencialmente maior para concursos recentes.
    O concurso mais recente tem peso 1.0, o anterior DECAY_FACTOR, etc.
    """
    scores = {d: 0.0 for d in range(1, TOTAL_DEZENAS + 1)}
    n = len(concursos)
    for i, cs in enumerate(concursos):
        peso = DECAY_FACTOR ** (n - 1 - i)   # mais recente = peso maior
        for d in cs["dezenas"]:
            scores[d] += peso
    return scores


# -- Pares e trios quentes ----------------------------------------------------

def calcular_pares_quentes(concursos: list[dict], top_n: int = TOP_PARES) -> list[tuple]:
    """
    Retorna os TOP_N pares de dezenas que mais aparecem juntos.
    [(dezena_a, dezena_b, contagem), ...]
    """
    contador = Counter()
    for cs in concursos:
        for par in combinations(sorted(cs["dezenas"]), 2):
            contador[par] += 1
    return [(a, b, c) for (a, b), c in contador.most_common(top_n)]


def calcular_trios_quentes(concursos: list[dict], top_n: int = TOP_TRIOS) -> list[tuple]:
    """
    Retorna os TOP_N trios de dezenas que mais aparecem juntos.
    [(a, b, c, contagem), ...]
    """
    contador = Counter()
    for cs in concursos:
        for trio in combinations(sorted(cs["dezenas"]), 3):
            contador[trio] += 1
    return [(a, b, c, cnt) for (a, b, c), cnt in contador.most_common(top_n)]


def score_pares_por_dezena(pares_quentes: list[tuple]) -> dict[int, float]:
    """Quanto cada dezena aparece nos pares quentes (score acumulado)."""
    scores = {d: 0.0 for d in range(1, TOTAL_DEZENAS + 1)}
    for a, b, cnt in pares_quentes:
        scores[a] += cnt
        scores[b] += cnt
    return scores


def score_trios_por_dezena(trios_quentes: list[tuple]) -> dict[int, float]:
    """Quanto cada dezena aparece nos trios quentes."""
    scores = {d: 0.0 for d in range(1, TOTAL_DEZENAS + 1)}
    for a, b, c, cnt in trios_quentes:
        scores[a] += cnt
        scores[b] += cnt
        scores[c] += cnt
    return scores


# -- Score principal ----------------------------------------------------------

def calcular_scores(stats: dict, concursos: list[dict]) -> dict[int, float]:
    dezenas = list(range(1, TOTAL_DEZENAS + 1))

    # Frequencia com decaimento exponencial
    freq_decay = frequencia_com_decaimento(concursos)
    freq_decay_norm = _normalizar(freq_decay)

    # Tendencias por janela
    tend = stats["tendencia"]
    tend10_norm = _normalizar({d: tend[d].get(10, 0.0) for d in dezenas})
    tend20_norm = _normalizar({d: tend[d].get(20, 0.0) for d in dezenas})
    tend50_norm = _normalizar({d: tend[d].get(50, 0.0) for d in dezenas})

    # Atraso inverso
    atrasos = stats["atraso"]
    media_atraso = sum(atrasos.values()) / len(atrasos)
    atr_score = {d: 1.0 - abs(v - media_atraso) / max(media_atraso, 1)
                 for d, v in atrasos.items()}
    atr_norm = _normalizar(atr_score)

    # Pares e trios quentes
    pares = calcular_pares_quentes(concursos)
    trios = calcular_trios_quentes(concursos)
    pares_score = _normalizar(score_pares_por_dezena(pares))
    trios_score = _normalizar(score_trios_por_dezena(trios))

    scores = {}
    for d in dezenas:
        scores[d] = (
            PESOS["freq_decaimento"] * freq_decay_norm[d]
            + PESOS["tendencia_10"]  * tend10_norm[d]
            + PESOS["tendencia_20"]  * tend20_norm[d]
            + PESOS["tendencia_50"]  * tend50_norm[d]
            + PESOS["atraso_inverso"] * atr_norm[d]
            + PESOS["pares_quentes"] * pares_score[d]
            + PESOS["trios_quentes"] * trios_score[d]
        )
    return scores


def top_n(stats: dict, concursos: list[dict], n: int = 18) -> list[int]:
    """Retorna lista ordenada com as N dezenas de maior score."""
    scores = calcular_scores(stats, concursos)
    ranking = sorted(scores.items(), key=lambda x: -x[1])
    return sorted(d for d, _ in ranking[:n])


def top18(stats: dict, n_concursos: int = 0, concursos: list[dict] = None) -> list[int]:
    """Compatibilidade com chamadas antigas."""
    return top_n(stats, concursos or [], 18)


def ranking_completo(stats: dict, n_concursos: int, concursos: list[dict] = None) -> list[dict]:
    concursos = concursos or []
    scores = calcular_scores(stats, concursos)
    atrasos = stats["atraso"]
    freq_abs = stats["freq_abs"]
    freq_pct = stats["freq_pct"]
    tend = stats["tendencia"]
    freq_decay = frequencia_com_decaimento(concursos)

    rows = []
    for pos, (dezena, score) in enumerate(
        sorted(scores.items(), key=lambda x: -x[1]), start=1
    ):
        rows.append({
            "posicao":      pos,
            "dezena":       dezena,
            "score":        round(score, 4),
            "freq_abs":     freq_abs[dezena],
            "freq_pct":     freq_pct[dezena],
            "freq_decay":   round(freq_decay[dezena], 2),
            "atraso":       atrasos[dezena],
            **{f"tend_{n}": tend[dezena].get(n, 0.0) for n in JANELAS_TENDENCIA},
        })
    return rows
