"""
modo_especialista.py - Modo Especialista do LotofacilPro v4.

Quando ativado, o sistema:
  1. Usa os ultimos 500 concursos (ou tudo que tiver)
  2. Executa milhares de backtests testando diferentes combinacoes de pesos
  3. Testa cada perfil (conservador/equilibrado/agressivo) em cada janela
  4. Pede avaliacao da IA com o relatorio completo
  5. Escolhe automaticamente a estrategia com melhor desempenho historico
  6. Retorna o pool e os pesos otimizados para o fechamento final

Diferenca para o modo normal:
  - Modo normal: usa os pesos atuais (otimizados pelo Hill Climbing)
  - Modo especialista: testa exaustivamente e escolhe o melhor historico real
"""

import time
import json
import random
import itertools
import numpy as np
from pathlib import Path
from config import BASE_DIR, DEZENAS_SORTEADAS

ESPECIALISTA_LOG = BASE_DIR / "cache" / "especialista_log.json"


# -- Configuracoes do modo especialista ----------------------------------------

JANELAS_TESTE    = [20, 30, 50, 100]   # ultimos N concursos como janela de treino
N_VARIANTES      = 40                  # quantas variantes de pesos testar
MAX_CONCURSOS    = 500                 # usar no maximo os ultimos 500 concursos


# -- Gerador de variantes de pesos ---------------------------------------------

def _gerar_variantes(n: int = N_VARIANTES) -> list[dict]:
    """Gera N combinacoes diferentes de pesos para testar."""
    criterios = [
        "freq_100","freq_50","freq_20","freq_10",
        "tendencia","atraso","repeticao","linhas_cols",
        "paridade","moldura","soma_ideal","ml"
    ]
    variantes = []

    # Variante 1: pesos uniformes
    uniformes = {k: 1/len(criterios) for k in criterios}
    variantes.append(("uniforme", uniformes))

    # Variante 2: mais peso para frequencias recentes
    freq_pesada = {k: 0.01 for k in criterios}
    freq_pesada.update({"freq_10": 0.35, "freq_20": 0.25, "tendencia": 0.20,
                         "atraso": 0.10, "freq_50": 0.09})
    variantes.append(("freq_recente", _norm(freq_pesada)))

    # Variante 3: mais peso para tendencia e atraso
    tend_pesada = {k: 0.02 for k in criterios}
    tend_pesada.update({"tendencia": 0.30, "atraso": 0.25, "freq_10": 0.20,
                         "freq_20": 0.13, "repeticao": 0.08})
    variantes.append(("tendencia_atraso", _norm(tend_pesada)))

    # Variante 4: conservadora (historia longa)
    conservadora = {k: 0.02 for k in criterios}
    conservadora.update({"freq_100": 0.30, "freq_50": 0.25, "freq_20": 0.20,
                          "atraso": 0.10, "freq_10": 0.08})
    variantes.append(("conservadora", _norm(conservadora)))

    # Variante 5: agressiva (curto prazo)
    agressiva = {k: 0.02 for k in criterios}
    agressiva.update({"freq_10": 0.40, "tendencia": 0.30, "atraso": 0.15,
                       "freq_20": 0.08, "ml": 0.05})
    variantes.append(("agressiva", _norm(agressiva)))

    # Restantes: variantes aleatorias com seed fixo para reproducibilidade
    rng = random.Random(42)
    for i in range(n - len(variantes)):
        raw = {k: rng.uniform(0.01, 0.40) for k in criterios}
        variantes.append((f"aleatoria_{i}", _norm(raw)))

    return variantes[:n]


def _norm(pesos: dict) -> dict:
    total = sum(pesos.values())
    return {k: v / total for k, v in pesos.items()} if total > 0 else pesos


# -- Avaliacao de uma variante de pesos ----------------------------------------

def _avaliar_variante(
    concursos: list[dict],
    pesos: dict,
    janela: int,
    n_teste: int = 30,
) -> dict:
    """
    Avalia um conjunto de pesos nos ultimos n_teste concursos usando
    janela concursos como historico de treino. Sem data leakage.
    """
    from hibrido_score import calcular_scores
    import statistics as stats_mod

    total = len(concursos)
    inicio_teste = max(janela, total - n_teste)

    hits = []
    coberturas = 0

    for idx in range(inicio_teste, total):
        historico = concursos[max(0, idx-janela):idx]
        sorteio = set(concursos[idx]["dezenas"])

        dados = stats_mod.consolidar(historico)
        scores = calcular_scores(historico, pesos, None)
        pool18 = set(sorted(scores, key=lambda d: -scores[d])[:18])

        n_hits = len(sorteio & pool18)
        hits.append(n_hits)
        if n_hits == DEZENAS_SORTEADAS:
            coberturas += 1

    n = len(hits)
    return {
        "hits_media": round(float(np.mean(hits)), 3) if hits else 0,
        "hits_std":   round(float(np.std(hits)), 3) if hits else 0,
        "cobertura_pct": round(coberturas / n * 100, 1) if n else 0,
        "n_testados": n,
    }


# -- Pipeline do modo especialista ---------------------------------------------

def executar_modo_especialista(
    concursos: list[dict],
    verbose: bool = True,
    callback_progresso=None,
) -> dict:
    """
    Executa o modo especialista completo.

    Retorna dict com:
      - melhor_variante: nome da estrategia vencedora
      - melhores_pesos: dict de pesos otimizados
      - pool_recomendado: 18 dezenas
      - relatorio: texto completo para enviar a IA
      - resultados: todos os resultados dos testes
    """
    def prog(msg, pct):
        if verbose: print(f"  [Especialista] {msg}")
        if callback_progresso: callback_progresso(msg, pct)

    # Limitar a MAX_CONCURSOS
    if len(concursos) > MAX_CONCURSOS:
        concursos = concursos[-MAX_CONCURSOS:]

    prog(f"Iniciando com {len(concursos)} concursos...", 2)

    variantes = _gerar_variantes(N_VARIANTES)
    prog(f"{len(variantes)} variantes de pesos a testar", 5)

    resultados = []
    total_testes = len(variantes) * len(JANELAS_TESTE)
    teste_atual = 0

    for nome, pesos in variantes:
        resultados_janela = []
        for janela in JANELAS_TESTE:
            teste_atual += 1
            pct = int(5 + 70 * teste_atual / total_testes)
            prog(f"Testando '{nome}' | janela={janela}", pct)

            resultado = _avaliar_variante(concursos, pesos, janela)
            resultados_janela.append({
                "janela": janela,
                **resultado,
            })

        # Score consolidado: media ponderada entre janelas
        score_medio = np.mean([r["hits_media"] for r in resultados_janela])
        cobertura_media = np.mean([r["cobertura_pct"] for r in resultados_janela])

        resultados.append({
            "nome":            nome,
            "pesos":           pesos,
            "score_medio":     round(float(score_medio), 3),
            "cobertura_media": round(float(cobertura_media), 1),
            "por_janela":      resultados_janela,
        })

    # Ordenar por score (hits media)
    resultados.sort(key=lambda x: (-x["score_medio"], -x["cobertura_media"]))
    prog("Rankeando estrategias...", 78)

    melhor = resultados[0]
    melhores_pesos = melhor["pesos"]

    # Gerar pool com os melhores pesos
    prog("Gerando pool com melhores pesos...", 82)
    from hibrido_score import calcular_scores
    from hibrido_tendencia import classificar_todas
    scores = calcular_scores(concursos, melhores_pesos, None)
    pool = sorted(sorted(scores, key=lambda d: -scores[d])[:18])

    # Montar relatorio completo para a IA
    prog("Montando relatorio completo...", 90)
    relatorio = _montar_relatorio_especialista(
        concursos, resultados, melhor, pool
    )

    # Salvar log
    entrada = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_concursos": len(concursos),
        "n_variantes": len(variantes),
        "melhor_estrategia": melhor["nome"],
        "melhor_score": melhor["score_medio"],
        "melhor_cobertura": melhor["cobertura_media"],
        "pool": pool,
    }
    log = []
    if ESPECIALISTA_LOG.exists():
        try: log = json.loads(ESPECIALISTA_LOG.read_text(encoding="utf-8"))
        except: pass
    log.append(entrada)
    ESPECIALISTA_LOG.write_text(json.dumps(log[-50:], ensure_ascii=False, indent=2),
                                encoding="utf-8")

    prog("Modo especialista concluido!", 100)

    return {
        "melhor_variante":   melhor["nome"],
        "melhores_pesos":    melhores_pesos,
        "melhor_score":      melhor["score_medio"],
        "melhor_cobertura":  melhor["cobertura_media"],
        "pool_recomendado":  pool,
        "top5_estrategias":  resultados[:5],
        "relatorio":         relatorio,
        "n_testes":          total_testes,
    }


def _montar_relatorio_especialista(
    concursos: list[dict],
    resultados: list[dict],
    melhor: dict,
    pool: list[int],
) -> dict:
    """Monta o relatorio completo para enviar a IA."""
    import statistics as stats_mod
    import ranking as rm

    dados = stats_mod.consolidar(concursos)
    pares = rm.calcular_pares_quentes(concursos)

    freq_abs = dados["freq_abs"]
    freq_pct = dados["freq_pct"]
    atrasos  = dados["atraso"]

    # Estatisticas das linhas e colunas
    from config import GRID
    linhas  = {1:0, 2:0, 3:0, 4:0, 5:0}
    colunas = {1:0, 2:0, 3:0, 4:0, 5:0}
    pares_count = 0
    impares_count = 0
    for cs in concursos[-50:]:
        for d in cs["dezenas"]:
            l, c = GRID[d]
            linhas[l] += 1
            colunas[c] += 1
            if d % 2 == 0: pares_count += 1
            else: impares_count += 1

    n = len(concursos)

    return {
        "ultimos_n_concursos": min(n, MAX_CONCURSOS),
        "periodo": f"{concursos[0]['data']} a {concursos[-1]['data']}",
        "ranking": [
            {"dezena": d, "freq_abs": freq_abs.get(d,0),
             "freq_pct": round(freq_pct.get(d,0),1), "atraso": atrasos.get(d,0)}
            for d in range(1, 26)
        ],
        "estatisticas": {
            "soma_media":   dados["stats_soma"].get("media", 0),
            "soma_min":     dados["stats_soma"].get("minimo", 0),
            "soma_max":     dados["stats_soma"].get("maximo", 0),
            "media_pares":  round(pares_count / max(n,1), 1),
            "media_impares":round(impares_count / max(n,1), 1),
        },
        "frequencias":  {str(d): freq_pct.get(d,0) for d in range(1,26)},
        "pares":        [[a,b,c] for a,b,c in pares[:20]],
        "linhas":       {str(k): round(v/max(n,1),2) for k,v in linhas.items()},
        "colunas":      {str(k): round(v/max(n,1),2) for k,v in colunas.items()},
        "sequencias":   {
            "max_consec_media": round(
                float(np.mean([r["max_seq"] for r in dados["sequencias"]])), 2
            )
        },
        "backtest_especialista": {
            "melhor_estrategia":  melhor["nome"],
            "melhor_score":       melhor["score_medio"],
            "melhor_cobertura":   melhor["cobertura_media"],
            "top5": [
                {"nome":r["nome"],"score":r["score_medio"],"cob":r["cobertura_media"]}
                for r in resultados[:5]
            ],
        },
        "pesos_otimizados":  melhor["pesos"],
        "pool_recomendado":  pool,
    }


def resumo_especialista(resultado: dict) -> str:
    linhas = [
        "=" * 65,
        "  MODO ESPECIALISTA — RESULTADO",
        "=" * 65,
        f"  Testes executados    : {resultado.get('n_testes', 0)}",
        f"  Melhor estrategia    : {resultado.get('melhor_variante')}",
        f"  Score (hits/conc.)   : {resultado.get('melhor_score'):.3f}",
        f"  Cobertura historica  : {resultado.get('melhor_cobertura'):.1f}%",
        f"  Pool recomendado     : " +
        "  ".join(f"{d:02d}" for d in resultado.get('pool_recomendado', [])),
        "",
        "  Top-5 estrategias:",
        f"  {'#':>2}  {'Nome':<20}  {'Score':>7}  {'Cobertura':>10}",
        "  " + "-" * 46,
    ]
    for i, e in enumerate(resultado.get("top5_estrategias", [])[:5], 1):
        linhas.append(
            f"  {i:>2}  {e['nome']:<20}  {e['score_medio']:>7.3f}  "
            f"{e['cobertura_media']:>9.1f}%"
        )
    linhas.append("=" * 65)
    return "\n".join(linhas)
