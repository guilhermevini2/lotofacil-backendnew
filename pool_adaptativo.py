"""
pool_adaptativo.py — Testa pools de diferentes tamanhos e escolhe o melhor
custo-beneficio entre cobertura e numero de jogos.
"""

import itertools
from config import POOL_SIZES, DEZENAS_SORTEADAS

# Matrizes pre-definidas para cada tamanho de pool
# Cada matriz garante 14 pontos se todos os 15 sorteados caírem no pool

# 18 dezenas -> 24 jogos (ja existe em config.py, importamos de la)
from config import INDICES_FECHAMENTO as MATRIZ_18

# 19 dezenas -> 38 jogos (fechamento 19-15-14)
MATRIZ_19 = [
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,17,18,19],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,13,14,15,17,18,19],
    [ 1, 2, 3, 4, 5, 6,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6,10,11,12,13,14,15,17,18,19],
    [ 1, 2, 3, 7, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 7, 8, 9,10,11,12,13,14,15,17,18,19],
    [ 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,17,18,19],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,14,16,17],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,15,16,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,14,15,17,18],
    [ 1, 2, 4, 5, 7, 8,10,11,12,13,14,15,16,17,18],
    [ 1, 3, 4, 6, 7, 9,10,11,12,13,14,15,16,17,18],
    [ 2, 3, 5, 6, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,15,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,14,15,16,19],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,14,17,19],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,14,15,16,17],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,13,14,16,19],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,13,15,16,17],
    [ 1, 2, 4, 6, 8, 9,10,11,12,13,14,15,16,17,19],
    [ 1, 2, 5, 6, 7, 9,10,11,12,13,14,15,16,18,19],
    [ 1, 3, 4, 5, 8, 9,10,11,12,13,14,15,16,17,19],
    [ 1, 3, 5, 6, 7, 8,10,11,12,13,14,15,16,18,19],
    [ 2, 3, 4, 5, 7, 9,10,11,12,13,14,15,16,17,19],
    [ 2, 3, 4, 6, 7, 8,10,11,12,13,14,15,16,17,19],
    [ 1, 2, 3, 4, 5, 7, 8,10,11,13,15,16,17,18,19],
    [ 1, 2, 3, 5, 6, 7, 9,10,12,14,15,16,17,18,19],
    [ 1, 2, 4, 5, 6, 8, 9,11,13,14,15,16,17,18,19],
    [ 1, 3, 4, 5, 6, 7, 8,12,13,14,15,16,17,18,19],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,15,16,18,19],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,14,17,18,19],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,15,16,17,19],
    [ 2, 3, 4, 5, 6, 7, 8, 9,11,12,14,15,16,17,18],
    [ 2, 3, 4, 5, 6, 7, 8,10,11,12,13,14,15,18,19],
]

# 20 dezenas -> 54 jogos (fechamento 20-15-14)
MATRIZ_20 = [
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,18,19,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,13,14,15,18,19,20],
    [ 1, 2, 3, 4, 5, 6,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6,10,11,12,13,14,15,18,19,20],
    [ 1, 2, 3, 7, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 7, 8, 9,10,11,12,13,14,15,18,19,20],
    [ 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,18,19,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,16,17,18,19,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,13,16,17,18,19,20],
    [ 1, 2, 3, 4, 5, 6,10,11,12,16,17,18,19,20,15],
    [ 1, 2, 3, 7, 8, 9,10,11,12,16,17,18,19,20,15],
    [ 4, 5, 6, 7, 8, 9,10,11,12,16,17,18,19,20,15],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,14,16,17],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,15,16,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,14,15,17,18],
    [ 1, 2, 4, 5, 7, 8,10,11,12,13,14,15,16,17,18],
    [ 1, 3, 4, 6, 7, 9,10,11,12,13,14,15,16,17,18],
    [ 2, 3, 5, 6, 8, 9,10,11,12,13,14,15,16,17,18],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,15,19,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,14,15,16,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,14,17,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,10,12,14,15,19,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,13,14,16,20],
    [ 1, 2, 3, 4, 5, 6, 7, 8, 9,11,12,13,15,16,19],
    [ 1, 2, 4, 6, 8, 9,10,11,12,13,14,15,16,19,20],
    [ 1, 2, 5, 6, 7, 9,10,11,12,13,14,15,16,18,20],
    [ 1, 3, 4, 5, 8, 9,10,11,12,13,14,15,16,17,20],
    [ 1, 3, 5, 6, 7, 8,10,11,12,13,14,15,17,18,20],
    [ 2, 3, 4, 5, 7, 9,10,11,12,13,14,15,17,19,20],
    [ 2, 3, 4, 6, 7, 8,10,11,12,13,14,15,17,18,20],
    [ 1, 2, 3, 4, 5, 7, 8,10,11,13,15,16,17,18,20],
    [ 1, 2, 3, 5, 6, 7, 9,10,12,14,15,16,17,19,20],
    [ 1, 2, 4, 5, 6, 8, 9,11,13,14,15,16,17,18,20],
    [ 1, 3, 4, 5, 6, 7, 8,12,13,14,15,16,17,18,20],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,15,16,19,20],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,11,13,14,17,18,20],
    [ 2, 3, 4, 5, 6, 7, 8, 9,10,12,13,15,16,17,20],
    [ 2, 3, 4, 5, 6, 7, 8, 9,11,12,14,15,16,17,19],
    [ 2, 3, 4, 5, 6, 7, 8,10,11,12,13,14,15,18,20],
    [ 1, 2, 3, 4, 6, 7, 9,11,13,14,16,17,18,19,20],
    [ 1, 2, 3, 5, 6, 8,10,11,13,14,16,17,18,19,20],
    [ 1, 2, 4, 5, 7, 8,10,12,13,14,16,17,18,19,20],
    [ 1, 3, 4, 6, 7, 9,10,12,13,14,16,17,18,19,20],
    [ 2, 3, 5, 6, 8, 9,10,12,13,14,16,17,18,19,20],
    [ 1, 2, 3, 4, 5, 7, 9,11,12,15,16,17,18,19,20],
    [ 1, 2, 3, 4, 6, 8,10,11,12,15,16,17,18,19,20],
    [ 1, 2, 3, 5, 7, 8,10,11,12,15,16,17,18,19,20],
    [ 1, 2, 4, 6, 7, 9,10,11,12,15,16,17,18,19,20],
    [ 1, 3, 5, 6, 7, 8,10,11,12,15,16,17,18,19,20],
    [ 2, 4, 5, 6, 7, 8,10,11,12,15,16,17,18,19,20],
]

MATRIZES = {
    18: MATRIZ_18,
    19: MATRIZ_19,
    20: MATRIZ_20,
}

VALOR_JOGO = 3.00


def validar_matriz_pool(matriz: list[list[int]], pool_size: int) -> bool:
    """Valida que a matriz garante >=14 para todas as combinacoes do pool."""
    jogos_sets = [set(j) for j in matriz]
    for sorteio in itertools.combinations(range(1, pool_size + 1), DEZENAS_SORTEADAS):
        s = set(sorteio)
        if not any(len(s & j) >= 14 for j in jogos_sets):
            return False
    return True


def probabilidade_pool(pool_size: int, total: int = 25, sorteados: int = 15) -> float:
    """P(todos os 15 sorteados caem no pool de N dezenas)."""
    from math import comb
    return comb(pool_size, sorteados) / comb(total, sorteados)


def analisar_pools(dezenas_rankeadas: list[int]) -> list[dict]:
    """
    Para cada tamanho de pool em POOL_SIZES:
    - Seleciona as top-N dezenas do ranking
    - Mapeia a matriz correspondente
    - Calcula custo e probabilidade de cobertura
    Retorna lista de dicts com comparativo.
    """
    resultados = []
    for size in POOL_SIZES:
        pool = sorted(dezenas_rankeadas[:size])
        matriz = MATRIZES.get(size)

        if matriz is None:
            continue

        n_jogos = len(matriz)
        custo   = n_jogos * VALOR_JOGO
        prob    = probabilidade_pool(size)

        jogos_gerados = [
            sorted(pool[idx - 1] for idx in linha)
            for linha in matriz
        ]

        resultados.append({
            "pool_size":     size,
            "pool":          pool,
            "n_jogos":       n_jogos,
            "custo":         round(custo, 2),
            "prob_cobertura": round(prob * 100, 2),
            "jogos":         jogos_gerados,
            "matriz":        matriz,
        })

    return resultados


def melhor_pool(analise: list[dict], criterio: str = "custo_beneficio") -> dict:
    """
    Escolhe o melhor pool pelo criterio:
    - 'custo_beneficio': maior prob_cobertura / custo
    - 'cobertura': maior probabilidade (independente do custo)
    - 'economico': menor custo (pool 18)
    """
    if criterio == "cobertura":
        return max(analise, key=lambda x: x["prob_cobertura"])
    if criterio == "economico":
        return min(analise, key=lambda x: x["custo"])
    # custo_beneficio (default)
    return max(analise, key=lambda x: x["prob_cobertura"] / x["custo"])


def resumo_pools(analise: list[dict]) -> str:
    linhas = [
        "=" * 65,
        "  ANALISE COMPARATIVA DE POOLS",
        "=" * 65,
        f"  {'Pool':>5}  {'Jogos':>6}  {'Custo':>10}  {'Cobertura':>10}  {'Custo/Cob':>10}",
        "  " + "-" * 60,
    ]
    for r in analise:
        ratio = r["custo"] / r["prob_cobertura"]
        linhas.append(
            f"  {r['pool_size']:>5}  {r['n_jogos']:>6}  "
            f"R$ {r['custo']:>7.2f}  {r['prob_cobertura']:>8.2f}%  "
            f"R$ {ratio:>7.2f}"
        )
    linhas.append("=" * 65)
    linhas.append("  * Cobertura = P(todos os 15 sorteados caem no pool)")
    linhas.append("  * Custo/Cob = Reais por ponto percentual de cobertura")
    return "\n".join(linhas)
