"""
hibrido_perfis.py - Perfis de aposta: Conservador, Equilibrado, Agressivo.

Cada perfil ajusta os pesos do motor hibrido para privilegiar
diferentes estrategias:

  CONSERVADOR : prioriza padroes historicos solidos (frequencia longa)
  EQUILIBRADO : balanca estatistica e tendencias recentes
  AGRESSIVO   : da mais peso ao ML e tendencias de curto prazo
"""

import copy
from hibrido_pesos import _normalizar, PESOS_INICIAIS

# -- Definicao dos perfis -----------------------------------------------------

PERFIS = {
    "conservador": {
        "nome":      "Conservador",
        "descricao": "Prioriza padroes historicos solidos. Menor risco, maior consistencia.",
        "icone":     "C",
        "modificadores": {
            "freq_100":    +0.10,
            "freq_50":     +0.08,
            "freq_20":     +0.02,
            "freq_10":     -0.05,
            "tendencia":   -0.05,
            "atraso":      +0.02,
            "repeticao":   +0.01,
            "linhas_cols": +0.01,
            "paridade":    0.00,
            "moldura":     0.00,
            "soma_ideal":  +0.01,
            "ml":          -0.03,
        },
    },
    "equilibrado": {
        "nome":      "Equilibrado",
        "descricao": "Balanca estatistica classica e tendencias recentes.",
        "icone":     "E",
        "modificadores": {k: 0.0 for k in PESOS_INICIAIS},  # usa pesos sem alteracao
    },
    "agressivo": {
        "nome":      "Agressivo",
        "descricao": "Prioriza ML e tendencias recentes. Maior variacao, mais dinamico.",
        "icone":     "A",
        "modificadores": {
            "freq_100":    -0.08,
            "freq_50":     -0.05,
            "freq_20":     +0.02,
            "freq_10":     +0.05,
            "tendencia":   +0.08,
            "atraso":      -0.02,
            "repeticao":   -0.02,
            "linhas_cols": 0.00,
            "paridade":    +0.01,
            "moldura":     0.00,
            "soma_ideal":  -0.01,
            "ml":          +0.10,
        },
    },
}

PERFIS_VALIDOS = list(PERFIS.keys())


def pesos_perfil(perfil: str, pesos_base: dict) -> dict:
    """
    Aplica os modificadores do perfil sobre os pesos base (otimizados ou iniciais).

    Parametros
    ----------
    perfil      : "conservador" | "equilibrado" | "agressivo"
    pesos_base  : pesos carregados de hibrido_pesos.carregar_pesos()

    Retorna
    -------
    dict com pesos ajustados e normalizados
    """
    if perfil not in PERFIS:
        raise ValueError(f"Perfil invalido: '{perfil}'. Use: {PERFIS_VALIDOS}")

    mods = PERFIS[perfil]["modificadores"]
    pesos_ajustados = {}
    for k, v in pesos_base.items():
        mod = mods.get(k, 0.0)
        # Clamp para nao ficar negativo
        pesos_ajustados[k] = max(0.005, v + mod)

    return _normalizar(pesos_ajustados)


def descrever_perfil(perfil: str, pesos_base: dict) -> str:
    """Exibe descricao detalhada do perfil e seus pesos efetivos."""
    info = PERFIS[perfil]
    pesos = pesos_perfil(perfil, pesos_base)

    linhas = [
        "=" * 55,
        f"  PERFIL: [{info['icone']}] {info['nome'].upper()}",
        f"  {info['descricao']}",
        "=" * 55,
        f"  {'Criterio':<22} {'Peso':>8}  {'Barra'}",
        "  " + "-" * 50,
    ]
    for k, v in sorted(pesos.items(), key=lambda x: -x[1]):
        bar = "#" * int(v * 60)
        linhas.append(f"  {k:<22} {v*100:>6.1f}%  {bar}")
    linhas.append("=" * 55)
    return "\n".join(linhas)


def comparar_perfis(pesos_base: dict) -> str:
    """Compara os tres perfis lado a lado."""
    p = {nome: pesos_perfil(nome, pesos_base) for nome in PERFIS_VALIDOS}
    chaves = list(PESOS_INICIAIS.keys())

    linhas = [
        "=" * 65,
        "  COMPARATIVO DE PERFIS",
        f"  {'Criterio':<22}  {'Conserv':>8}  {'Equilib':>8}  {'Agressiv':>8}",
        "  " + "-" * 58,
    ]
    for k in chaves:
        pc = p["conservador"][k] * 100
        pe = p["equilibrado"][k] * 100
        pa = p["agressivo"][k] * 100
        # destacar maior
        maior = max(pc, pe, pa)
        def fmt(v): return f"{v:>6.1f}%{'*' if abs(v-maior)<0.01 else ' '}"
        linhas.append(f"  {k:<22}  {fmt(pc)}   {fmt(pe)}   {fmt(pa)}")
    linhas.append("=" * 65)
    linhas.append("  * = maior peso neste criterio")
    return "\n".join(linhas)


def top18_por_perfil(
    scores_fn,
    concursos_historico: list,
    pesos_base: dict,
    ml_probas: dict = None,
) -> dict[str, list[int]]:
    """
    Gera o pool de 18 dezenas para cada perfil.

    Parametros
    ----------
    scores_fn           : hibrido_score.calcular_scores
    concursos_historico : lista de concursos anteriores
    pesos_base          : pesos carregados/otimizados
    ml_probas           : probabilidades ML (opcional)

    Retorna
    -------
    {"conservador": [d1,...,d18], "equilibrado": [...], "agressivo": [...]}
    """
    resultado = {}
    for perfil in PERFIS_VALIDOS:
        pesos = pesos_perfil(perfil, pesos_base)
        scores = scores_fn(concursos_historico, pesos, ml_probas)
        top18 = sorted(
            sorted(scores, key=lambda d: -scores[d])[:18]
        )
        resultado[perfil] = top18
    return resultado


def resumo_perfis(pools_por_perfil: dict[str, list[int]]) -> str:
    """Exibe as 18 dezenas de cada perfil lado a lado."""
    linhas = [
        "=" * 62,
        "  POOLS DE 18 DEZENAS POR PERFIL",
        "=" * 62,
    ]
    todos = set()
    for pool in pools_por_perfil.values():
        todos.update(pool)

    for perfil, pool in pools_por_perfil.items():
        info = PERFIS[perfil]
        nums = "  ".join(f"{d:02d}" for d in pool)
        linhas.append(f"  [{info['icone']}] {info['nome']:<12} {nums}")

    # Dezenas em consenso (nos 3 perfis)
    consenso = set(pools_por_perfil.get("conservador", [])) \
             & set(pools_por_perfil.get("equilibrado", [])) \
             & set(pools_por_perfil.get("agressivo", []))

    if consenso:
        nums_c = "  ".join(f"{d:02d}" for d in sorted(consenso))
        linhas.append(f"\n  Consenso ({len(consenso)}/18): {nums_c}")

    linhas.append("=" * 62)
    return "\n".join(linhas)
