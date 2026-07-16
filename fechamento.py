"""
fechamento.py - Geracao dos jogos do fechamento 18-15-14.
"""

from config import INDICES_FECHAMENTO, DEZENAS_SORTEADAS, GRID
from config import FILTRO_SOMA_MIN, FILTRO_SOMA_MAX, FILTRO_MAX_CONSEC
from config import FILTRO_PAR_MIN, FILTRO_PAR_MAX, FILTRO_LINHA_MIN, FILTRO_LINHA_MAX


def gerar_jogos(dezenas_18):
    if len(dezenas_18) != 18:
        raise ValueError(f"Sao necessarias exatamente 18 dezenas (recebido: {len(dezenas_18)})")
    return [sorted(dezenas_18[i - 1] for i in linha) for linha in INDICES_FECHAMENTO]


def jogo_valido(jogo):
    """Retorna (bool, motivo)."""
    s = sum(jogo)
    if not (FILTRO_SOMA_MIN <= s <= FILTRO_SOMA_MAX):
        return False, f"Soma {s} fora de [{FILTRO_SOMA_MIN},{FILTRO_SOMA_MAX}]"

    dezenas = sorted(jogo)
    max_c = atual = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i-1] + 1:
            atual += 1
            max_c = max(max_c, atual)
        else:
            atual = 1
    if max_c > FILTRO_MAX_CONSEC:
        return False, f"{max_c} consecutivos (max {FILTRO_MAX_CONSEC})"

    pares = sum(1 for d in jogo if d % 2 == 0)
    if not (FILTRO_PAR_MIN <= pares <= FILTRO_PAR_MAX):
        return False, f"{pares} pares (fora de [{FILTRO_PAR_MIN},{FILTRO_PAR_MAX}])"

    dist = {}
    for d in jogo:
        l = GRID[d][0]
        dist[l] = dist.get(l, 0) + 1
    for linha in range(1, 6):
        qtd = dist.get(linha, 0)
        if not (FILTRO_LINHA_MIN <= qtd <= FILTRO_LINHA_MAX):
            return False, f"Linha {linha} com {qtd} dezenas"

    return True, ""


def filtrar_jogos(jogos):
    aprovados, relatorio = [], []
    for i, jogo in enumerate(jogos, 1):
        ok, motivo = jogo_valido(jogo)
        pares = sum(1 for d in jogo if d % 2 == 0)
        relatorio.append({
            "jogo": i, "dezenas": jogo, "soma": sum(jogo),
            "pares": pares, "impares": 15 - pares,
            "aprovado": ok, "motivo": motivo,
        })
        if ok:
            aprovados.append(jogo)
    return aprovados, relatorio


def resumo_jogos(jogos, dezenas_18):
    linhas = [
        "=" * 62,
        f"  FECHAMENTO 18-15-14  -  {len(jogos)} jogos",
        "  Pool: " + "  ".join(f"{d:02d}" for d in dezenas_18),
        "=" * 62,
    ]
    for i, jogo in enumerate(jogos, 1):
        ok, motivo = jogo_valido(jogo)
        status = "OK" if ok else f"[FILTRADO: {motivo}]"
        nums = "  ".join(f"{d:02d}" for d in jogo)
        linhas.append(f"  Jogo {i:02d}: {nums}  {status}")
    linhas.append("=" * 62)
    linhas.append("\n  AVISO: Garantia de >=14 pontos SOMENTE se os 15 sorteados")
    linhas.append("  estiverem dentro das 18 dezenas do pool acima.")
    return "\n".join(linhas)


def custo_fechamento(jogos, valor_aposta=3.00):
    return {
        "jogos": len(jogos),
        "valor_por_jogo": valor_aposta,
        "custo_total": round(len(jogos) * valor_aposta, 2),
    }
