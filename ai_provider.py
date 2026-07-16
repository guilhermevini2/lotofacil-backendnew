"""
ai_provider.py — Camada modular de provedores de IA para o LotofacilPro v3.

Objetivo:
  Isolar a "inteligencia externa" (LLM) do resto do sistema atraves de uma
  interface unica `analisar(dados)`. Isso permite trocar o provedor no futuro
  (Puter.js via Node.js, OpenAI, modelo local, etc.) SEM alterar o restante do
  codigo Python.

Arquitetura:
  Provider (abstrato)
    ├─ PuterNodeProvider     -> fala com o servidor Node.js local (porta 3001)
    │                           que por sua vez usa o Puter.js (Claude/GPT/Gemini)
    └─ LocalHeuristicProvider -> fallback 100% Python (sem rede)

  get_provider(nome) -> instancia o provedor desejado
  analisar(dados, ...) -> funcao de conveniencia (usa o provedor padrao +
                          faz fallback automatico para heuristica)

Contrato de dados
  Entrada  (dados): dict com estatisticas consolidadas do pipeline
      {
        "concurso_base": int,
        "estado_mercado": str,
        "ranking": [{"dezena","score","atraso","tendencia"}...],
        "tendencias": {"esquentando":[...],"esfriando":[...],"ciclo":[...]},
        "pares_quentes": [[a,b,count]...],
        "backtest": {"pct_dentro_pool": float},
        "pool_atual": [18 dezenas]
      }
  Saida (dict):
      {
        "ok": bool,
        "provider": "puter" | "heuristic" | "local",
        "model": str | None,
        "pesos": {...},
        "pool_final": [18 dezenas],
        "fechamento": {"tipo": "18-15-14", "jogos": 24},
        "estrategia": {"perfil","confianca","resumo","explicacao","pontos_chave"}
      }
"""

from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from typing import Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


# ── Configuracao ──────────────────────────────────────────────────────────────

NODE_SERVER_URL = os.environ.get("PUTER_NODE_URL", "http://localhost:3001")
NODE_TIMEOUT    = float(os.environ.get("PUTER_NODE_TIMEOUT", "45"))
# Provedor padrao: "puter" (via Node) — cai para heuristica automaticamente.
DEFAULT_PROVIDER = os.environ.get("AI_PROVIDER", "puter")
DEFAULT_MODEL    = os.environ.get("PUTER_MODEL", "gpt-4o-mini")


# ── Validacao / normalizacao da resposta ──────────────────────────────────────

def _validar_pool(pool) -> Optional[list]:
    """Retorna uma lista de 18 dezenas validas (1-25, unicas) ou None."""
    if not isinstance(pool, (list, tuple)):
        return None
    limpo = []
    vistos = set()
    for x in pool:
        try:
            n = int(x)
        except Exception:
            continue
        if 1 <= n <= 25 and n not in vistos:
            vistos.add(n)
            limpo.append(n)
    if len(limpo) != 18:
        return None
    return sorted(limpo)


def _resposta_valida(resp: dict) -> bool:
    return isinstance(resp, dict) and _validar_pool(resp.get("pool_final")) is not None


# ── Provedor base ──────────────────────────────────────────────────────────────

class Provider(ABC):
    nome = "base"

    @abstractmethod
    def analisar(self, dados: dict, model: Optional[str] = None) -> dict:
        ...

    def disponivel(self) -> bool:
        return True


# ── Provedor Puter.js (via servidor Node.js) ───────────────────────────────────

class PuterNodeProvider(Provider):
    """Envia as estatisticas ao servidor Node.js que orquestra o Puter.js."""

    nome = "puter"

    def __init__(self, base_url: str = NODE_SERVER_URL, timeout: float = NODE_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def disponivel(self) -> bool:
        if requests is None:
            return False
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def analisar(self, dados: dict, model: Optional[str] = None) -> dict:
        if requests is None:
            raise RuntimeError("biblioteca 'requests' indisponivel")
        payload = dict(dados)
        payload["model"] = model or DEFAULT_MODEL
        r = requests.post(
            f"{self.base_url}/api/ai-analyze",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        resp = r.json()
        pool = _validar_pool(resp.get("pool_final"))
        if pool is None:
            raise ValueError("resposta do Node.js sem pool_final valido")
        resp["pool_final"] = pool
        return resp


# ── Provedor heuristico local (fallback 100% Python) ────────────────────────────

class LocalHeuristicProvider(Provider):
    """
    Fallback que NAO depende de rede. Reproduz em Python a mesma logica do
    motor heuristico do Node (construir pool + decidir perfil), garantindo que
    o sistema continue funcionando mesmo sem Node.js/Puter/internet.
    """

    nome = "local"

    def analisar(self, dados: dict, model: Optional[str] = None) -> dict:
        ranking = dados.get("ranking", []) or []
        tend = dados.get("tendencias", {}) or {}
        esquentando = set(tend.get("esquentando", []))
        ciclo = set(tend.get("ciclo", []))
        pct_pool = (dados.get("backtest", {}) or {}).get("pct_dentro_pool", 0) or 0

        ordenado = sorted(ranking, key=lambda r: -(r.get("score") or 0))

        pool, usados = [], set()
        for r in ordenado:
            if len(pool) >= 16:
                break
            d = r.get("dezena")
            if d is not None and d not in usados:
                pool.append(d); usados.add(d)

        atrasadas = sorted(
            [r for r in ordenado if r.get("dezena") not in usados],
            key=lambda r: -(r.get("atraso") or 0),
        )
        for r in atrasadas:
            if len(pool) >= 18:
                break
            pool.append(r["dezena"]); usados.add(r["dezena"])

        for d in range(1, 26):
            if len(pool) >= 18:
                break
            if d not in usados:
                pool.append(d); usados.add(d)

        pool = sorted(pool[:18])

        n_esq = len(tend.get("esquentando", []))
        n_ciclo = len(tend.get("ciclo", []))
        if pct_pool < 25:
            perfil, conf = "conservador", 72
            motivo = ("Cobertura historica baixa nos backtests. Priorizando padroes "
                      "solidos e dezenas de alta frequencia de longo prazo.")
            pesos = {"frequencia":0.4,"atraso":0.15,"tendencia":0.2,"pares_quentes":0.15,"distribuicao":0.1}
        elif n_esq >= 8:
            perfil, conf = "agressivo", 66
            motivo = f"{n_esq} dezenas esquentando. Tendencias recentes fortes favorecem abordagem dinamica."
            pesos = {"frequencia":0.2,"atraso":0.2,"tendencia":0.35,"pares_quentes":0.15,"distribuicao":0.1}
        elif n_ciclo >= 4:
            perfil, conf = "equilibrado", 70
            motivo = f"{n_ciclo} dezenas em ciclo de retorno. Mix de estatistica solida com dezenas atrasadas."
            pesos = {"frequencia":0.3,"atraso":0.18,"tendencia":0.27,"pares_quentes":0.15,"distribuicao":0.1}
        else:
            perfil, conf = "equilibrado", 68
            motivo = "Mercado sem padrao dominante claro. Estrategia balanceada tende a ser a mais robusta."
            pesos = {"frequencia":0.3,"atraso":0.18,"tendencia":0.27,"pares_quentes":0.15,"distribuicao":0.1}

        esq_pool = [d for d in pool if d in esquentando]
        ciclo_pool = [d for d in pool if d in ciclo]

        explicacao = (
            f"Estrategia {perfil.upper()} escolhida (confianca {conf}%). {motivo} "
            f"O pool de 18 dezenas prioriza as de maior score consolidado"
            + (f", incluindo {len(esq_pool)} em alta ({', '.join(map(str, esq_pool[:4]))})" if esq_pool else "")
            + (f" e {len(ciclo_pool)} em ciclo de retorno" if ciclo_pool else "")
            + ". Sobre essas 18 dezenas aplica-se o fechamento 18-15-14 (24 jogos), "
              "com garantia de 14 acertos se as 15 sorteadas estiverem no pool."
        )

        return {
            "ok": True,
            "provider": "local",
            "model": None,
            "motivo_fallback": "Servidor Node.js/Puter.js indisponivel — fallback Python.",
            "pesos": pesos,
            "pool_final": pool,
            "fechamento": {"tipo": "18-15-14", "jogos": 24},
            "estrategia": {
                "perfil": perfil,
                "confianca": conf,
                "resumo": motivo,
                "explicacao": explicacao,
                "pontos_chave": [
                    f"Perfil: {perfil}",
                    f"{len(esq_pool)} dezenas em alta no pool",
                    f"{len(ciclo_pool)} dezenas em ciclo de retorno no pool",
                    "Fechamento 18-15-14 (24 jogos)",
                ],
            },
        }


# ── Fabrica de provedores ───────────────────────────────────────────────────────

_PROVIDERS = {
    "puter": PuterNodeProvider,
    "local": LocalHeuristicProvider,
    "heuristic": LocalHeuristicProvider,
}


def get_provider(nome: Optional[str] = None) -> Provider:
    nome = (nome or DEFAULT_PROVIDER).lower()
    cls = _PROVIDERS.get(nome, PuterNodeProvider)
    return cls()


# ── Interface principal ──────────────────────────────────────────────────────────

def analisar(dados: dict, provider: Optional[str] = None,
             model: Optional[str] = None, verbose: bool = False) -> dict:
    """
    Envia estatisticas para o provedor de IA e retorna a analise estruturada.

    Fluxo:
      1. Tenta o provedor solicitado (padrao: Puter.js via Node.js).
      2. Se falhar (rede/timeout/JSON invalido), cai para o heuristico local.
      3. Garante sempre um pool_final valido de 18 dezenas.
    """
    provider_nome = (provider or DEFAULT_PROVIDER).lower()

    # Fallback direto se for pedido o local/heuristico.
    if provider_nome in ("local", "heuristic"):
        return LocalHeuristicProvider().analisar(dados, model)

    prov = get_provider(provider_nome)
    try:
        if verbose:
            print(f"  [ai_provider] Tentando provedor '{prov.nome}' em {NODE_SERVER_URL}...")
        resp = prov.analisar(dados, model)
        if not _resposta_valida(resp):
            raise ValueError("resposta do provedor invalida")
        if verbose:
            print(f"  [ai_provider] OK via '{resp.get('provider', prov.nome)}'.")
        return resp
    except Exception as exc:
        if verbose:
            print(f"  [ai_provider] Provedor '{prov.nome}' falhou: {exc}. Fallback local.")
        resp = LocalHeuristicProvider().analisar(dados, model)
        resp["motivo_fallback"] = f"{prov.nome} indisponivel: {exc}"
        return resp


# ── Helper: montar 'dados' a partir do payload do pipeline ───────────────────────

def montar_dados_para_ia(resultado: dict) -> dict:
    """
    Converte o payload completo de /api/resultado (ou do pipeline) no formato
    enxuto esperado pela IA. Mantido aqui para reutilizacao em servidor.py.
    """
    ranking = []
    for r in (resultado.get("ranking") or [])[:25]:
        ranking.append({
            "dezena":    r.get("dezena"),
            "score":     r.get("score", 0),
            "atraso":    r.get("atraso", 0),
            "tendencia": r.get("label_tend") or r.get("tendencia") or "NEUTRO",
        })

    # Tendencias a partir do bloco hibrido, se existir.
    esquentando, esfriando, ciclo = [], [], []
    hib = resultado.get("hibrido") or {}
    for t in (hib.get("tendencias") or []):
        tend = (t.get("tendencia") or "").upper()
        d = t.get("dezena")
        if "ESQUENT" in tend:
            esquentando.append(d)
        elif "ESFRI" in tend:
            esfriando.append(d)
        elif "CICLO" in tend:
            ciclo.append(d)

    pares = [[p["a"], p["b"], p["count"]] for p in (resultado.get("pares_quentes") or [])[:12]]

    return {
        "concurso_base": resultado.get("ultimo_concurso"),
        "estado_mercado": (resultado.get("ai") or {}).get("estado_mercado", ""),
        "ranking": ranking,
        "tendencias": {"esquentando": esquentando, "esfriando": esfriando, "ciclo": ciclo},
        "pares_quentes": pares,
        "backtest": {"pct_dentro_pool": (resultado.get("backtest") or {}).get("pct_dentro_pool", 0)},
        "pool_atual": resultado.get("dezenas_18") or [],
    }


if __name__ == "__main__":
    # Teste rapido standalone.
    exemplo = {
        "concurso_base": 3600, "estado_mercado": "AQUECIDO",
        "ranking": [{"dezena": d, "score": 90 - d, "atraso": d % 7,
                     "tendencia": "ESQUENTANDO" if d < 5 else "NEUTRO"} for d in range(1, 26)],
        "tendencias": {"esquentando": [1, 2, 3, 4], "esfriando": [20, 21], "ciclo": [10, 11, 12, 13]},
        "pares_quentes": [[1, 2, 40], [3, 4, 35]],
        "backtest": {"pct_dentro_pool": 42.0},
        "pool_atual": list(range(1, 19)),
    }
    out = analisar(exemplo, verbose=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
