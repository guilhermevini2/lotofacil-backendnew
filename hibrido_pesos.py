"""
hibrido_pesos.py - Gestao dos pesos do motor hibrido.

Os pesos iniciais refletem a arquitetura definida. Apos cada ciclo de
backtest, o otimizador ajusta os pesos para maximizar a cobertura historica.
Os pesos otimizados sao salvos em cache e reutilizados automaticamente.
"""

import json
import copy
import random
import numpy as np
from pathlib import Path
from config import BASE_DIR

PESOS_PATH = BASE_DIR / "cache" / "hibrido_pesos.json"

# -- Pesos iniciais (arquitetura definida) ------------------------------------

PESOS_INICIAIS = {
    "freq_100":     0.15,
    "freq_50":      0.10,
    "freq_20":      0.15,
    "freq_10":      0.20,
    "tendencia":    0.10,
    "atraso":       0.08,
    "repeticao":    0.05,
    "linhas_cols":  0.05,
    "paridade":     0.03,
    "moldura":      0.03,
    "soma_ideal":   0.03,
    "ml":           0.03,
}

# Limites de variacao permitida por otimizacao (min, max)
LIMITES = {
    "freq_100":     (0.05, 0.30),
    "freq_50":      (0.03, 0.20),
    "freq_20":      (0.05, 0.30),
    "freq_10":      (0.05, 0.35),
    "tendencia":    (0.02, 0.20),
    "atraso":       (0.02, 0.20),
    "repeticao":    (0.01, 0.12),
    "linhas_cols":  (0.01, 0.12),
    "paridade":     (0.01, 0.08),
    "moldura":      (0.01, 0.08),
    "soma_ideal":   (0.01, 0.08),
    "ml":           (0.01, 0.15),
}


def _normalizar(pesos: dict) -> dict:
    """Garante que os pesos somam 1.0."""
    total = sum(pesos.values())
    if total == 0:
        return {k: 1/len(pesos) for k in pesos}
    return {k: v / total for k, v in pesos.items()}


def carregar_pesos() -> dict:
    """Carrega pesos otimizados do disco, ou usa os iniciais."""
    if PESOS_PATH.exists():
        try:
            dados = json.loads(PESOS_PATH.read_text(encoding="utf-8"))
            pesos = dados.get("pesos", PESOS_INICIAIS)
            # Garantir que todas as chaves existem (backward compat)
            for k, v in PESOS_INICIAIS.items():
                if k not in pesos:
                    pesos[k] = v
            return _normalizar(pesos)
        except Exception:
            pass
    return dict(PESOS_INICIAIS)


def salvar_pesos(pesos: dict, meta: dict = None):
    """Salva pesos otimizados no disco."""
    PESOS_PATH.parent.mkdir(exist_ok=True)
    dados = {"pesos": pesos, "meta": meta or {}}
    PESOS_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def resetar_pesos():
    """Volta aos pesos iniciais."""
    if PESOS_PATH.exists():
        PESOS_PATH.unlink()


# -- Otimizacao por Hill Climbing ---------------------------------------------

def _perturbar(pesos: dict, intensidade: float = 0.05) -> dict:
    """
    Pertuba levemente os pesos. Garante que continuam dentro dos limites
    e somam 1.0.
    """
    novo = copy.deepcopy(pesos)
    chaves = list(novo.keys())
    # Sortear 2-4 pesos para alterar
    n_alterar = random.randint(2, min(4, len(chaves)))
    para_alterar = random.sample(chaves, n_alterar)

    for k in para_alterar:
        delta = random.uniform(-intensidade, intensidade)
        mn, mx = LIMITES.get(k, (0.01, 0.40))
        novo[k] = float(np.clip(novo[k] + delta, mn, mx))

    return _normalizar(novo)


def _avaliar_pesos(
    pesos: dict,
    concursos: list[dict],
    score_fn,
    n_teste: int = 40,
) -> float:
    """
    Avalia um conjunto de pesos medindo a cobertura media nos ultimos
    n_teste concursos (sem data leakage).
    Retorna: hits_media (media de dezenas do sorteio dentro do pool de 18).
    """
    from config import DEZENAS_SORTEADAS
    total_hits = 0
    n_avaliados = 0

    inicio = max(30, len(concursos) - n_teste)
    for idx in range(inicio, len(concursos)):
        historico = concursos[:idx]
        sorteio = set(concursos[idx]["dezenas"])

        scores = score_fn(historico, pesos=pesos, ml_probas=None)
        pool18 = sorted(scores, key=lambda d: -scores[d])[:18]
        hits = len(sorteio & set(pool18))
        total_hits += hits
        n_avaliados += 1

    return total_hits / n_avaliados if n_avaliados else 0.0


def otimizar_pesos(
    concursos: list[dict],
    score_fn,
    n_iter: int = 120,
    n_teste: int = 40,
    verbose: bool = True,
) -> tuple[dict, float]:
    """
    Hill Climbing para otimizar os pesos.

    Parametros
    ----------
    concursos : lista de concursos
    score_fn  : funcao(historico, pesos, ml_probas) -> {dezena: score}
    n_iter    : iteracoes de busca
    n_teste   : concursos usados na avaliacao
    verbose   : exibir progresso

    Retorna (pesos_otimos, melhor_hits_media)
    """
    pesos_atual = carregar_pesos()
    melhor_score = _avaliar_pesos(pesos_atual, concursos, score_fn, n_teste)
    melhor_pesos = dict(pesos_atual)

    if verbose:
        print(f"  Score inicial: {melhor_score:.4f} hits/concurso")

    sem_melhora = 0
    for i in range(n_iter):
        # Intensidade diminui com o tempo (simulated annealing suave)
        intensidade = max(0.01, 0.08 * (1 - i / n_iter))
        candidato = _perturbar(melhor_pesos, intensidade)
        score_cand = _avaliar_pesos(candidato, concursos, score_fn, n_teste)

        if score_cand > melhor_score:
            melhor_score = score_cand
            melhor_pesos = candidato
            sem_melhora = 0
            if verbose:
                print(f"  [{i+1:3d}/{n_iter}] Melhora: {melhor_score:.4f}")
        else:
            sem_melhora += 1

        # Early stopping se convergiu
        if sem_melhora >= 30:
            if verbose:
                print(f"  Convergido na iteracao {i+1}")
            break

    if verbose:
        print(f"  Score final: {melhor_score:.4f} hits/concurso")
        print(f"  Pesos otimizados:")
        for k, v in sorted(melhor_pesos.items(), key=lambda x: -x[1]):
            bar = "#" * int(v * 100)
            print(f"    {k:<18} {bar} {v*100:.1f}%")

    return melhor_pesos, melhor_score


def resumo_pesos(pesos: dict) -> str:
    linhas = [
        "=" * 55,
        "  PESOS DO MOTOR HIBRIDO",
        "=" * 55,
        f"  {'Criterio':<22} {'Peso':>8}  {'Barra'}",
        "  " + "-" * 50,
    ]
    for k, v in sorted(pesos.items(), key=lambda x: -x[1]):
        bar = "#" * int(v * 60)
        linhas.append(f"  {k:<22} {v*100:>6.1f}%  {bar}")
    linhas.append("=" * 55)
    return "\n".join(linhas)
