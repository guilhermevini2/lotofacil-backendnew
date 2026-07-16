"""
filtros.py - Filtros de consistencia estatistica para os jogos gerados.

FILOSOFIA IMPORTANTE:
  Os filtros aqui sao ALERTAS, nao exclusoes automaticas.
  Um jogo "fora da media" nao e impossivel — e apenas incomum.
  A Caixa nao impede resultados fora de qualquer padrao historico.

  Modos de operacao:
    MODO_AVISO  (padrao): marca jogos improvaveis, mas os mantém todos
    MODO_FILTRO (opt-in): exclui jogos que falham em criterios criticos

  O usuario decide qual modo usar. O default e AVISO.
"""

from config import (
    FILTRO_SOMA_MIN, FILTRO_SOMA_MAX, FILTRO_MAX_CONSEC,
    FILTRO_PAR_MIN, FILTRO_PAR_MAX, FILTRO_LINHA_MIN, FILTRO_LINHA_MAX,
    GRID,
)

MODO_AVISO  = "aviso"
MODO_FILTRO = "filtro"


# -- Testes individuais -------------------------------------------------------

def _soma(jogo):
    s = sum(jogo)
    ok = FILTRO_SOMA_MIN <= s <= FILTRO_SOMA_MAX
    return ok, f"soma={s} (faixa {FILTRO_SOMA_MIN}-{FILTRO_SOMA_MAX})"


def _consecutivos(jogo):
    d = sorted(jogo)
    max_c = atual = 1
    for i in range(1, len(d)):
        if d[i] == d[i-1] + 1:
            atual += 1; max_c = max(max_c, atual)
        else:
            atual = 1
    ok = max_c <= FILTRO_MAX_CONSEC
    return ok, f"max_consec={max_c} (max {FILTRO_MAX_CONSEC})"


def _paridade(jogo):
    pares = sum(1 for d in jogo if d % 2 == 0)
    ok = FILTRO_PAR_MIN <= pares <= FILTRO_PAR_MAX
    return ok, f"pares={pares} (faixa {FILTRO_PAR_MIN}-{FILTRO_PAR_MAX})"


def _linhas(jogo):
    dist = {}
    for d in jogo:
        l = GRID[d][0]
        dist[l] = dist.get(l, 0) + 1
    falhas = [f"L{r}={dist.get(r,0)}" for r in range(1, 6)
              if not (FILTRO_LINHA_MIN <= dist.get(r, 0) <= FILTRO_LINHA_MAX)]
    ok = len(falhas) == 0
    detalhe = ("OK" if ok else "Linhas fora: " + " ".join(falhas))
    return ok, detalhe


# -- Analise completa de um jogo ----------------------------------------------

def analisar_jogo(jogo: list[int]) -> dict:
    """
    Analisa um jogo contra todos os criterios.
    Nao exclui — apenas classifica e explica.
    """
    soma_ok,  d_soma  = _soma(jogo)
    cons_ok,  d_cons  = _consecutivos(jogo)
    par_ok,   d_par   = _paridade(jogo)
    lin_ok,   d_lin   = _linhas(jogo)

    alertas = []
    if not soma_ok:   alertas.append(f"Soma incomum ({d_soma})")
    if not cons_ok:   alertas.append(f"Muitas consecutivas ({d_cons})")
    if not par_ok:    alertas.append(f"Paridade incomum ({d_par})")
    if not lin_ok:    alertas.append(f"Linhas desbalanceadas ({d_lin})")

    n_ok = sum([soma_ok, cons_ok, par_ok, lin_ok])
    score = int(n_ok / 4 * 100)

    return {
        "dezenas":    jogo,
        "soma":       sum(jogo),
        "pares":      sum(1 for d in jogo if d % 2 == 0),
        "soma_ok":    soma_ok,
        "consec_ok":  cons_ok,
        "par_ok":     par_ok,
        "lin_ok":     lin_ok,
        "n_alertas":  len(alertas),
        "alertas":    alertas,
        "score":      score,
        "padrao":     score == 100,   # True = jogo dentro de todos os padroes
    }


# -- Processar lista de jogos -------------------------------------------------

def filtrar_jogos(
    jogos: list[list[int]],
    modo: str = MODO_AVISO,
) -> tuple[list[list[int]], list[dict]]:
    """
    Processa todos os jogos.

    Parametros
    ----------
    jogos : lista de jogos (cada um e lista de 15 dezenas)
    modo  : MODO_AVISO (mantem todos) ou MODO_FILTRO (exclui improvaveis)

    Retorna
    -------
    (jogos_resultado, relatorio)

    jogos_resultado:
      - MODO_AVISO  : todos os jogos originais (sem exclusao)
      - MODO_FILTRO : apenas jogos que passam em todos os criterios
                      (se nenhum passar, retorna todos e avisa)
    """
    relatorio = []
    aprovados = []

    for i, jogo in enumerate(jogos, 1):
        analise = analisar_jogo(jogo)
        analise["numero"] = i
        analise["aprovado"] = analise["padrao"]
        relatorio.append(analise)
        if analise["padrao"]:
            aprovados.append(jogo)

    if modo == MODO_FILTRO:
        if aprovados:
            return aprovados, relatorio
        else:
            # Nenhum passou — aviso critico, manter todos
            return jogos, relatorio
    else:
        # MODO_AVISO: manter todos, mas relatorio mostra alertas
        return jogos, relatorio


def resumo_filtros(relatorio: list[dict], modo: str = MODO_AVISO) -> str:
    total   = len(relatorio)
    padrao  = sum(1 for r in relatorio if r["padrao"])
    alertas = total - padrao

    linhas = [
        "=" * 62,
        f"  ANALISE DE CONSISTENCIA — MODO: {modo.upper()}",
        "=" * 62,
        f"  Total de jogos     : {total}",
        f"  Dentro do padrao   : {padrao}",
        f"  Com alertas        : {alertas}",
    ]

    if modo == MODO_AVISO:
        linhas += [
            "",
            "  TODOS OS JOGOS MANTIDOS.",
            "  Alertas indicam jogos incomuns, nao impossíveis.",
            "  A combinacao premiada pode ser qualquer uma.",
        ]
    else:
        linhas += [
            "",
            f"  Jogos retidos apos filtro: {padrao if padrao else total}",
        ]
        if padrao == 0:
            linhas.append("  AVISO: Nenhum jogo passou — mantendo todos.")

    # Mostrar jogos com alertas
    com_alertas = [r for r in relatorio if not r["padrao"]]
    if com_alertas:
        linhas += ["", "  Jogos com alertas:"]
        for r in com_alertas[:8]:
            linhas.append(f"    Jogo {r['numero']:02d}: " +
                          " | ".join(r["alertas"]))
        if len(com_alertas) > 8:
            linhas.append(f"    ... e mais {len(com_alertas)-8} jogos com alertas")

    linhas += [
        "",
        "  NOTA: Filtros estatisticos nao aumentam nem diminuem",
        "  a probabilidade matematica de cada combinacao.",
        "=" * 62,
    ]
    return "\n".join(linhas)
