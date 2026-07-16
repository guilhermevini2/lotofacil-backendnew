"""
statistics.py — Análises estatísticas completas dos concursos da Lotofácil.
"""

from collections import Counter, defaultdict
from datetime import datetime

from config import (
    TOTAL_DEZENAS, DEZENAS_SORTEADAS,
    JANELAS_TENDENCIA, PRIMOS, FIBONACCI, MULTIPLOS3,
    GRID, MOLDURA, CENTRO,
)


# ── utilidades internas ────────────────────────────────────────────────────────

def _todas_dezenas() -> list[int]:
    return list(range(1, TOTAL_DEZENAS + 1))


def _mes_ano(data_str: str) -> str:
    """Converte 'DD/MM/AAAA' → 'YYYY-MM' para agrupamentos."""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m")
    except Exception:
        return "desconhecido"


# ── frequência ────────────────────────────────────────────────────────────────

def frequencia_absoluta(concursos: list[dict]) -> dict[int, int]:
    c = Counter()
    for cs in concursos:
        c.update(cs["dezenas"])
    return {d: c.get(d, 0) for d in _todas_dezenas()}


def frequencia_percentual(concursos: list[dict]) -> dict[int, float]:
    n = len(concursos)
    if n == 0:
        return {d: 0.0 for d in _todas_dezenas()}
    freq = frequencia_absoluta(concursos)
    return {d: round(v / n * 100, 2) for d, v in freq.items()}


# ── atraso ────────────────────────────────────────────────────────────────────

def atraso(concursos: list[dict]) -> dict[int, int]:
    """Quantidade de concursos desde a última aparição de cada dezena."""
    ultimo = {d: None for d in _todas_dezenas()}
    total = len(concursos)
    for i, cs in enumerate(concursos):
        for d in cs["dezenas"]:
            ultimo[d] = i
    return {
        d: (total - 1 - pos) if pos is not None else total
        for d, pos in ultimo.items()
    }


# ── tendência por janela ──────────────────────────────────────────────────────

def tendencia(concursos: list[dict]) -> dict[int, dict[int, float]]:
    """
    Para cada janela em JANELAS_TENDENCIA, calcula a frequência percentual
    nos últimos N concursos.
    Retorna: {dezena: {janela: pct, ...}, ...}
    """
    resultado: dict[int, dict[int, float]] = {d: {} for d in _todas_dezenas()}
    for n in JANELAS_TENDENCIA:
        janela = concursos[-n:] if len(concursos) >= n else concursos
        pct = frequencia_percentual(janela)
        for d in _todas_dezenas():
            resultado[d][n] = pct[d]
    return resultado


# ── frequência por mês e semestre ─────────────────────────────────────────────

def frequencia_por_mes(concursos: list[dict]) -> dict[str, dict[int, int]]:
    """Retorna {mes: {dezena: contagem}}"""
    agrup: dict[str, Counter] = defaultdict(Counter)
    for cs in concursos:
        mes = _mes_ano(cs["data"])
        agrup[mes].update(cs["dezenas"])
    return {mes: dict(c) for mes, c in sorted(agrup.items())}


def frequencia_por_semestre(concursos: list[dict]) -> dict[str, dict[int, int]]:
    """Retorna {'2026-S1': {dezena: contagem}, ...}"""
    agrup: dict[str, Counter] = defaultdict(Counter)
    for cs in concursos:
        try:
            dt = datetime.strptime(cs["data"], "%d/%m/%Y")
            sem = f"{dt.year}-S{'1' if dt.month <= 6 else '2'}"
        except Exception:
            sem = "desconhecido"
        agrup[sem].update(cs["dezenas"])
    return {sem: dict(c) for sem, c in sorted(agrup.items())}


# ── distribuição estrutural ───────────────────────────────────────────────────

def distribuicao_linhas_colunas(concursos: list[dict]) -> dict:
    """
    Para cada concurso, quantas dezenas caem em cada linha (1-5) e coluna (1-5).
    Retorna médias históricas: {linhas: {1: media, ...}, colunas: {1: media, ...}}
    """
    soma_l: Counter = Counter()
    soma_c: Counter = Counter()
    n = len(concursos)
    for cs in concursos:
        for d in cs["dezenas"]:
            l, c = GRID[d]
            soma_l[l] += 1
            soma_c[c] += 1
    media_l = {k: round(v / n, 2) for k, v in sorted(soma_l.items())}
    media_c = {k: round(v / n, 2) for k, v in sorted(soma_c.items())}
    return {"linhas": media_l, "colunas": media_c}


def pares_impares(concursos: list[dict]) -> list[dict]:
    """Por concurso: {'concurso': N, 'pares': X, 'impares': Y}"""
    resultado = []
    for cs in concursos:
        pares = sum(1 for d in cs["dezenas"] if d % 2 == 0)
        resultado.append({
            "concurso": cs["concurso"],
            "pares": pares,
            "impares": DEZENAS_SORTEADAS - pares,
        })
    return resultado


def moldura_centro(concursos: list[dict]) -> list[dict]:
    """Por concurso: {'concurso': N, 'moldura': X, 'centro': Y}"""
    resultado = []
    for cs in concursos:
        m = sum(1 for d in cs["dezenas"] if d in MOLDURA)
        resultado.append({
            "concurso": cs["concurso"],
            "moldura": m,
            "centro": DEZENAS_SORTEADAS - m,
        })
    return resultado


# ── conjuntos matemáticos ─────────────────────────────────────────────────────

def contagem_conjuntos(concursos: list[dict]) -> list[dict]:
    """Por concurso: quantos primos, fibonacci, múltiplos de 3 foram sorteados."""
    resultado = []
    for cs in concursos:
        s = set(cs["dezenas"])
        resultado.append({
            "concurso": cs["concurso"],
            "primos":     len(s & PRIMOS),
            "fibonacci":  len(s & FIBONACCI),
            "multiplos3": len(s & MULTIPLOS3),
        })
    return resultado


# ── soma das dezenas ──────────────────────────────────────────────────────────

def soma_dezenas(concursos: list[dict]) -> list[dict]:
    """Por concurso: soma das 15 dezenas sorteadas."""
    return [
        {"concurso": cs["concurso"], "soma": sum(cs["dezenas"])}
        for cs in concursos
    ]


def estatisticas_soma(concursos: list[dict]) -> dict:
    """Média, mínimo e máximo histórico da soma das dezenas."""
    somas = [sum(cs["dezenas"]) for cs in concursos]
    if not somas:
        return {}
    return {
        "media": round(sum(somas) / len(somas), 2),
        "minimo": min(somas),
        "maximo": max(somas),
    }


# ── sequências consecutivas ───────────────────────────────────────────────────

def sequencias_consecutivas(concursos: list[dict]) -> list[dict]:
    """
    Por concurso: maior sequência consecutiva e total de pares adjacentes.
    """
    resultado = []
    for cs in concursos:
        dezenas = sorted(cs["dezenas"])
        max_seq = 1
        atual = 1
        pares = 0
        for i in range(1, len(dezenas)):
            if dezenas[i] == dezenas[i - 1] + 1:
                atual += 1
                pares += 1
                max_seq = max(max_seq, atual)
            else:
                atual = 1
        resultado.append({
            "concurso":   cs["concurso"],
            "max_seq":    max_seq,
            "pares_adj":  pares,
        })
    return resultado


# ── repetição em relação ao concurso anterior ────────────────────────────────

def repeticoes(concursos: list[dict]) -> list[dict]:
    """
    Para cada concurso (a partir do 2.º), quantas dezenas se repetiram
    em relação ao concurso imediatamente anterior.
    """
    resultado = []
    for i in range(1, len(concursos)):
        ant = set(concursos[i - 1]["dezenas"])
        atu = set(concursos[i]["dezenas"])
        resultado.append({
            "concurso":   concursos[i]["concurso"],
            "repeticoes": len(ant & atu),
        })
    return resultado


# ── consolidação geral ────────────────────────────────────────────────────────

def consolidar(concursos: list[dict]) -> dict:
    """
    Calcula e devolve todas as métricas de uma só vez em um dicionário.
    Útil para passar ao ranking.py e exports.py.
    """
    return {
        "freq_abs":       frequencia_absoluta(concursos),
        "freq_pct":       frequencia_percentual(concursos),
        "atraso":         atraso(concursos),
        "tendencia":      tendencia(concursos),
        "por_mes":        frequencia_por_mes(concursos),
        "por_semestre":   frequencia_por_semestre(concursos),
        "linhas_colunas": distribuicao_linhas_colunas(concursos),
        "pares_impares":  pares_impares(concursos),
        "moldura_centro": moldura_centro(concursos),
        "conjuntos":      contagem_conjuntos(concursos),
        "soma":           soma_dezenas(concursos),
        "stats_soma":     estatisticas_soma(concursos),
        "sequencias":     sequencias_consecutivas(concursos),
        "repeticoes":     repeticoes(concursos),
    }
