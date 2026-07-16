"""
ai_engine.py - AI Engine: diretor tecnico do LotofacilPro v3.

O AI Engine coordena todo o pipeline de decisao e age como um
"analista especialista" que:

  1. Recebe todas as informacoes do sistema (estatisticas, tendencias,
     scores hibridos, ML, backtest, historico de pesos)
  2. Avalia o estado atual de cada dezena com visao holistica
  3. Decide qual estrategia aplicar (conservadora/equilibrada/agressiva)
     baseado no desempenho recente dos backtests
  4. Escolhe o melhor fechamento para a situacao atual
  5. Classifica os 24 jogos por nivel de confianca
  6. Explica cada decisao em linguagem clara
  7. Aprende continuamente — ajusta sua propria estrategia com base
     nos resultados reais

Arquitetura:
  AIEngine.analisar() -> AnaliseCompleta
    - estado_mercado: tendencias dominantes no momento
    - estrategia: qual perfil escolher e por que
    - pool_recomendado: as 18 dezenas com justificativa
    - jogos_rankeados: os 24 jogos ordenados por confianca
    - explicacao: texto legivel para o usuario
    - alertas: avisos importantes
"""

import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

from config import (
    BASE_DIR, TOTAL_DEZENAS, DEZENAS_SORTEADAS,
    FILTRO_SOMA_MIN, FILTRO_SOMA_MAX,
)

AI_ENGINE_LOG  = BASE_DIR / "cache" / "ai_engine_log.json"
AI_ENGINE_META = BASE_DIR / "cache" / "ai_engine_meta.json"


# ── Integracao com provedor de IA externo (Puter.js via Node.js) ───────────────
# A camada de provedores fica isolada em ai_provider.py para permitir troca de
# provedor no futuro (Puter.js, OpenAI, modelo local) sem alterar este arquivo.
try:
    import ai_provider  # noqa: F401
    HAS_AI_PROVIDER = True
except Exception:
    HAS_AI_PROVIDER = False


def analisar_inteligente(dados: dict, provider: str = None,
                         model: str = None, verbose: bool = False) -> dict:
    """
    Ponte modular para a IA externa (Puter.js / OpenAI / local).

    Recebe as estatisticas ja consolidadas (dict) e delega a decisao de
    pesos/pool/estrategia ao provedor configurado, com fallback automatico
    para a heuristica local. Mantem `analisar(...)` (o pipeline classico
    baseado em regras) totalmente intacto.

    Retorna dict com: pesos, pool_final (18 dezenas), fechamento, estrategia.
    """
    if not HAS_AI_PROVIDER:
        raise RuntimeError("ai_provider indisponivel")
    return ai_provider.analisar(dados, provider=provider, model=model, verbose=verbose)


# ── Estruturas de dados ───────────────────────────────────────────────────────

@dataclass
class DecisaoEstrategia:
    perfil: str            # conservador | equilibrado | agressivo
    confianca: float       # 0-100
    motivo: str
    dados_suporte: dict = field(default_factory=dict)


@dataclass
class AvaliacaoJogo:
    numero: int
    dezenas: list
    score_confianca: float    # 0-100
    nivel: str                # ALTA | MEDIA | BAIXA
    soma: int
    pares: int
    alertas: list
    explicacao: str


@dataclass
class AnaliseCompleta:
    timestamp: str
    concurso_base: int
    estado_mercado: str
    estrategia: DecisaoEstrategia
    pool_recomendado: list
    pool_score_qualidade: int
    jogos_rankeados: list
    n_jogos_alta_confianca: int
    n_jogos_media_confianca: int
    n_jogos_baixa_confianca: int
    explicacao_geral: str
    alertas: list
    desempenho_recente: dict


# ── Avaliador de estado do mercado ────────────────────────────────────────────

def _avaliar_estado_mercado(clasf: list[dict], bt_result: dict) -> str:
    """
    Classifica o 'estado do mercado' dos sorteios recentes.
    Retorna uma descricao do padrao atual.
    """
    esq = sum(1 for c in clasf if c['tendencia'] == 'ESQUENTANDO')
    esf = sum(1 for c in clasf if c['tendencia'] == 'ESFRIANDO')
    cic = sum(1 for c in clasf if c['tendencia'] == 'CICLO_RETORNO')
    pct_pool = bt_result.get('pct_dentro_pool', 0)

    if esq >= 10:
        return "AQUECIDO — muitas dezenas em alta frequencia recente"
    elif esf >= 10:
        return "FRIO — muitas dezenas perdendo frequencia recente"
    elif cic >= 5:
        return "CICLICO — varias dezenas prontas para retornar"
    elif pct_pool >= 40:
        return "FAVORAVEL — pool cobrindo bem os sorteios recentes"
    elif pct_pool < 20:
        return "DESAFIADOR — pool com baixa cobertura recente"
    else:
        return "NEUTRO — sem padrao dominante claro"


# ── Seletor de estrategia ─────────────────────────────────────────────────────

def _escolher_estrategia(
    bt_fixo: dict,
    bt_din: dict,
    clasf: list[dict],
    historico_engine: list[dict],
) -> DecisaoEstrategia:
    """
    Decide qual perfil usar baseado em:
    - Desempenho recente dos backtests
    - Estado das tendencias
    - Historico de decisoes anteriores do AI Engine
    """
    pct_fixo = bt_fixo.get('pct_dentro_pool', 0)
    pct_din  = bt_din.get('pct_dentro_pool', 0) if 'erro' not in bt_din else pct_fixo

    hits_fixo = sum(
        v for k, v in bt_fixo.get('faixas', {}).items()
        if k in (14, 15) or k == '14' or k == '15'
    )

    esq = sum(1 for c in clasf if c['tendencia'] == 'ESQUENTANDO')
    cic = sum(1 for c in clasf if c['tendencia'] == 'CICLO_RETORNO')

    # Verificar se estrategia agressiva funcionou bem no historico
    hist_agressivo_ok = False
    if historico_engine:
        ultimas = historico_engine[-5:]
        agressivos = [h for h in ultimas if h.get('perfil') == 'agressivo']
        if agressivos:
            med_cob = np.mean([h.get('pct_cobertura', 0) for h in agressivos])
            hist_agressivo_ok = med_cob > 30

    # Logica de decisao
    if pct_din < 25 and pct_fixo < 25:
        perfil = "conservador"
        confianca = 72.0
        motivo = (f"Cobertura historica baixa ({pct_din:.1f}%). "
                  "Priorizando padroes solidos de longo prazo.")
    elif esq >= 8 or hist_agressivo_ok:
        perfil = "agressivo"
        confianca = 65.0
        motivo = (f"{esq} dezenas esquentando. "
                  "Tendencias recentes fortes favorecem abordagem dinamica.")
    elif cic >= 4:
        perfil = "equilibrado"
        confianca = 70.0
        motivo = (f"{cic} dezenas em ciclo de retorno. "
                  "Mix de estatistica solida com dezenas atrasadas.")
    else:
        perfil = "equilibrado"
        confianca = 68.0
        motivo = "Mercado sem padrao dominante. Estrategia balanceada otima."

    return DecisaoEstrategia(
        perfil=perfil,
        confianca=confianca,
        motivo=motivo,
        dados_suporte={
            'pct_cobertura_fixo': pct_fixo,
            'pct_cobertura_din':  pct_din,
            'dezenas_esquentando': esq,
            'dezenas_ciclo':       cic,
        },
    )


# ── Rankeador de jogos ────────────────────────────────────────────────────────

def _score_jogo(
    jogo: list[int],
    pool_set: set,
    clasf_map: dict,
    pares_set: set,
    historico: list[list[int]],
) -> float:
    """
    Calcula score de confianca (0-100) para um jogo especifico.
    Considera:
    - Quantas dezenas do jogo estao "esquentando"
    - Quantas estao em ciclo de retorno
    - Se a soma esta na faixa historica ideal
    - Quantos pares quentes estao representados
    - Paridade e distribuicao
    """
    score = 50.0  # base neutra

    # Bonus por dezenas esquentando
    esq = sum(1 for d in jogo
              if clasf_map.get(d, {}).get('tendencia') == 'ESQUENTANDO')
    cic = sum(1 for d in jogo
              if clasf_map.get(d, {}).get('tendencia') == 'CICLO_RETORNO')
    score += esq * 2.5 + cic * 2.0

    # Bonus por pares quentes representados
    pares_no_jogo = sum(
        1 for i in range(len(jogo))
        for j in range(i+1, len(jogo))
        if (jogo[i], jogo[j]) in pares_set
    )
    score += min(pares_no_jogo * 1.5, 12.0)

    # Bonus por soma na faixa ideal
    soma = sum(jogo)
    soma_ideal = (FILTRO_SOMA_MIN + FILTRO_SOMA_MAX) / 2
    dist_soma = abs(soma - soma_ideal) / soma_ideal
    score += max(0, 8.0 - dist_soma * 30)

    # Bonus por paridade equilibrada
    pares_count = sum(1 for d in jogo if d % 2 == 0)
    if 6 <= pares_count <= 9:
        score += 5.0

    # Penalizacao por muitas dezenas esfriando
    esf = sum(1 for d in jogo
              if clasf_map.get(d, {}).get('tendencia') == 'ESFRIANDO')
    score -= esf * 1.5

    # Penalizacao por sequencias longas
    dezenas = sorted(jogo)
    max_seq = atual = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i-1] + 1:
            atual += 1; max_seq = max(max_seq, atual)
        else:
            atual = 1
    if max_seq > 4:
        score -= (max_seq - 4) * 3.0

    return round(min(max(score, 0), 100), 1)


def _nivel_confianca(score: float) -> str:
    if score >= 68:   return "ALTA"
    if score >= 52:   return "MEDIA"
    return "BAIXA"


def _explicar_jogo(jogo: list[int], score: float, clasf_map: dict) -> str:
    esq = [d for d in jogo if clasf_map.get(d,{}).get('tendencia')=='ESQUENTANDO']
    cic = [d for d in jogo if clasf_map.get(d,{}).get('tendencia')=='CICLO_RETORNO']
    partes = []
    if esq: partes.append(f"{len(esq)} dezenas em alta ({', '.join(str(d) for d in esq[:3])})")
    if cic: partes.append(f"{len(cic)} em ciclo de retorno")
    soma = sum(jogo)
    partes.append(f"soma={soma}")
    return " | ".join(partes) if partes else "combinacao balanceada"


def _rankear_jogos(
    jogos: list[list[int]],
    clasf: list[dict],
    pares_quentes: list[tuple],
    historico: list[list[int]],
) -> list[AvaliacaoJogo]:
    clasf_map = {c['dezena']: c for c in clasf}
    pool_set  = set(d for jogo in jogos for d in jogo)

    # Top pares quentes como set de tuplas (a,b)
    pares_set = {(a, b) for a, b, _ in pares_quentes[:20]}

    avaliacoes = []
    for i, jogo in enumerate(jogos, 1):
        score = _score_jogo(jogo, pool_set, clasf_map, pares_set, historico)
        nivel = _nivel_confianca(score)
        soma  = sum(jogo)
        pares_c = sum(1 for d in jogo if d % 2 == 0)

        alertas = []
        if soma < FILTRO_SOMA_MIN:
            alertas.append(f"Soma baixa ({soma})")
        elif soma > FILTRO_SOMA_MAX:
            alertas.append(f"Soma alta ({soma})")

        dezenas = sorted(jogo)
        max_seq = atual = 1
        for k in range(1, len(dezenas)):
            if dezenas[k] == dezenas[k-1] + 1:
                atual += 1; max_seq = max(max_seq, atual)
            else: atual = 1
        if max_seq > 4:
            alertas.append(f"{max_seq} consecutivas")

        avaliacoes.append(AvaliacaoJogo(
            numero=i,
            dezenas=jogo,
            score_confianca=score,
            nivel=nivel,
            soma=soma,
            pares=pares_c,
            alertas=alertas,
            explicacao=_explicar_jogo(jogo, score, clasf_map),
        ))

    # Ordenar por score decrescente
    avaliacoes.sort(key=lambda x: -x.score_confianca)
    return avaliacoes


# ── Explicacao geral ──────────────────────────────────────────────────────────

def _gerar_explicacao(
    estado: str,
    estrategia: DecisaoEstrategia,
    pool: list[int],
    val_pool: dict,
    avaliacoes: list[AvaliacaoJogo],
    clasf: list[dict],
) -> str:
    alta  = sum(1 for a in avaliacoes if a.nivel == 'ALTA')
    media = sum(1 for a in avaliacoes if a.nivel == 'MEDIA')
    baixa = sum(1 for a in avaliacoes if a.nivel == 'BAIXA')

    top3 = avaliacoes[:3]
    top3_nums = [f"Jogo {a.numero}" for a in top3]

    clasf_map = {c['dezena']: c for c in clasf}
    esq_pool = [d for d in pool if clasf_map.get(d,{}).get('tendencia')=='ESQUENTANDO']
    cic_pool = [d for d in pool if clasf_map.get(d,{}).get('tendencia')=='CICLO_RETORNO']

    linhas = [
        f"Estado do mercado: {estado}.",
        f"",
        f"Estrategia escolhida: {estrategia.perfil.upper()} "
        f"(confianca {estrategia.confianca:.0f}%).",
        f"Motivo: {estrategia.motivo}",
        f"",
        f"Pool de {len(pool)} dezenas — qualidade {val_pool['score_qualidade']}/100.",
    ]
    if esq_pool:
        linhas.append(f"  Dezenas esquentando no pool: "
                      + " ".join(f"{d:02d}" for d in esq_pool))
    if cic_pool:
        linhas.append(f"  Dezenas em ciclo de retorno: "
                      + " ".join(f"{d:02d}" for d in cic_pool))
    linhas += [
        f"",
        f"Dos {len(avaliacoes)} jogos gerados:",
        f"  {alta} com ALTA confianca, {media} com MEDIA, {baixa} com BAIXA.",
        f"Mais recomendados: {', '.join(top3_nums)}.",
    ]
    return "\n".join(linhas)


# ── Historico de decisoes ─────────────────────────────────────────────────────

def _carregar_historico() -> list:
    if AI_ENGINE_LOG.exists():
        try:
            return json.loads(AI_ENGINE_LOG.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []


def _salvar_historico(historico: list):
    AI_ENGINE_LOG.parent.mkdir(exist_ok=True)
    AI_ENGINE_LOG.write_text(
        json.dumps(historico[-100:], ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


# ── Interface principal ───────────────────────────────────────────────────────

def analisar(
    concursos: list[dict],
    clasf: list[dict],
    rows_h: list[dict],
    pares_quentes: list[tuple],
    bt_fixo: dict,
    bt_din: dict,
    jogos: list[list[int]],
    pool_final: list[int],
    val_pool: dict,
    verbose: bool = True,
) -> AnaliseCompleta:
    """
    Ponto de entrada do AI Engine.
    Recebe todos os dados do pipeline e retorna uma AnaliseCompleta.
    """
    t0 = time.time()
    if verbose:
        print("  [AI Engine] Iniciando analise...")

    historico_engine = _carregar_historico()
    historico_dz = [c['dezenas'] for c in concursos]

    # 1. Estado do mercado
    estado = _avaliar_estado_mercado(clasf, bt_din if 'erro' not in bt_din else bt_fixo)
    if verbose:
        print(f"  [AI Engine] Estado: {estado}")

    # 2. Estrategia
    estrategia = _escolher_estrategia(bt_fixo, bt_din, clasf, historico_engine)
    if verbose:
        print(f"  [AI Engine] Estrategia: {estrategia.perfil} "
              f"(confianca {estrategia.confianca:.0f}%)")

    # 3. Rankear jogos
    avaliacoes = _rankear_jogos(jogos, clasf, pares_quentes, historico_dz)

    alta  = sum(1 for a in avaliacoes if a.nivel == 'ALTA')
    media = sum(1 for a in avaliacoes if a.nivel == 'MEDIA')
    baixa = sum(1 for a in avaliacoes if a.nivel == 'BAIXA')

    if verbose:
        print(f"  [AI Engine] Jogos: {alta} alta | {media} media | {baixa} baixa confianca")

    # 4. Explicacao geral
    explicacao = _gerar_explicacao(estado, estrategia, pool_final, val_pool, avaliacoes, clasf)

    # 5. Alertas
    alertas = []
    if val_pool['score_qualidade'] < 60:
        alertas.append(f"Pool com qualidade baixa ({val_pool['score_qualidade']}/100). "
                       "Considere ajustar os parametros.")
    pct_cobertura = bt_din.get('pct_dentro_pool', 0) if 'erro' not in bt_din else bt_fixo.get('pct_dentro_pool', 0)
    if pct_cobertura < 25:
        alertas.append(f"Cobertura historica baixa ({pct_cobertura:.1f}%). "
                       "A garantia do fechamento depende do pool cobrir o sorteio.")
    if baixa > 16:
        alertas.append("Maioria dos jogos com baixa confianca. "
                       "Considere usar o perfil Conservador.")

    # 6. Desempenho recente
    bt_usar = bt_din if 'erro' not in bt_din else bt_fixo
    desempenho = {
        'tipo_backtest':  bt_usar.get('tipo', 'fixo'),
        'concursos_bt':   bt_usar.get('total_concursos', 0),
        'pct_cobertura':  bt_usar.get('pct_dentro_pool', 0),
        'faixas': {str(k): v for k, v in bt_usar.get('faixas', {}).items()},
    }

    analise = AnaliseCompleta(
        timestamp=datetime.now().isoformat(),
        concurso_base=concursos[-1]['concurso'],
        estado_mercado=estado,
        estrategia=estrategia,
        pool_recomendado=pool_final,
        pool_score_qualidade=val_pool['score_qualidade'],
        jogos_rankeados=[asdict(a) for a in avaliacoes],
        n_jogos_alta_confianca=alta,
        n_jogos_media_confianca=media,
        n_jogos_baixa_confianca=baixa,
        explicacao_geral=explicacao,
        alertas=alertas,
        desempenho_recente=desempenho,
    )

    # Salvar no historico
    entrada_hist = {
        'concurso':    concursos[-1]['concurso'],
        'data':        concursos[-1]['data'],
        'timestamp':   analise.timestamp,
        'perfil':      estrategia.perfil,
        'confianca':   estrategia.confianca,
        'pct_cobertura': pct_cobertura,
        'alta':  alta, 'media': media, 'baixa': baixa,
    }
    historico_engine.append(entrada_hist)
    _salvar_historico(historico_engine)

    if verbose:
        print(f"  [AI Engine] Concluido em {time.time()-t0:.2f}s")

    return analise


# ── Relatorio textual ─────────────────────────────────────────────────────────

def relatorio_engine(analise: AnaliseCompleta) -> str:
    a = analise
    linhas = [
        "=" * 65,
        "  AI ENGINE — ANALISE E RECOMENDACOES",
        "=" * 65,
        f"  Concurso base    : #{a.concurso_base}",
        f"  Estado mercado   : {a.estado_mercado}",
        f"",
        f"  ESTRATEGIA: [{a.estrategia.perfil.upper()}] "
        f"(confianca {a.estrategia.confianca:.0f}%)",
        f"  {a.estrategia.motivo}",
        f"",
        f"  POOL ({len(a.pool_recomendado)} dezenas) — "
        f"qualidade {a.pool_score_qualidade}/100:",
        "  " + "  ".join(f"{d:02d}" for d in sorted(a.pool_recomendado)),
        f"",
        f"  JOGOS RANKEADOS POR CONFIANCA:",
        f"  {'#':>3}  {'Jogo':>5}  {'Score':>6}  {'Nivel':>6}  "
        f"{'Soma':>5}  {'Pares':>6}  Explicacao",
        "  " + "-" * 65,
    ]

    for pos, jogo_d in enumerate(a.jogos_rankeados[:24], 1):
        nums = " ".join(f"{d:02d}" for d in jogo_d['dezenas'][:5]) + "..."
        linhas.append(
            f"  {pos:>3}  J{jogo_d['numero']:02d}    "
            f"{jogo_d['score_confianca']:>5.1f}  {jogo_d['nivel']:>6}  "
            f"{jogo_d['soma']:>5}  {jogo_d['pares']:>6}  "
            f"{jogo_d['explicacao'][:35]}"
        )

    linhas += [
        f"",
        f"  DISTRIBUICAO:",
        f"  Alta confianca : {a.n_jogos_alta_confianca:>3} jogos",
        f"  Media confianca: {a.n_jogos_media_confianca:>3} jogos",
        f"  Baixa confianca: {a.n_jogos_baixa_confianca:>3} jogos",
    ]

    if a.alertas:
        linhas += ["", "  ALERTAS:"]
        for alerta in a.alertas:
            linhas.append(f"  ! {alerta}")

    linhas += ["", "  ANALISE:", ""]
    for linha in a.explicacao_geral.split('\n'):
        linhas.append(f"  {linha}")

    linhas += [
        f"",
        f"  Cobertura historica (backtest): "
        f"{a.desempenho_recente.get('pct_cobertura', 0):.1f}%",
        "=" * 65,
    ]
    return "\n".join(linhas)


def historico_decisoes(n_ultimas: int = 10) -> str:
    hist = _carregar_historico()
    if not hist:
        return "  Nenhuma decisao registrada ainda."
    entradas = hist[-n_ultimas:]
    linhas = [
        "=" * 60,
        f"  HISTORICO DO AI ENGINE (ultimas {len(entradas)})",
        "=" * 60,
        f"  {'Conc':>6}  {'Data':>12}  {'Perfil':>12}  "
        f"{'Confian':>8}  {'Cobert':>7}  Alta/Med/Bx",
        "  " + "-" * 58,
    ]
    for e in entradas:
        linhas.append(
            f"  #{e.get('concurso','?'):>5}  {e.get('data','?'):>12}  "
            f"{e.get('perfil','?'):>12}  {e.get('confianca',0):>7.0f}%  "
            f"{e.get('pct_cobertura',0):>6.1f}%  "
            f"{e.get('alta',0)}/{e.get('media',0)}/{e.get('baixa',0)}"
        )
    linhas.append("=" * 60)
    return "\n".join(linhas)
