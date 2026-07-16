"""
ml_backtest.py - Backtest walk-forward comparativo: ML vs ranking classico.

Metodologia rigorosa:
  Para cada concurso de teste (a partir do indice min_treino):
    1. Treina modelo APENAS com dados anteriores ao concurso
    2. Gera ranking ML e ranking classico com os mesmos dados
    3. Seleciona pool de 18 para cada abordagem
    4. Verifica quantas dezenas do sorteio real estao em cada pool
    5. Simula os 24 jogos do fechamento e registra melhor resultado

Nao ha data leakage — cada predicao usa SOMENTE o passado.
"""

import time
import numpy as np
from config import DEZENAS_SORTEADAS
from ml_features import extrair_features, construir_dataset
from ml_model import _criar_modelo
from ml_ranking import ranking_ml, top18_ml
import statistics as stats_mod
import ranking as ranking_mod
from fechamento import gerar_jogos


def _acertos(jogo: list[int], sorteio: list[int]) -> int:
    return len(set(jogo) & set(sorteio))


def _melhor_resultado(jogos: list[list[int]], sorteio: list[int]) -> int:
    return max(_acertos(j, sorteio) for j in jogos)


def backtest_comparativo(
    concursos: list[dict],
    min_treino: int = 80,
    janela_retrain: int = 20,
    verbose: bool = True,
) -> dict:
    """
    Executa backtest walk-forward comparando ML vs classico.

    Parametros
    ----------
    concursos      : lista completa de concursos ordenados
    min_treino     : minimo de concursos para primeiro treinamento
    janela_retrain : re-treina o modelo a cada N concursos

    Retorna dict com resultados detalhados dos dois metodos.
    """
    if len(concursos) < min_treino + 10:
        return {"erro": f"Historico insuficiente (min {min_treino+10} concursos)."}

    resultados_ml  = []
    resultados_cls = []
    modelo = None
    ultimo_treino = -999

    total_teste = len(concursos) - min_treino
    if verbose:
        print(f"  Backtest walk-forward: {total_teste} concursos de teste")
        print(f"  Re-treino a cada {janela_retrain} concursos\n")

    for idx in range(min_treino, len(concursos)):
        concursos_treino = concursos[:idx]
        cs_teste = concursos[idx]
        sorteio  = cs_teste["dezenas"]

        # Re-treinar modelo se necessario
        if idx - ultimo_treino >= janela_retrain or modelo is None:
            if verbose:
                prog = (idx - min_treino) / total_teste * 100
                print(f"  [{prog:5.1f}%] Concurso #{cs_teste['concurso']} "
                      f"— treinando com {idx} concursos...")
            X, y, _ = construir_dataset(concursos_treino, min_historico=30)
            modelo = _criar_modelo()
            modelo.fit(X, y)
            ultimo_treino = idx

        # Estatisticas e scores classicos
        dados = stats_mod.consolidar(concursos_treino)
        rows_cls = ranking_mod.ranking_completo(dados, len(concursos_treino), concursos_treino)

        # Probabilidades ML
        historico = [c["dezenas"] for c in concursos_treino]
        X_pred = np.array(
            [extrair_features(historico, d) for d in range(1, 26)],
            dtype=np.float32,
        )
        probas_ml = {d: float(modelo.predict_proba(X_pred)[:, 1][d-1])
                     for d in range(1, 26)}

        # Pools de 18 dezenas
        pool_ml  = top18_ml(probas_ml, rows_cls, concursos_treino)
        pool_cls = sorted([r["dezena"] for r in rows_cls[:18]])

        # Coberturas (quantas do sorteio caem no pool)
        hits_ml  = len(set(sorteio) & set(pool_ml))
        hits_cls = len(set(sorteio) & set(pool_cls))
        cobertura_ml  = hits_ml == DEZENAS_SORTEADAS
        cobertura_cls = hits_cls == DEZENAS_SORTEADAS

        # Melhor resultado dos 24 jogos
        jogos_ml  = gerar_jogos(pool_ml)
        jogos_cls = gerar_jogos(pool_cls)
        melhor_ml  = _melhor_resultado(jogos_ml, sorteio)
        melhor_cls = _melhor_resultado(jogos_cls, sorteio)

        resultados_ml.append({
            "concurso":    cs_teste["concurso"],
            "data":        cs_teste["data"],
            "pool":        pool_ml,
            "pool_hits":   hits_ml,
            "cobertura":   cobertura_ml,
            "melhor_pts":  melhor_ml,
        })
        resultados_cls.append({
            "concurso":    cs_teste["concurso"],
            "data":        cs_teste["data"],
            "pool":        pool_cls,
            "pool_hits":   hits_cls,
            "cobertura":   cobertura_cls,
            "melhor_pts":  melhor_cls,
        })

    # Agregar resultados
    def agregar(resultados: list[dict]) -> dict:
        n = len(resultados)
        coberturas = sum(1 for r in resultados if r["cobertura"])
        hits_media = np.mean([r["pool_hits"] for r in resultados])
        faixas = {k: 0 for k in [15, 14, 13, 12, 11, "abaixo_11"]}
        for r in resultados:
            pts = r["melhor_pts"]
            chave = pts if pts >= 11 else "abaixo_11"
            faixas[chave] = faixas.get(chave, 0) + 1
        return {
            "total": n,
            "coberturas": coberturas,
            "pct_cobertura": round(coberturas / n * 100, 2) if n else 0,
            "hits_media": round(float(hits_media), 2),
            "faixas": faixas,
            "detalhes": resultados,
        }

    return {
        "total_concursos": len(concursos) - min_treino,
        "min_treino":      min_treino,
        "ml":  agregar(resultados_ml),
        "cls": agregar(resultados_cls),
    }


def resumo_backtest_comparativo(resultado: dict) -> str:
    if "erro" in resultado:
        return f"  AVISO: {resultado['erro']}"

    ml  = resultado["ml"]
    cls = resultado["cls"]
    n   = resultado["total_concursos"]

    def linha_faixa(label, pts):
        vm = ml["faixas"].get(pts, 0)
        vc = cls["faixas"].get(pts, 0)
        pm = round(vm / n * 100, 1) if n else 0
        pc = round(vc / n * 100, 1) if n else 0
        diff = vm - vc
        sinal = f"ML+{diff}" if diff > 0 else (f"CLS+{abs(diff)}" if diff < 0 else "=")
        return f"  {label:<12} ML={vm:3d}({pm:.1f}%)  CLS={vc:3d}({pc:.1f}%)  [{sinal}]"

    linhas = [
        "=" * 62,
        "  BACKTEST COMPARATIVO: ML vs RANKING CLASSICO",
        f"  {n} concursos testados (walk-forward, sem data leakage)",
        "=" * 62,
        f"  {'':12} {'ML':>14}   {'Classico':>14}   {'Diferenca':>10}",
        f"  {'Cobertura':<12} {ml['pct_cobertura']:>12.2f}%   {cls['pct_cobertura']:>12.2f}%"
        f"   [{'+' if ml['pct_cobertura'] >= cls['pct_cobertura'] else ''}"
        f"{ml['pct_cobertura']-cls['pct_cobertura']:.2f}%]",
        f"  {'Hits media':<12} {ml['hits_media']:>13.2f}   {cls['hits_media']:>13.2f}"
        f"   [{'+' if ml['hits_media'] >= cls['hits_media'] else ''}"
        f"{ml['hits_media']-cls['hits_media']:.2f}]",
        "",
        "  Distribuicao de resultados (melhor jogo por concurso):",
        linha_faixa("15 pts", 15),
        linha_faixa("14 pts", 14),
        linha_faixa("13 pts", 13),
        linha_faixa("12 pts", 12),
        linha_faixa("11 pts", 11),
        linha_faixa("< 11", "abaixo_11"),
        "=" * 62,
    ]

    # Veredicto
    vantagem_ml = ml["pct_cobertura"] - cls["pct_cobertura"]
    if abs(vantagem_ml) < 1.0:
        veredicto = "  Resultado: EMPATE (diferenca < 1%)"
    elif vantagem_ml > 0:
        veredicto = f"  Resultado: ML SUPERIOR em {vantagem_ml:.2f}% de cobertura"
    else:
        veredicto = f"  Resultado: CLASSICO SUPERIOR em {abs(vantagem_ml):.2f}% de cobertura"
    linhas.append(veredicto)
    linhas.append("=" * 62)

    return "\n".join(linhas)
