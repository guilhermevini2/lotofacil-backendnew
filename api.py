"""
api.py - Download com retry, cache e alerta de acumulacao.
"""

import json
import re
import time
from pathlib import Path
import requests
from config import (
    API_BASE, API_TIMEOUT, API_RETRY_MAX,
    API_RETRY_DELAY, API_SLEEP, CACHE_DIR,
)

# -- Headers de navegador -------------------------------------------------------
# A Caixa bloqueia (403) requisicoes vindas de IPs de datacenter (Render, Railway,
# AWS, etc.) e/ou sem cara de navegador. Enviar headers completos ajuda, mas nao
# elimina o bloqueio por IP — por isso o fallback para APIs espelho abaixo.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://loterias.caixa.gov.br/",
    "Accept": "application/json, text/plain, */*",
}

# -- APIs espelho (fallback) -----------------------------------------------------
# Usadas quando a Caixa responde 403/erro (comum em hosts de nuvem como o Render).
# Mesma familia de projeto (loteriascaixa-api), com espelhos redundantes.
MIRRORS = [
    "https://loteriascaixa-api.herokuapp.com/api/lotofacil",
    "https://loterias-gutotech.herokuapp.com/api/lotofacil",
]


# -- Circuit breaker -------------------------------------------------------------
# Um 403 da Caixa e bloqueio de IP, nao falha passageira: tentar de novo no mesmo
# processo so desperdica tempo (e trava a requisicao HTTP do frontend ate dar
# timeout). Assim que a Caixa falhar uma vez, o processo para de tentar nela e
# vai direto para os espelhos pelo resto da execucao.
_caixa_disponivel = True


def _is_403(exc):
    return isinstance(exc, requests.exceptions.HTTPError) and getattr(exc.response, "status_code", None) == 403


def _cache_path(numero):
    return CACHE_DIR / f"{numero}.json"


def _get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _fetch_one(numero):
    """Busca um concurso especifico, tentando a Caixa e depois os espelhos."""
    global _caixa_disponivel

    fontes = []
    if _caixa_disponivel:
        fontes.append(("Caixa (oficial)", f"{API_BASE}/{numero}"))
    fontes += [(f"espelho {i+1}", f"{m}/{numero}") for i, m in enumerate(MIRRORS)]

    ultimo_erro = None
    for nome_fonte, url in fontes:
        for attempt in range(1, API_RETRY_MAX + 1):
            try:
                return _get_json(url)
            except Exception as exc:
                ultimo_erro = exc
                if nome_fonte == "Caixa (oficial)" and _is_403(exc):
                    # Bloqueio de IP: nao adianta tentar de novo, nem em outros
                    # concursos nesta mesma execucao. Desativa e ja pula pro espelho.
                    print(f"    AVISO: Caixa bloqueou o IP (403). Desativando Caixa para o resto desta execucao.")
                    _caixa_disponivel = False
                    break
                if attempt == API_RETRY_MAX:
                    print(f"    AVISO: {nome_fonte} falhou apos {API_RETRY_MAX} tentativas: {exc}")
                    break
                wait = API_RETRY_DELAY * attempt
                print(f"    AVISO: {nome_fonte} tentativa {attempt}/{API_RETRY_MAX} falhou. Aguardando {wait:.1f}s...")
                time.sleep(wait)

    raise RuntimeError(f"Concurso {numero} falhou em todas as fontes (Caixa + espelhos): {ultimo_erro}")


def _fetch_latest():
    """Busca o ultimo concurso, tentando a Caixa e depois os espelhos."""
    global _caixa_disponivel

    fontes = []
    if _caixa_disponivel:
        fontes.append(("Caixa (oficial)", API_BASE))
    fontes += [(f"espelho {i+1}", f"{m}/latest") for i, m in enumerate(MIRRORS)]

    ultimo_erro = None
    for nome_fonte, url in fontes:
        try:
            return _get_json(url)
        except Exception as exc:
            ultimo_erro = exc
            if nome_fonte == "Caixa (oficial)" and _is_403(exc):
                print(f"    AVISO: Caixa bloqueou o IP (403). Desativando Caixa para o resto desta execucao.")
                _caixa_disponivel = False
            else:
                print(f"    AVISO: {nome_fonte} falhou ao buscar ultimo concurso: {exc}")
            continue

    raise RuntimeError(f"Nao foi possivel obter o ultimo concurso em nenhuma fonte (Caixa + espelhos): {ultimo_erro}")


def _valor_brl(valor):
    """Converte valores em formato 'R$ 1.500.000,00' (espelhos) ou numerico (Caixa) para float."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if not valor:
        return 0.0
    limpo = re.sub(r"[^\d,]", "", str(valor)).replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def _parse(raw):
    # Formato oficial da Caixa (servicebus2.caixa.gov.br)
    if "dezenasSorteadasOrdemSorteio" in raw:
        return {
            "concurso":         raw["numero"],
            "data":             raw.get("dataApuracao", ""),
            "dezenas":          sorted(int(d) for d in raw["dezenasSorteadasOrdemSorteio"]),
            "acumulou":         raw.get("acumulado", False),
            "valor_acumulado":  raw.get("valorAcumuladoProximoConcurso", 0),
            "arrecadacao":      raw.get("valorArrecadado", 0),
            "premio_maximo":    raw.get("premioMaximoVal", 0),
        }
    # Formato das APIs espelho (loteriascaixa-api e forks)
    return {
        "concurso":         raw["concurso"],
        "data":             raw.get("data", ""),
        "dezenas":          sorted(int(d) for d in raw["dezenas"]),
        "acumulou":         raw.get("acumulou", False),
        "valor_acumulado":  _valor_brl(raw.get("acumuladaProxConcurso", 0)),
        "arrecadacao":      _valor_brl(raw.get("valorArrecadado", 0)),
        "premio_maximo":    _valor_brl(raw.get("premioMaximoVal", 0)),
    }


def ultimo_concurso():
    """Retorna apenas o numero (int) do ultimo concurso disponivel."""
    raw = _fetch_latest()
    return int(raw.get("numero") or raw.get("concurso"))


def ultimo_concurso_completo():
    """Retorna (numero, dados_parseados) do ultimo concurso."""
    raw = _fetch_latest()
    dados = _parse(raw)
    return dados["concurso"], dados


def buscar_concurso(numero, forcar=False):
    path = _cache_path(numero)
    if not forcar and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raw = _fetch_one(numero)
    dados = _parse(raw)
    path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def buscar_intervalo(inicio, fim, forcar=False):
    total = fim - inicio + 1
    resultado = []
    novos = 0
    print(f"\n[DOWN] Coletando {total} concursos ({inicio} -> {fim})...\n")
    for idx, numero in enumerate(range(inicio, fim + 1), 1):
        cached = _cache_path(numero).exists() and not forcar
        try:
            dados = buscar_concurso(numero, forcar=forcar)
            resultado.append(dados)
            status = "cache" if cached else "download"
            print(f"  [{idx:03d}/{total}]  #{numero}  {dados['data']}  [{status}]")
            if not cached:
                novos += 1
                time.sleep(API_SLEEP)
        except RuntimeError as exc:
            print(f"  [{idx:03d}/{total}]  #{numero}  ERRO: {exc}")

    print(f"\nOK: {len(resultado)} concursos carregados  |  {novos} novos downloads\n")
    return resultado


def atualizar(inicio):
    num = ultimo_concurso()
    return buscar_intervalo(inicio, num)


def alerta_acumulacao(ultimo_dados: dict) -> str:
    """Gera alerta se o proximo concurso estiver acumulado."""
    if not ultimo_dados.get("acumulou"):
        return ""
    val = ultimo_dados.get("valor_acumulado", 0)
    if val > 0:
        return (
            f"\n  *** ATENCAO: PROXIMO CONCURSO ACUMULADO ***\n"
            f"  Valor estimado: R$ {val:,.2f}\n"
            f"  Concursos acumulados tendem a ter retorno esperado mais favoravel!\n"
        )
    return "\n  *** ATENCAO: PROXIMO CONCURSO ACUMULADO ***\n"
