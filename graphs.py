"""
graphs.py - Graficos de frequencia, tendencia, pares quentes, backtest e soma.
"""

from pathlib import Path
from config import RELATORIO_DIR, TOTAL_DEZENAS, JANELAS_TENDENCIA

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _check():
    if not HAS_MPL:
        raise ImportError("matplotlib nao instalado. Execute: pip install matplotlib")


def _salvar(fig, nome):
    caminho = RELATORIO_DIR / nome
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return caminho


def grafico_frequencia(stats, dezenas_18):
    _check()
    freq = stats["freq_abs"]
    dezenas = list(range(1, TOTAL_DEZENAS + 1))
    valores = [freq[d] for d in dezenas]
    cores = ["#1F4E79" if d in dezenas_18 else "#AAAAAA" for d in dezenas]

    fig, ax = plt.subplots(figsize=(14, 5))
    bars = ax.bar([str(d).zfill(2) for d in dezenas], valores, color=cores, edgecolor="white")
    ax.set_title("Frequencia Absoluta - Lotofacil 2026", fontsize=14, fontweight="bold")
    ax.set_xlabel("Dezena")
    ax.set_ylabel("Aparicoes")
    ax.tick_params(axis="x", labelsize=8)
    p1 = mpatches.Patch(color="#1F4E79", label="Pool das 18")
    p2 = mpatches.Patch(color="#AAAAAA", label="Fora do pool")
    ax.legend(handles=[p1, p2])
    for bar, val in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                str(val), ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    return _salvar(fig, "frequencia_absoluta.png")


def grafico_frequencia_pct(stats, dezenas_18):
    _check()
    freq = stats["freq_pct"]
    dezenas = list(range(1, TOTAL_DEZENAS + 1))
    valores = [freq[d] for d in dezenas]
    cores = ["#2E75B6" if d in dezenas_18 else "#CCCCCC" for d in dezenas]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar([str(d).zfill(2) for d in dezenas], valores, color=cores, edgecolor="white")
    ax.axhline(60.0, color="red", linestyle="--", linewidth=1, label="60% esperado")
    ax.set_title("Frequencia Percentual - Lotofacil 2026", fontsize=14, fontweight="bold")
    ax.set_xlabel("Dezena")
    ax.set_ylabel("% de concursos")
    ax.tick_params(axis="x", labelsize=8)
    ax.legend()
    fig.tight_layout()
    return _salvar(fig, "frequencia_percentual.png")


def grafico_tendencia(stats, dezenas_18):
    _check()
    tend = stats["tendencia"]
    dezenas = list(range(1, TOTAL_DEZENAS + 1))
    janelas = JANELAS_TENDENCIA[:3]
    cores_linhas = ["#FF0000", "#E97132", "#1F4E79"]

    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(TOTAL_DEZENAS)
    labels = [str(d).zfill(2) for d in dezenas]

    for n, cor in zip(janelas, cores_linhas):
        vals = [tend[d].get(n, 0) for d in dezenas]
        ax.plot(x, vals, marker="o", markersize=4, linewidth=1.5,
                color=cor, label=f"Ultimos {n}")

    ax.axhline(60.0, color="gray", linestyle="--", linewidth=0.8, label="60% esperado")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Tendencia de Frequencia (ultimos N concursos)", fontsize=13, fontweight="bold")
    ax.set_ylabel("% de aparicoes")
    ax.set_xlabel("Dezena")
    ax.legend()
    for d in dezenas_18:
        ax.axvspan(d - 1 - 0.4, d - 1 + 0.4, alpha=0.07, color="#2E75B6")
    fig.tight_layout()
    return _salvar(fig, "tendencia.png")


def grafico_atraso(stats, dezenas_18):
    _check()
    atr = stats["atraso"]
    dezenas = list(range(1, TOTAL_DEZENAS + 1))
    valores = [atr[d] for d in dezenas]
    cores = ["#C00000" if v > 10 else ("#1F4E79" if d in dezenas_18 else "#AAAAAA")
             for d, v in zip(dezenas, valores)]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar([str(d).zfill(2) for d in dezenas], valores, color=cores, edgecolor="white")
    ax.set_title("Atraso das Dezenas", fontsize=13, fontweight="bold")
    ax.set_xlabel("Dezena")
    ax.set_ylabel("Concursos de atraso")
    ax.tick_params(axis="x", labelsize=8)
    p1 = mpatches.Patch(color="#C00000", label="Atraso > 10")
    p2 = mpatches.Patch(color="#1F4E79", label="Pool (normal)")
    p3 = mpatches.Patch(color="#AAAAAA", label="Fora do pool")
    ax.legend(handles=[p1, p2, p3])
    fig.tight_layout()
    return _salvar(fig, "atraso.png")


def grafico_pares_quentes(pares_quentes, dezenas_18):
    _check()
    top = pares_quentes[:20]
    labels = [f"{a:02d}-{b:02d}" for a, b, _ in top]
    valores = [c for _, _, c in top]
    cores = ["#1F4E79" if (a in dezenas_18 and b in dezenas_18) else
             "#9DC3E6" if (a in dezenas_18 or b in dezenas_18) else "#CCCCCC"
             for a, b, _ in top]

    fig, ax = plt.subplots(figsize=(14, 5))
    bars = ax.bar(labels, valores, color=cores, edgecolor="white")
    ax.set_title("Top 20 Pares Mais Frequentes", fontsize=13, fontweight="bold")
    ax.set_xlabel("Par de Dezenas")
    ax.set_ylabel("Aparicoes juntas")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    p1 = mpatches.Patch(color="#1F4E79", label="Ambas no pool")
    p2 = mpatches.Patch(color="#9DC3E6", label="Uma no pool")
    p3 = mpatches.Patch(color="#CCCCCC", label="Fora do pool")
    ax.legend(handles=[p1, p2, p3])
    for bar, val in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                str(val), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    return _salvar(fig, "pares_quentes.png")


def grafico_backtest(resultado_bt):
    _check()
    faixas = resultado_bt["faixas"]
    labels = ["15 pts", "14 pts", "13 pts", "12 pts", "11 pts", "< 11"]
    chaves = [15, 14, 13, 12, 11, "abaixo_11"]
    valores = [faixas.get(k, 0) for k in chaves]
    cores = ["#1F4E79", "#2E75B6", "#9DC3E6", "#BDD7EE", "#DDEBF7", "#CCCCCC"]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, valores, color=cores, edgecolor="white", width=0.6)
    tipo = "DINAMICO" if resultado_bt.get("tipo") == "dinamico" else "FIXO"
    ax.set_title(f"Backtest {tipo} - Distribuicao de Resultados", fontsize=13, fontweight="bold")
    ax.set_ylabel("Concursos")
    for bar, val in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                str(val), ha="center", va="bottom", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return _salvar(fig, "backtest_faixas.png")


def grafico_soma(stats):
    _check()
    somas = [s["soma"] for s in stats["soma"]]
    concursos = [s["concurso"] for s in stats["soma"]]
    media = sum(somas) / len(somas) if somas else 0

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(concursos, somas, color="#1F4E79", linewidth=0.8, alpha=0.7)
    ax.axhline(media, color="red", linestyle="--", linewidth=1, label=f"Media = {media:.1f}")
    ax.axhline(170, color="orange", linestyle=":", linewidth=1, label="Limite inferior (170)")
    ax.axhline(230, color="orange", linestyle=":", linewidth=1, label="Limite superior (230)")
    ax.set_title("Soma das Dezenas por Concurso", fontsize=13, fontweight="bold")
    ax.set_xlabel("Concurso")
    ax.set_ylabel("Soma")
    ax.legend()
    fig.tight_layout()
    return _salvar(fig, "soma_dezenas.png")


def grafico_comparativo_pools(analise_pools):
    _check()
    sizes   = [p["pool_size"] for p in analise_pools]
    custos  = [p["custo"] for p in analise_pools]
    coberturas = [p["prob_cobertura"] for p in analise_pools]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    x = range(len(sizes))
    labels = [f"Pool {s}" for s in sizes]

    bar = ax1.bar(x, custos, color="#1F4E79", alpha=0.7, label="Custo (R$)")
    ax1.set_ylabel("Custo total (R$)", color="#1F4E79")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels)
    for b, val in zip(bar, custos):
        ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 1,
                 f"R${val:.0f}", ha="center", va="bottom", fontsize=9, color="#1F4E79")

    ax2 = ax1.twinx()
    ax2.plot(list(x), coberturas, color="#C00000", marker="o",
             linewidth=2, markersize=8, label="Cobertura (%)")
    ax2.set_ylabel("Cobertura (%)", color="#C00000")
    for xi, val in zip(x, coberturas):
        ax2.text(xi, val + 0.5, f"{val:.1f}%", ha="center", va="bottom",
                 fontsize=9, color="#C00000")

    ax1.set_title("Comparativo de Pools: Custo vs Cobertura", fontsize=13, fontweight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    fig.tight_layout()
    return _salvar(fig, "comparativo_pools.png")


def grafico_decaimento(concursos, dezenas_18):
    """Visualiza o peso de cada concurso pelo decaimento exponencial."""
    _check()
    from config import DECAY_FACTOR
    n = len(concursos)
    pesos = [DECAY_FACTOR ** (n - 1 - i) for i in range(n)]
    nums  = [cs["concurso"] for cs in concursos]

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(nums, pesos, color="#2E75B6", alpha=0.6)
    ax.plot(nums, pesos, color="#1F4E79", linewidth=1)
    ax.set_title(f"Peso por Concurso (Decaimento Exponencial, fator={DECAY_FACTOR})",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Concurso")
    ax.set_ylabel("Peso")
    fig.tight_layout()
    return _salvar(fig, "decaimento_exponencial.png")


def gerar_todos(stats, dezenas_18, resultado_bt, pares_quentes=None,
                analise_pools=None, concursos=None):
    paths = []
    tarefas = [
        lambda: grafico_frequencia(stats, dezenas_18),
        lambda: grafico_frequencia_pct(stats, dezenas_18),
        lambda: grafico_tendencia(stats, dezenas_18),
        lambda: grafico_atraso(stats, dezenas_18),
        lambda: grafico_backtest(resultado_bt),
        lambda: grafico_soma(stats),
    ]
    if pares_quentes:
        tarefas.append(lambda: grafico_pares_quentes(pares_quentes, dezenas_18))
    if analise_pools:
        tarefas.append(lambda: grafico_comparativo_pools(analise_pools))
    if concursos:
        tarefas.append(lambda: grafico_decaimento(concursos, dezenas_18))

    for fn in tarefas:
        try:
            paths.append(fn())
        except Exception as exc:
            print(f"  AVISO: Grafico ignorado: {exc}")
    return paths
