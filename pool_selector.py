"""
pool_selector.py - Selecao inteligente do pool de 18 dezenas.

Estrategia:
  1. Identifica as dezenas mais frequentes nos ULTIMOS N concursos (base)
  2. Forca a inclusao de 2-3 dezenas muito atrasadas (ciclo de retorno)
  3. Valida o pool resultante contra checklist de qualidade
  4. Permite ajuste fino manual antes de gerar os jogos

Por que forcar atrasadas?
  Dezenas com atraso muito acima do ciclo medio estao "devendo" aparicoes
  do ponto de vista historico. Nao e garantia matematica, mas e o padrao
  mais consistente observado nos dados reais da Lotofacil.
"""

import numpy as np
from collections import Counter
from config import (
    TOTAL_DEZENAS, DEZENAS_SORTEADAS, GRID,
    MOLDURA, CENTRO, FIBONACCI, PRIMOS,
)


# -- Parametros configuráveis -------------------------------------------------

JANELA_RECENTE    = 20    # concursos recentes para base do pool
N_ATRASADAS       = 2     # quantas dezenas atrasadas forcar no pool
ATRASO_MIN_FORCADO = 8    # atraso minimo para ser considerada "forcada"
SOBREPOSICAO_ALVO = (9, 11)   # dezenas do ultimo jogo que devem estar no pool


# -- Helpers ------------------------------------------------------------------

def _freq_recente(historico: list[list[int]], n: int) -> dict[int, int]:
    """Contagem de aparicoes nos ultimos N concursos."""
    janela = historico[-n:] if len(historico) >= n else historico
    c = Counter()
    for s in janela:
        c.update(s)
    return {d: c.get(d, 0) for d in range(1, TOTAL_DEZENAS + 1)}


def _atrasos(historico: list[list[int]]) -> dict[int, int]:
    """Atraso de cada dezena (concursos desde a ultima aparicao)."""
    res = {}
    for d in range(1, TOTAL_DEZENAS + 1):
        for i, s in enumerate(reversed(historico)):
            if d in s:
                res[d] = i
                break
        else:
            res[d] = len(historico)
    return res


def _ciclo_medio(historico: list[list[int]], dezena: int) -> float:
    """Intervalo medio de aparicao da dezena."""
    ap = [i for i, s in enumerate(historico) if dezena in s]
    if len(ap) < 2:
        return TOTAL_DEZENAS / DEZENAS_SORTEADAS
    return float(np.mean([ap[j] - ap[j-1] for j in range(1, len(ap))]))


# -- Selecao principal --------------------------------------------------------

def selecionar_pool(
    concursos: list[dict],
    tamanho: int = 18,
    n_atrasadas: int = N_ATRASADAS,
    janela_recente: int = JANELA_RECENTE,
    atraso_min: int = ATRASO_MIN_FORCADO,
) -> dict:
    """
    Seleciona o pool de dezenas usando a estrategia hibrida:
      - Base: dezenas mais frequentes nos ultimos JANELA concursos
      - Forcado: 2-3 dezenas muito atrasadas (acima de atraso_min)

    Retorna dict com pool, dezenas base, dezenas forcadas e metricas.
    """
    historico = [c["dezenas"] for c in concursos]
    if not historico:
        return {"pool": list(range(1, tamanho + 1)), "base": [], "forcadas": [],
                "atrasos": {}, "freq_recente": {}}

    freq_rec = _freq_recente(historico, janela_recente)
    atr = _atrasos(historico)
    ciclos = {d: _ciclo_medio(historico, d) for d in range(1, TOTAL_DEZENAS + 1)}

    # Candidatas atrasadas: atraso >= atraso_min E acima do ciclo medio
    candidatas_atrasadas = sorted(
        [d for d in range(1, TOTAL_DEZENAS + 1)
         if atr[d] >= atraso_min and atr[d] >= ciclos[d] * 1.2],
        key=lambda d: -atr[d]  # mais atrasada primeiro
    )

    # Selecionar as N mais atrasadas para forcar
    forcadas = candidatas_atrasadas[:n_atrasadas]

    # Base: top dezenas por frequencia recente, excluindo as forcadas
    base_candidatas = sorted(
        [d for d in range(1, TOTAL_DEZENAS + 1) if d not in forcadas],
        key=lambda d: (-freq_rec[d], d)
    )
    n_base = tamanho - len(forcadas)
    base = base_candidatas[:n_base]

    pool = sorted(base + forcadas)

    return {
        "pool":          pool,
        "base":          sorted(base),
        "forcadas":      sorted(forcadas),
        "atrasos":       atr,
        "ciclos":        {d: round(ciclos[d], 1) for d in range(1, TOTAL_DEZENAS + 1)},
        "freq_recente":  freq_rec,
        "janela_usada":  janela_recente,
        "n_atrasadas":   len(forcadas),
    }


# -- Validador de qualidade do pool -------------------------------------------

def validar_pool(
    pool: list[int],
    historico: list[list[int]],
    sobreposicao_alvo: tuple = SOBREPOSICAO_ALVO,
) -> dict:
    """
    Valida o pool contra criterios de qualidade estatistica.

    Criterios:
      - Pares/impares: entre 7-11 pares dentro do pool de 18
      - Sobreposicao com ultimo jogo: 9-11 dezenas em comum
      - Cobertura de linhas (1-5): todas as linhas cobertas
      - Cobertura de colunas (1-5): todas as colunas cobertas
      - Moldura vs centro: pelo menos 6 de cada
      - Primos: pelo menos 3 primos no pool
      - Fibonacci: pelo menos 2 fibonacci no pool

    Retorna dict com resultado de cada criterio e score geral (0-100).
    """
    pool_set = set(pool)

    # 1. Paridade
    pares_pool = [d for d in pool if d % 2 == 0]
    impares_pool = [d for d in pool if d % 2 != 0]
    par_ok = 7 <= len(pares_pool) <= 11

    # 2. Sobreposicao com ultimo jogo
    ultimo = set(historico[-1]) if historico else set()
    sobreposicao = len(pool_set & ultimo)
    sob_min, sob_max = sobreposicao_alvo
    sob_ok = sob_min <= sobreposicao <= sob_max

    # 3. Cobertura de linhas
    linhas = {r: [] for r in range(1, 6)}
    colunas = {c: [] for c in range(1, 6)}
    for d in pool:
        l, c = GRID[d]
        linhas[l].append(d)
        colunas[c].append(d)
    linhas_cobertas = sum(1 for v in linhas.values() if len(v) >= 1)
    colunas_cobertas = sum(1 for v in colunas.values() if len(v) >= 1)
    linhas_ok = linhas_cobertas == 5
    colunas_ok = colunas_cobertas == 5

    # 4. Moldura e centro
    n_moldura = len(pool_set & MOLDURA)
    n_centro  = len(pool_set & CENTRO)
    moldura_ok = n_moldura >= 6 and n_centro >= 3

    # 5. Primos e Fibonacci
    n_primos = len(pool_set & PRIMOS)
    n_fib    = len(pool_set & FIBONACCI)
    primos_ok = n_primos >= 3
    fib_ok    = n_fib >= 2

    # Score: cada criterio vale pontos
    criterios = {
        "paridade": {
            "ok": par_ok,
            "detalhe": f"{len(pares_pool)} pares / {len(impares_pool)} impares (ideal: 7-11 pares)",
            "peso": 20,
        },
        "sobreposicao_ultimo": {
            "ok": sob_ok,
            "detalhe": f"{sobreposicao} dezenas em comum com ultimo sorteio (ideal: {sob_min}-{sob_max})",
            "peso": 25,
        },
        "linhas": {
            "ok": linhas_ok,
            "detalhe": f"{linhas_cobertas}/5 linhas cobertas | " +
                       " ".join(f"L{r}:{len(v)}" for r, v in linhas.items()),
            "peso": 20,
        },
        "colunas": {
            "ok": colunas_ok,
            "detalhe": f"{colunas_cobertas}/5 colunas cobertas | " +
                       " ".join(f"C{c}:{len(v)}" for c, v in colunas.items()),
            "peso": 15,
        },
        "moldura_centro": {
            "ok": moldura_ok,
            "detalhe": f"{n_moldura} moldura / {n_centro} centro (ideal: >=6 moldura, >=3 centro)",
            "peso": 10,
        },
        "primos": {
            "ok": primos_ok,
            "detalhe": f"{n_primos} primos no pool (ideal: >=3)",
            "peso": 5,
        },
        "fibonacci": {
            "ok": fib_ok,
            "detalhe": f"{n_fib} fibonacci no pool (ideal: >=2)",
            "peso": 5,
        },
    }

    score = sum(c["peso"] for c in criterios.values() if c["ok"])

    return {
        "pool":          pool,
        "score_qualidade": score,
        "criterios":     criterios,
        "aprovado":      score >= 70,
        "sobreposicao":  sobreposicao,
        "pares_pool":    len(pares_pool),
        "impares_pool":  len(impares_pool),
        "linhas":        {r: v for r, v in linhas.items()},
        "colunas":       {c: v for c, v in colunas.items()},
        "n_moldura":     n_moldura,
        "n_centro":      n_centro,
        "n_primos":      n_primos,
        "n_fibonacci":   n_fib,
    }


# -- Ajuste fino: substituicao de dezenas no pool -----------------------------

def ajustar_pool(
    pool: list[int],
    adicionar: list[int] = None,
    remover: list[int] = None,
) -> list[int]:
    """
    Permite ajuste manual do pool: adiciona e/ou remove dezenas.
    Mantém o tamanho original compensando automaticamente.
    """
    pool_set = set(pool)
    adicionar = adicionar or []
    remover = remover or []

    for d in remover:
        pool_set.discard(d)
    for d in adicionar:
        if 1 <= d <= 25:
            pool_set.add(d)

    return sorted(pool_set)


# -- Relatorio ----------------------------------------------------------------

def relatorio_selecao(selecao: dict, validacao: dict) -> str:
    pool     = selecao["pool"]
    base     = selecao["base"]
    forcadas = selecao["forcadas"]
    atr      = selecao["atrasos"]
    freq     = selecao["freq_recente"]
    jan      = selecao["janela_usada"]

    linhas = [
        "=" * 62,
        f"  SELECAO DO POOL (Top-{jan} recentes + {len(forcadas)} atrasadas)",
        "=" * 62,
        "",
        f"  Base (frequencia ultimos {jan} concursos):",
        "  " + "  ".join(f"{d:02d}({freq[d]})" for d in base),
    ]

    if forcadas:
        linhas += [
            "",
            f"  Forcadas por atraso elevado:",
        ]
        for d in forcadas:
            ciclo = selecao["ciclos"].get(d, 0)
            linhas.append(
                f"    Dezena {d:02d}: atraso={atr[d]} concursos "
                f"(ciclo medio={ciclo:.1f}, pressao={atr[d]/max(ciclo,1):.2f}x)"
            )

    linhas += [
        "",
        f"  Pool final ({len(pool)} dezenas):",
        "  " + "  ".join(f"{d:02d}" for d in pool),
        "",
        f"  Score de qualidade: {validacao['score_qualidade']}/100  "
        f"({'APROVADO' if validacao['aprovado'] else 'ATENCAO'})",
        "",
        "  Checklist de qualidade:",
    ]

    for nome, crit in validacao["criterios"].items():
        status = "OK" if crit["ok"] else "--"
        linhas.append(f"    [{status}] {nome:<25} {crit['detalhe']}")

    linhas.append("=" * 62)
    return "\n".join(linhas)
