"""
hibrido_autoaprendizado.py - Pipeline de autoaprendizado pos-concurso.

Apos cada novo concurso disponivel, executa automaticamente:
  1. Download do resultado oficial
  2. Backtest do motor hibrido nos concursos recentes
  3. Otimizacao dos pesos por Hill Climbing
  4. Re-treinamento do modelo ML (se necessario)
  5. Atualizacao do ranking e cache
  6. Relatorio de desempenho
"""

import json
import time
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, CONCURSO_INICIO_2026, DEZENAS_SORTEADAS
from hibrido_pesos import carregar_pesos, salvar_pesos, otimizar_pesos
from hibrido_score import calcular_scores

LOG_PATH = BASE_DIR / "cache" / "autoaprendizado_log.json"


# -- Historico de desempenho --------------------------------------------------

def _carregar_log() -> list:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _salvar_log(log: list):
    LOG_PATH.parent.mkdir(exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2),
                        encoding="utf-8")


# -- Avaliacao do ciclo atual -------------------------------------------------

def avaliar_ciclo(
    concursos: list[dict],
    pesos: dict,
    ml_probas: dict = None,
    n_ultimos: int = 10,
) -> dict:
    """
    Avalia o desempenho dos pesos atuais nos ultimos N concursos.
    Retorna metricas de hits (dezenas do sorteio dentro do pool de 18).
    """
    inicio = max(30, len(concursos) - n_ultimos)
    hits_list = []

    for idx in range(inicio, len(concursos)):
        historico = concursos[:idx]
        sorteio = set(concursos[idx]["dezenas"])
        scores = calcular_scores(historico, pesos, ml_probas)
        pool18 = set(sorted(scores, key=lambda d: -scores[d])[:18])
        hits_list.append(len(sorteio & pool18))

    if not hits_list:
        return {"n": 0, "hits_media": 0.0, "hits_min": 0, "hits_max": 0,
                "cobertura_pct": 0.0}

    return {
        "n":             len(hits_list),
        "hits_media":    round(sum(hits_list) / len(hits_list), 2),
        "hits_min":      min(hits_list),
        "hits_max":      max(hits_list),
        "cobertura_pct": round(
            sum(1 for h in hits_list if h == DEZENAS_SORTEADAS) / len(hits_list) * 100, 1
        ),
        "hits_lista":    hits_list,
    }


# -- Pipeline principal -------------------------------------------------------

def executar_ciclo_autoaprendizado(
    concursos: list[dict],
    ml_probas: dict = None,
    forcar_otimizacao: bool = False,
    forcar_ml: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Executa o pipeline completo de autoaprendizado.

    Parametros
    ----------
    concursos           : lista atualizada de concursos
    ml_probas           : probabilidades ML ja calculadas (None = nao usar)
    forcar_otimizacao   : forcara re-otimizacao mesmo sem novos concursos
    forcar_ml           : forcara re-treinamento do ML
    verbose             : exibir progresso

    Retorna dict com metricas e resultado do ciclo.
    """
    log = _carregar_log()
    ultimo_processado = log[-1]["concurso"] if log else 0
    ultimo_disponivel = concursos[-1]["concurso"] if concursos else 0

    if verbose:
        print(f"\n  Ultimo processado: #{ultimo_processado}")
        print(f"  Ultimo disponivel: #{ultimo_disponivel}")

    novos = ultimo_disponivel > ultimo_processado

    if not novos and not forcar_otimizacao:
        if verbose:
            print("  Nenhum concurso novo. Autoaprendizado ignorado.")
        return {"status": "sem_novidades", "concurso": ultimo_disponivel}

    resultado = {
        "concurso":  ultimo_disponivel,
        "data":      concursos[-1]["data"],
        "timestamp": datetime.now().isoformat(),
        "novos_concursos": int(ultimo_disponivel - ultimo_processado),
    }

    # Passo 1: Avaliar desempenho ANTES da otimizacao
    if verbose:
        print("\n  [1/5] Avaliando desempenho atual...")
    pesos_antes = carregar_pesos()
    metricas_antes = avaliar_ciclo(concursos, pesos_antes, ml_probas, n_ultimos=20)
    resultado["metricas_antes"] = metricas_antes
    if verbose:
        print(f"       Hits media: {metricas_antes['hits_media']:.2f} | "
              f"Cobertura: {metricas_antes['cobertura_pct']}%")

    # Passo 2: Backtest e otimizacao dos pesos
    if verbose:
        print("\n  [2/5] Otimizando pesos por Hill Climbing...")

    def score_fn_wrapper(historico_conc, pesos, ml_probas=None):
        return calcular_scores(historico_conc, pesos, ml_probas)

    pesos_novos, melhor_score = otimizar_pesos(
        concursos,
        score_fn=score_fn_wrapper,
        n_iter=80,
        n_teste=30,
        verbose=verbose,
    )

    # Passo 3: Avaliar DEPOIS da otimizacao
    metricas_depois = avaliar_ciclo(concursos, pesos_novos, ml_probas, n_ultimos=20)
    resultado["metricas_depois"] = metricas_depois
    melhora = metricas_depois["hits_media"] - metricas_antes["hits_media"]
    resultado["melhora_hits"] = round(melhora, 3)

    if verbose:
        print(f"\n  [3/5] Avaliando apos otimizacao...")
        print(f"       Hits media: {metricas_depois['hits_media']:.2f} | "
              f"Cobertura: {metricas_depois['cobertura_pct']}%")
        sinal = "+" if melhora >= 0 else ""
        print(f"       Melhora: {sinal}{melhora:.3f} hits/concurso")

    # Aceitar novos pesos se melhoraram (ou forcado)
    if melhora >= 0 or forcar_otimizacao:
        salvar_pesos(pesos_novos, meta={
            "concurso": ultimo_disponivel,
            "hits_media": metricas_depois["hits_media"],
            "timestamp": resultado["timestamp"],
        })
        resultado["pesos_atualizados"] = True
        if verbose:
            print("  Pesos atualizados e salvos.")
    else:
        resultado["pesos_atualizados"] = False
        if verbose:
            print("  Pesos nao melhoraram — mantendo anteriores.")

    # Passo 4: Re-treinar ML se necessario
    if verbose:
        print("\n  [4/5] Verificando modelo ML...")
    try:
        from ml_model import treinar as ml_treinar
        meta_ml = ml_treinar(concursos, forcar=forcar_ml, verbose=verbose)
        resultado["ml_atualizado"] = True
        resultado["ml_auc"] = meta_ml.get("auc_medio")
        if verbose:
            print(f"       AUC: {meta_ml.get('auc_medio', 0):.4f}")
    except Exception as exc:
        resultado["ml_atualizado"] = False
        resultado["ml_erro"] = str(exc)
        if verbose:
            print(f"       ML ignorado: {exc}")

    # Passo 5: Salvar log
    if verbose:
        print("\n  [5/5] Salvando log de desempenho...")
    log.append(resultado)
    _salvar_log(log[-200:])   # manter ultimas 200 entradas

    resultado["status"] = "concluido"
    return resultado


# -- Relatorio de historico ---------------------------------------------------

def relatorio_historico(n_ultimos: int = 20) -> str:
    log = _carregar_log()
    if not log:
        return "  Nenhum ciclo de autoaprendizado registrado ainda."

    entradas = log[-n_ultimos:]
    linhas = [
        "=" * 62,
        f"  HISTORICO DE AUTOAPRENDIZADO (ultimos {len(entradas)} ciclos)",
        "=" * 62,
        f"  {'Concurso':>9}  {'Data':>12}  {'Hits antes':>10}  "
        f"{'Hits depois':>11}  {'Melhora':>8}  {'ML AUC':>8}",
        "  " + "-" * 58,
    ]
    for e in entradas:
        ha = e.get("metricas_antes", {}).get("hits_media", 0)
        hd = e.get("metricas_depois", {}).get("hits_media", 0)
        mh = e.get("melhora_hits", 0)
        auc = e.get("ml_auc", 0) or 0
        sinal = "+" if mh >= 0 else ""
        linhas.append(
            f"  #{e.get('concurso','?'):>8}  {e.get('data','?'):>12}  "
            f"{ha:>10.2f}  {hd:>11.2f}  "
            f"{sinal}{mh:>7.3f}  {auc:>8.4f}"
        )
    linhas.append("=" * 62)
    return "\n".join(linhas)


def resumo_ultimo_ciclo(resultado: dict) -> str:
    if resultado.get("status") == "sem_novidades":
        return "  Autoaprendizado: sem novos concursos."

    antes  = resultado.get("metricas_antes", {})
    depois = resultado.get("metricas_depois", {})
    mh     = resultado.get("melhora_hits", 0)
    sinal  = "+" if mh >= 0 else ""

    linhas = [
        "=" * 55,
        "  AUTOAPRENDIZADO - RESULTADO DO CICLO",
        "=" * 55,
        f"  Concurso processado : #{resultado.get('concurso')}",
        f"  Novos concursos     : {resultado.get('novos_concursos', 0)}",
        f"  Hits media antes    : {antes.get('hits_media', 0):.2f}",
        f"  Hits media depois   : {depois.get('hits_media', 0):.2f}",
        f"  Melhora             : {sinal}{mh:.3f} hits/concurso",
        f"  Pesos atualizados   : {'SIM' if resultado.get('pesos_atualizados') else 'NAO'}",
        f"  ML atualizado       : {'SIM' if resultado.get('ml_atualizado') else 'NAO'}",
    ]
    if resultado.get("ml_auc"):
        linhas.append(f"  ML AUC              : {resultado['ml_auc']:.4f}")
    linhas.append("=" * 55)
    return "\n".join(linhas)
