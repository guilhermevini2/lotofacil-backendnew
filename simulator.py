"""
simulator.py - Backtest historico fixo e dinamico (sem vies de dados futuros).
"""

from fechamento import gerar_jogos
from config import DEZENAS_SORTEADAS

FAIXAS = {15: "15 pontos (maximo)", 14: "14 pontos",
          13: "13 pontos", 12: "12 pontos", 11: "11 pontos"}


def _acertos(jogo, sorteio):
    return len(set(jogo) & set(sorteio))


# -- Backtest fixo ------------------------------------------------------------

def backtest(concursos, dezenas_pool, inicio=None, fim=None):
    jogos = gerar_jogos(dezenas_pool)
    cs_filtro = [
        cs for cs in concursos
        if (inicio is None or cs["concurso"] >= inicio)
        and (fim is None or cs["concurso"] <= fim)
    ]
    detalhes = []
    contagem = {k: 0 for k in FAIXAS}
    contagem["abaixo_11"] = 0
    total_pool = 0

    for cs in cs_filtro:
        sorteio = cs["dezenas"]
        pool_hits = len(set(sorteio) & set(dezenas_pool))
        dentro = pool_hits == DEZENAS_SORTEADAS
        total_pool += int(dentro)

        resultados = [_acertos(j, sorteio) for j in jogos]
        melhor = max(resultados)
        idx = resultados.index(melhor) + 1

        chave = melhor if melhor >= 11 else "abaixo_11"
        contagem[chave] = contagem.get(chave, 0) + 1

        detalhes.append({
            "concurso": cs["concurso"], "data": cs["data"],
            "sorteio": sorteio, "pool_hits": pool_hits,
            "dentro_pool": dentro, "melhor_pts": melhor,
            "melhor_jogo": idx, "todos_jogos": resultados,
        })

    n = len(cs_filtro)
    return {
        "tipo": "fixo",
        "total_concursos":  n,
        "total_pool":       total_pool,
        "pct_dentro_pool":  round(total_pool / n * 100, 1) if n else 0,
        "faixas":           contagem,
        "detalhes":         detalhes,
    }


# -- Backtest dinamico --------------------------------------------------------

def backtest_dinamico(concursos, tamanho_pool=18, janela_treino=60):
    """
    Para cada concurso de teste, calcula o pool usando APENAS
    os concursos anteriores a ele — sem vies de dados futuros.
    """
    import statistics as stats_mod
    import ranking as ranking_mod

    if len(concursos) < janela_treino + 10:
        return {"erro": "Historico insuficiente para backtest dinamico."}

    detalhes = []
    contagem = {k: 0 for k in FAIXAS}
    contagem["abaixo_11"] = 0
    total_pool = 0

    for i in range(janela_treino, len(concursos)):
        treino   = concursos[max(0, i - janela_treino):i]
        cs_teste = concursos[i]

        dados_treino = stats_mod.consolidar(treino)
        pool = ranking_mod.top_n(dados_treino, treino, tamanho_pool)
        jogos = gerar_jogos(pool)

        sorteio   = cs_teste["dezenas"]
        pool_hits = len(set(sorteio) & set(pool))
        dentro    = pool_hits == DEZENAS_SORTEADAS
        total_pool += int(dentro)

        resultados = [_acertos(j, sorteio) for j in jogos]
        melhor = max(resultados)
        chave = melhor if melhor >= 11 else "abaixo_11"
        contagem[chave] = contagem.get(chave, 0) + 1

        detalhes.append({
            "concurso":    cs_teste["concurso"],
            "data":        cs_teste["data"],
            "pool":        pool,
            "pool_hits":   pool_hits,
            "dentro_pool": dentro,
            "melhor_pts":  melhor,
        })

    n = len(detalhes)
    return {
        "tipo":             "dinamico",
        "janela_treino":    janela_treino,
        "tamanho_pool":     tamanho_pool,
        "total_concursos":  n,
        "total_pool":       total_pool,
        "pct_dentro_pool":  round(total_pool / n * 100, 1) if n else 0,
        "faixas":           contagem,
        "detalhes":         detalhes,
    }


def resumo_backtest(resultado):
    if "erro" in resultado:
        return f"  AVISO: {resultado['erro']}"
    n    = resultado["total_concursos"]
    tipo = "DINAMICO" if resultado.get("tipo") == "dinamico" else "FIXO"
    linhas = [
        "=" * 62,
        f"  BACKTEST {tipo}",
        f"  Concursos simulados     : {n}",
        f"  Sorteios dentro do pool : {resultado['total_pool']} ({resultado['pct_dentro_pool']}%)",
        "",
        "  Distribuicao de resultados (melhor jogo por concurso):",
    ]
    for pts, label in FAIXAS.items():
        qtd = resultado["faixas"].get(pts, 0)
        pct = round(qtd / n * 100, 1) if n else 0
        linhas.append(f"    {label:<30} {qtd:4d}  ({pct:.1f}%)")
    qtd_b = resultado["faixas"].get("abaixo_11", 0)
    pct_b = round(qtd_b / n * 100, 1) if n else 0
    linhas.append(f"    {'< 11 pontos':<30} {qtd_b:4d}  ({pct_b:.1f}%)")
    linhas.append("=" * 62)
    return "\n".join(linhas)
