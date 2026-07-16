"""
chat_engine.py - Chat contextual do LotofacilPro v4.

Permite ao usuario fazer perguntas sobre os dados atuais do sistema
diretamente na interface. O contexto (resultados, pool, jogos) e
automaticamente incluido em cada mensagem.

Usa o ai_provider.py como camada de IA (Puter.js ou fallback).
O historico da conversa e mantido em memoria durante a sessao.
"""

import json
import time
from pathlib import Path
from config import BASE_DIR

CHAT_LOG = BASE_DIR / "cache" / "chat_log.json"

# Contexto do sistema enviado em cada mensagem
SYSTEM_CHAT = """Voce e um assistente especialista na Lotofacil brasileira integrado ao sistema LotofacilPro v4.

Voce tem acesso ao contexto atual do sistema (estatisticas, pool selecionado, jogos gerados, backtest).
Responda de forma clara e objetiva em portugues. Seja direto — o usuario esta no celular.

REGRAS:
- Use os dados do contexto para fundamentar suas respostas
- Nunca invente dados que nao estejam no contexto
- Se nao souber algo, diga claramente
- Respostas curtas (maximo 4 paragrafos)
- Pode usar numeros e listas quando ajudar
- Lembre que nenhum sistema pode prever resultados de loteria"""


def _resumo_contexto(resultado: dict) -> str:
    """Monta um resumo do estado atual do sistema para incluir no contexto."""
    if not resultado:
        return "Nenhuma analise executada ainda."

    pool = resultado.get("dezenas_18", [])
    jogos = resultado.get("jogos", [])
    bt = resultado.get("backtest", {})
    ai = resultado.get("ai", {})
    pi = resultado.get("pool_inteligente", {})

    linhas = [
        f"=== CONTEXTO DO SISTEMA ===",
        f"Concursos analisados: {resultado.get('concursos_total', 0)}",
        f"Periodo: {resultado.get('periodo_inicio','')} a {resultado.get('periodo_fim','')}",
        f"Pool de 18 dezenas: {' '.join(str(d).zfill(2) for d in pool)}",
        f"Qualidade do pool: {pi.get('score_qualidade', 0)}/100",
        f"Jogos gerados: {len(jogos)}",
        f"Cobertura historica (backtest): {bt.get('pct_dentro_pool', 0):.1f}%",
    ]

    if ai and ai.get("disponivel"):
        linhas += [
            f"AI Engine — Estado: {ai.get('estado_mercado', '?')}",
            f"AI Engine — Estrategia: {ai.get('estrategia_perfil', '?')} "
            f"(confianca {ai.get('estrategia_confianca', 0):.0f}%)",
        ]

    faixas = bt.get("faixas", {})
    if faixas:
        linhas.append(
            f"Backtest faixas: 15pts={faixas.get('15',0)} "
            f"14pts={faixas.get('14',0)} "
            f"13pts={faixas.get('13',0)}"
        )

    if resultado.get("ai_explicacao_puter"):
        linhas.append(f"Ultima analise IA: {resultado['ai_explicacao_puter'][:200]}")

    return "\n".join(linhas)


class ChatEngine:
    """Gerencia o historico e envia mensagens para o provedor de IA."""

    def __init__(self, resultado_atual: dict = None):
        self.historico: list[dict] = []
        self.resultado = resultado_atual or {}
        self._carregar_log()

    def _carregar_log(self):
        if CHAT_LOG.exists():
            try:
                dados = json.loads(CHAT_LOG.read_text(encoding="utf-8"))
                # Manter apenas as ultimas 20 mensagens da sessao anterior
                self.historico = dados.get("historico", [])[-20:]
            except Exception:
                self.historico = []

    def _salvar_log(self):
        CHAT_LOG.parent.mkdir(exist_ok=True)
        CHAT_LOG.write_text(
            json.dumps({"historico": self.historico[-50:]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def atualizar_contexto(self, resultado: dict):
        self.resultado = resultado

    def enviar(self, mensagem_usuario: str, provider: str = None) -> dict:
        """
        Envia uma mensagem e retorna a resposta da IA.

        Retorna:
          {ok, resposta, provider, timestamp, erro}
        """
        # Montar prompt com contexto
        contexto = _resumo_contexto(self.resultado)
        prompt_completo = f"{contexto}\n\n=== PERGUNTA DO USUARIO ===\n{mensagem_usuario}"

        # Adicionar historico recente (últimas 6 trocas)
        hist_txt = ""
        for msg in self.historico[-6:]:
            hist_txt += f"Usuario: {msg['usuario']}\nAssistente: {msg['resposta']}\n\n"
        if hist_txt:
            prompt_completo = (
                f"{contexto}\n\n=== HISTORICO RECENTE ===\n{hist_txt}"
                f"=== PERGUNTA ATUAL ===\n{mensagem_usuario}"
            )

        try:
            from ai_provider import get_provider
            prov = get_provider(provider or "puter")

            # Para o chat, usar o provider diretamente com system prompt
            if hasattr(prov, 'base_url'):
                # PuterNodeProvider — envia via Node
                import requests as req
                payload = {
                    "mensagem": mensagem_usuario,
                    "contexto": contexto,
                    "historico": self.historico[-6:],
                    "system":   SYSTEM_CHAT,
                    "tipo":     "chat",
                }
                r = req.post(
                    f"{prov.base_url}/api/chat",
                    json=payload, timeout=30,
                )
                if r.status_code == 200:
                    resposta_txt = r.json().get("resposta", "")
                    provider_usado = "puter"
                else:
                    raise Exception(f"Node retornou {r.status_code}")
            else:
                # Fallback local — resposta simples baseada no contexto
                resposta_txt = _resposta_local(mensagem_usuario, self.resultado)
                provider_usado = "local"

        except Exception as exc:
            resposta_txt = _resposta_local(mensagem_usuario, self.resultado)
            provider_usado = "local"

        # Salvar no historico
        entrada = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "usuario":   mensagem_usuario,
            "resposta":  resposta_txt,
            "provider":  provider_usado,
        }
        self.historico.append(entrada)
        self._salvar_log()

        return {
            "ok":        True,
            "resposta":  resposta_txt,
            "provider":  provider_usado,
            "timestamp": entrada["timestamp"],
        }

    def limpar_historico(self):
        self.historico = []
        self._salvar_log()


# -- Respostas locais (fallback sem IA) ----------------------------------------

def _resposta_local(pergunta: str, resultado: dict) -> str:
    """Resposta baseada em regras simples quando a IA nao esta disponivel."""
    p = pergunta.lower()
    pool = resultado.get("dezenas_18", [])
    bt = resultado.get("backtest", {})
    jogos = resultado.get("jogos", [])

    if any(w in p for w in ["pool", "dezenas", "escolhidas", "selecionadas"]):
        return (f"O pool atual tem {len(pool)} dezenas: "
                + " ".join(str(d).zfill(2) for d in pool)
                + f". Qualidade: {resultado.get('pool_inteligente',{}).get('score_qualidade',0)}/100.")

    if any(w in p for w in ["jogo", "jogos", "fechar", "fechamento"]):
        return (f"Foram gerados {len(jogos)} jogos pelo fechamento 18-15-14. "
                "A garantia de 14 pontos e valida se os 15 sorteados estiverem "
                "dentro do pool de 18 dezenas.")

    if any(w in p for w in ["backtest", "cobertura", "historico"]):
        pct = bt.get("pct_dentro_pool", 0)
        return (f"A cobertura historica do backtest e de {pct:.1f}%. "
                "Isso significa que em {pct:.1f}% dos concursos testados, "
                "todos os 15 sorteados caiam dentro do pool de 18 dezenas.")

    if any(w in p for w in ["custo", "valor", "preco", "quanto"]):
        custo = resultado.get("custo_total", 0)
        return f"O custo total dos {len(jogos)} jogos e R$ {custo:.2f} (R$ 3,00 por jogo)."

    if any(w in p for w in ["estrategia", "perfil", "recomenda"]):
        ai = resultado.get("ai", {})
        if ai and ai.get("disponivel"):
            return (f"A IA recomendou o perfil {ai.get('estrategia_perfil','?').upper()} "
                    f"com {ai.get('estrategia_confianca',0):.0f}% de confianca. "
                    f"Motivo: {ai.get('estrategia_motivo','nao disponivel')}")
        return "Execute a analise completa para obter uma recomendacao de estrategia."

    return ("Nao consegui conectar ao servidor de IA para responder essa pergunta. "
            "O sistema continua funcionando normalmente. "
            "Tente novamente quando o servidor Node.js estiver ativo.")


# Instancia global — compartilhada entre sessoes do servidor Flask
_chat_global = ChatEngine()


def get_chat() -> ChatEngine:
    return _chat_global
