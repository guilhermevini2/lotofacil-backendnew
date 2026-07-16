"""
acumulacao.py - Alerta de concursos acumulados via API da Caixa.
"""

from config import ACUMULACAO_MINIMA
from api import _fetch_latest, _valor_brl


def verificar_acumulacao():
    """
    Consulta o ultimo concurso (Caixa, com fallback para espelhos) e
    retorna informacoes de acumulacao.
    """
    try:
        data = _fetch_latest()

        acumulou       = data.get("acumulou", False)
        # Formato Caixa: valores numericos diretos.
        # Formato espelho: strings tipo "R$ 1.500.000,00" e sem valorEstimado.
        valor_acum     = _valor_brl(data.get("valorAcumuladoProximoConcurso", 0))
        valor_estimado = _valor_brl(data.get("valorEstimadoProximoConcurso", 0))
        numero         = data.get("numero") or data.get("concurso", 0)
        data_prox      = data.get("dataProximoConcurso") or data.get("dataProxConcurso", "")

        alerta = acumulou and (valor_acum >= ACUMULACAO_MINIMA or valor_estimado >= ACUMULACAO_MINIMA)

        return {
            "ok":              True,
            "concurso_atual":  numero,
            "acumulou":        acumulou,
            "valor_acumulado": valor_acum,
            "valor_estimado":  valor_estimado,
            "data_proximo":    data_prox,
            "alerta":          alerta,
        }
    except Exception as exc:
        return {"ok": False, "erro": str(exc)}


def resumo_acumulacao(info):
    if not info.get("ok"):
        return f"  AVISO: Nao foi possivel verificar acumulacao: {info.get('erro')}"

    linhas = [
        "=" * 55,
        "  SITUACAO DO PROXIMO CONCURSO",
        "=" * 55,
        f"  Ultimo concurso    : {info['concurso_atual']}",
        f"  Acumulou           : {'SIM' if info['acumulou'] else 'NAO'}",
        f"  Proximo concurso   : {info['data_proximo']}",
    ]
    if info["valor_acumulado"]:
        linhas.append(f"  Valor acumulado    : R$ {info['valor_acumulado']:,.2f}")
    if info["valor_estimado"]:
        linhas.append(f"  Premio estimado    : R$ {info['valor_estimado']:,.2f}")
    if info["alerta"]:
        linhas += [
            "",
            "  *** ALERTA: Premio acumulado acima do limite! ***",
            f"  Premio estimado acima de R$ {ACUMULACAO_MINIMA:,.0f}",
            "  Momento mais favoravel para jogar.",
        ]
    linhas.append("=" * 55)
    return "\n".join(linhas)
