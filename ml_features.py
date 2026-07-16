"""
ml_features.py - Extracao de features para o modelo de ML da Lotofacil.

Para cada concurso N e cada dezena D, gera um vetor de features
calculado EXCLUSIVAMENTE com dados dos concursos anteriores a N.
Isso garante que nao ha vies de dados futuros (data leakage).

Target: 1 se D saiu no concurso N, 0 caso contrario.
"""

import numpy as np
from collections import Counter
from itertools import combinations
from config import TOTAL_DEZENAS, DEZENAS_SORTEADAS, GRID, MOLDURA, FIBONACCI, PRIMOS, MULTIPLOS3


# -- Features por dezena + janela de historico --------------------------------

def _freq_janela(historico: list[list[int]], dezena: int, n: int) -> float:
    """Frequencia percentual da dezena nos ultimos N concursos."""
    janela = historico[-n:] if len(historico) >= n else historico
    if not janela:
        return 0.0
    return sum(1 for s in janela if dezena in s) / len(janela)


def _atraso(historico: list[list[int]], dezena: int) -> int:
    """Quantos concursos desde a ultima aparicao da dezena."""
    for i, s in enumerate(reversed(historico)):
        if dezena in s:
            return i
    return len(historico)


def _freq_par(historico: list[list[int]], dezena: int, n: int = 30) -> float:
    """Frequencia media com que a dezena aparece em pares quentes."""
    janela = historico[-n:]
    if not janela:
        return 0.0
    contagem = Counter()
    for s in janela:
        if dezena in s:
            for outro in s:
                if outro != dezena:
                    contagem[outro] += 1
    # Retorna media de coocorrencias por concurso
    return sum(contagem.values()) / len(janela)


def _tendencia(historico: list[list[int]], dezena: int) -> float:
    """
    Diferenca de frequencia entre janela curta (10) e longa (50).
    Positivo = dezena em alta, Negativo = em baixa.
    """
    return _freq_janela(historico, dezena, 10) - _freq_janela(historico, dezena, 50)


def _soma_media(historico: list[list[int]], n: int = 20) -> float:
    """Soma media dos concursos recentes."""
    janela = historico[-n:]
    if not janela:
        return 192.5
    return np.mean([sum(s) for s in janela])


def _repeticao_media(historico: list[list[int]], n: int = 20) -> float:
    """Media de dezenas repetidas entre concursos consecutivos recentes."""
    janela = historico[-n:]
    if len(janela) < 2:
        return 9.0
    reps = []
    for i in range(1, len(janela)):
        reps.append(len(set(janela[i]) & set(janela[i-1])))
    return np.mean(reps)


def _saiu_ultimo(historico: list[list[int]], dezena: int) -> int:
    """1 se saiu no concurso imediatamente anterior."""
    if not historico:
        return 0
    return int(dezena in historico[-1])


def _saiu_penultimo(historico: list[list[int]], dezena: int) -> int:
    """1 se saiu no penultimo concurso."""
    if len(historico) < 2:
        return 0
    return int(dezena in historico[-2])


def _ciclo_estimado(historico: list[list[int]], dezena: int) -> float:
    """
    Ciclo medio da dezena: quantos concursos em media ela demora para reaparecer.
    Esperado matematicamente: 25/15 ≈ 1.67 concursos.
    """
    aparicoes = [i for i, s in enumerate(historico) if dezena in s]
    if len(aparicoes) < 2:
        return 25 / 15
    gaps = [aparicoes[i] - aparicoes[i-1] for i in range(1, len(aparicoes))]
    return np.mean(gaps)


def _pressao(historico: list[list[int]], dezena: int) -> float:
    """
    Pressao = atraso / ciclo_estimado.
    > 1 = dezena atrasada alem do ciclo normal (mais 'devida').
    < 1 = saiu recentemente.
    """
    atr = _atraso(historico, dezena)
    ciclo = _ciclo_estimado(historico, dezena)
    return atr / max(ciclo, 1.0)


# -- Features estruturais da dezena (estaticas) ------------------------------

def _features_estruturais(dezena: int) -> list[float]:
    """Features que dependem apenas da dezena, nao do historico."""
    linha, coluna = GRID[dezena]
    return [
        dezena / 25.0,              # posicao normalizada
        linha / 5.0,                # linha no volante
        coluna / 5.0,               # coluna no volante
        float(dezena % 2 == 0),     # e par?
        float(dezena in MOLDURA),   # esta na moldura?
        float(dezena in FIBONACCI), # e fibonacci?
        float(dezena in PRIMOS),    # e primo?
        float(dezena in MULTIPLOS3),# e multiplo de 3?
    ]


# -- Vetor de features completo -----------------------------------------------

def extrair_features(historico: list[list[int]], dezena: int) -> list[float]:
    """
    Gera vetor de features para (historico, dezena).
    historico = lista de sorteios ANTERIORES ao concurso alvo.

    Returns: lista de floats (vetor de features)
    """
    if not historico:
        return [0.0] * 24  # vetor zerado se nao ha historico

    f = []

    # Frequencias em diferentes janelas temporais
    f.append(_freq_janela(historico, dezena, 5))
    f.append(_freq_janela(historico, dezena, 10))
    f.append(_freq_janela(historico, dezena, 20))
    f.append(_freq_janela(historico, dezena, 30))
    f.append(_freq_janela(historico, dezena, 50))
    f.append(_freq_janela(historico, dezena, 100))

    # Atraso e pressao
    f.append(_atraso(historico, dezena) / max(len(historico), 1))  # normalizado
    f.append(_pressao(historico, dezena))

    # Tendencia (alta ou baixa)
    f.append(_tendencia(historico, dezena))

    # Ocorrencias recentes
    f.append(_saiu_ultimo(historico, dezena))
    f.append(_saiu_penultimo(historico, dezena))

    # Coocorrencia com outras dezenas
    f.append(_freq_par(historico, dezena, 30) / 14.0)  # normalizado por max pares

    # Ciclo e contexto global recente
    f.append(_ciclo_estimado(historico, dezena) / 5.0)  # normalizado
    f.append(_soma_media(historico, 20) / 200.0)        # normalizado
    f.append(_repeticao_media(historico, 20) / 15.0)    # normalizado

    # Features estruturais da dezena (8 features)
    f.extend(_features_estruturais(dezena))

    # Interacao: frequencia recente * pressao
    f.append(_freq_janela(historico, dezena, 10) * _pressao(historico, dezena))

    return f


NOMES_FEATURES = [
    "freq_5", "freq_10", "freq_20", "freq_30", "freq_50", "freq_100",
    "atraso_norm", "pressao",
    "tendencia",
    "saiu_ultimo", "saiu_penultimo",
    "coocorrencia_norm",
    "ciclo_norm", "soma_media_norm", "repeticao_media_norm",
    "posicao_norm", "linha_norm", "coluna_norm",
    "e_par", "e_moldura", "e_fibonacci", "e_primo", "e_multiplo3",
    "freq10_x_pressao",
]


# -- Construcao do dataset completo -------------------------------------------

def construir_dataset(
    concursos: list[dict],
    min_historico: int = 30,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """
    Constroi X (features), y (targets) e meta para todos os pares
    (concurso, dezena) com historico suficiente.

    Parametros
    ----------
    concursos    : lista ordenada de concursos
    min_historico: minimo de concursos anteriores para incluir amostra

    Retorna
    -------
    X    : array (N_amostras, N_features)
    y    : array (N_amostras,)  — 1 se dezena saiu, 0 se nao saiu
    meta : lista de dicts com {concurso, dezena, idx}
    """
    X_rows, y_rows, meta = [], [], []

    for idx in range(min_historico, len(concursos)):
        historico = [c["dezenas"] for c in concursos[:idx]]
        sorteio_alvo = set(concursos[idx]["dezenas"])
        num_concurso = concursos[idx]["concurso"]

        for dezena in range(1, TOTAL_DEZENAS + 1):
            features = extrair_features(historico, dezena)
            target = int(dezena in sorteio_alvo)
            X_rows.append(features)
            y_rows.append(target)
            meta.append({
                "concurso": num_concurso,
                "dezena":   dezena,
                "idx":      idx,
            })

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.int32)
    return X, y, meta
