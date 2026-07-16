"""
validator.py - Validacao matematica exaustiva do fechamento.
Testa todas as C(18,15) = 816 combinacoes possiveis.
"""

import itertools
from config import INDICES_FECHAMENTO


def validar_matriz(matriz=None):
    if matriz is None:
        matriz = INDICES_FECHAMENTO
    jogos_sets = [set(j) for j in matriz]
    todos = list(itertools.combinations(range(1, 19), 15))
    falhos, min_acertos = [], 15
    for sorteio in todos:
        s = set(sorteio)
        melhor = max(len(s & j) for j in jogos_sets)
        min_acertos = min(min_acertos, melhor)
        if melhor < 14:
            falhos.append(sorteio)
    return {
        "valida":             len(falhos) == 0,
        "total_cenarios":     len(todos),
        "cenarios_cobertos":  len(todos) - len(falhos),
        "cenarios_falhos":    falhos,
        "min_acertos":        min_acertos,
    }


def resumo_validacao(r):
    linhas = [
        "=" * 55,
        "  VALIDACAO MATEMATICA - FECHAMENTO 18-15-14",
        "=" * 55,
        f"  Cenarios testados  : {r['total_cenarios']}",
        f"  Cenarios cobertos  : {r['cenarios_cobertos']}",
        f"  Minimo de acertos  : {r['min_acertos']}",
        f"  Garantia valida    : {'SIM' if r['valida'] else 'NAO'}",
        "=" * 55,
    ]
    return "\n".join(linhas)
