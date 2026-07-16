"""
ml_ranking.py - Ranking das dezenas combinando ML + estatisticas classicas.

O score final e uma media ponderada entre:
  - Probabilidade do modelo ML (XGBoost/GradientBoosting)
  - Score estatistico classico (ranking.py)

Isso e mais robusto do que usar apenas um dos dois.
"""

import numpy as np
from config import TOTAL_DEZENAS, JANELAS_TENDENCIA

# Peso do score ML vs score estatistico classico
PESO_ML         = 0.60
PESO_ESTATISTICO = 0.40


def _normalizar(valores: dict) -> dict:
    mn, mx = min(valores.values()), max(valores.values())
    if mx == mn:
        return {k: 0.5 for k in valores}
    return {k: (v - mn) / (mx - mn) for k, v in valores.items()}


def ranking_ml(
    probas_ml: dict[int, float],
    rows_estatistico: list[dict],
    concursos: list[dict],
) -> list[dict]:
    """
    Combina probabilidades ML com score estatistico classico.

    Parametros
    ----------
    probas_ml         : {dezena: probabilidade} retornado por ml_model.prever_probabilidades()
    rows_estatistico  : lista retornada por ranking.ranking_completo()
    concursos         : lista de concursos (para contexto)

    Retorna
    -------
    Lista de dicts ordenada por score_final (descendente).
    """
    # Normalizar probabilidades ML para [0,1]
    ml_norm = _normalizar(probas_ml)

    # Score estatistico classico ja esta em [0,1]
    score_est = {r["dezena"]: r["score"] for r in rows_estatistico}
    est_norm  = _normalizar(score_est)

    dezenas = list(range(1, TOTAL_DEZENAS + 1))
    resultados = []

    for dezena in dezenas:
        prob_ml  = probas_ml.get(dezena, 0.0)
        ml_n     = ml_norm.get(dezena, 0.0)
        est_n    = est_norm.get(dezena, 0.0)
        score_f  = PESO_ML * ml_n + PESO_ESTATISTICO * est_n

        # Pegar metricas do row estatistico correspondente
        row_est = next((r for r in rows_estatistico if r["dezena"] == dezena), {})

        resultados.append({
            "dezena":         dezena,
            "score_final":    round(score_f, 4),
            "prob_ml":        round(prob_ml, 4),
            "score_ml_norm":  round(ml_n, 4),
            "score_est":      round(row_est.get("score", 0.0), 4),
            "score_est_norm": round(est_n, 4),
            "freq_abs":       row_est.get("freq_abs", 0),
            "freq_pct":       row_est.get("freq_pct", 0.0),
            "atraso":         row_est.get("atraso", 0),
            **{f"tend_{n}": row_est.get(f"tend_{n}", 0.0) for n in JANELAS_TENDENCIA},
        })

    # Ordenar por score final
    resultados.sort(key=lambda x: -x["score_final"])

    # Adicionar posicao
    for i, r in enumerate(resultados, 1):
        r["posicao"] = i

    return resultados


def top18_ml(
    probas_ml: dict[int, float],
    rows_estatistico: list[dict],
    concursos: list[dict],
) -> list[int]:
    """Retorna as 18 dezenas de maior score ML+estatistico, ordenadas."""
    rows = ranking_ml(probas_ml, rows_estatistico, concursos)
    return sorted(r["dezena"] for r in rows[:18])


def comparar_rankings(
    rows_ml: list[dict],
    rows_classico: list[dict],
) -> list[dict]:
    """
    Compara posicao de cada dezena no ranking ML vs classico.
    Util para ver quais dezenas o modelo ML 'discorda' do estatistico.
    """
    pos_ml  = {r["dezena"]: r["posicao"] for r in rows_ml}
    pos_cls = {r["dezena"]: i + 1 for i, r in enumerate(rows_classico)}

    resultado = []
    for dezena in range(1, TOTAL_DEZENAS + 1):
        pm = pos_ml.get(dezena, 0)
        pc = pos_cls.get(dezena, 0)
        resultado.append({
            "dezena":       dezena,
            "pos_ml":       pm,
            "pos_classico": pc,
            "delta":        pc - pm,  # positivo = ML rankeou mais alto
            "no_pool_ml":   pm <= 18,
            "no_pool_cls":  pc <= 18,
            "consenso":     pm <= 18 and pc <= 18,
            "divergencia":  (pm <= 18) != (pc <= 18),
        })

    return sorted(resultado, key=lambda x: x["dezena"])


def resumo_comparacao(comp: list[dict]) -> str:
    consenso    = sum(1 for r in comp if r["consenso"])
    divergencia = sum(1 for r in comp if r["divergencia"])
    so_ml  = sum(1 for r in comp if r["no_pool_ml"] and not r["no_pool_cls"])
    so_cls = sum(1 for r in comp if r["no_pool_cls"] and not r["no_pool_ml"])

    linhas = [
        "=" * 55,
        "  COMPARATIVO: ML vs RANKING CLASSICO",
        "=" * 55,
        f"  Dezenas em consenso (ambos top-18): {consenso}",
        f"  Divergencias totais               : {divergencia}",
        f"    So no pool ML                   : {so_ml}",
        f"    So no pool classico             : {so_cls}",
        "",
        "  Dezenas com maior discordancia (delta pos):",
    ]
    top_div = sorted(comp, key=lambda x: -abs(x["delta"]))[:8]
    for r in top_div:
        sinal = "+" if r["delta"] > 0 else ""
        tag = ""
        if r["no_pool_ml"] and not r["no_pool_cls"]:
            tag = " <- ML favorece"
        elif r["no_pool_cls"] and not r["no_pool_ml"]:
            tag = " <- Classico favorece"
        linhas.append(
            f"    Dezena {r['dezena']:02d}: ML=#{r['pos_ml']:<3} "
            f"Classico=#{r['pos_classico']:<3} delta={sinal}{r['delta']}{tag}"
        )
    linhas.append("=" * 55)
    return "\n".join(linhas)
