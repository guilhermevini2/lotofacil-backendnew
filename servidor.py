"""
servidor.py - LotofacilPro v4 - Servidor Flask com AI Provider + Chat + Especialista.

Fluxo do pipeline (corrigido):
  statistics -> ranking -> ML -> pool_selector -> AI Provider
  -> validator -> fechamento -> exports

Endpoints novos:
  POST /api/analisar?modo=basico|especialista
  POST /api/ai/gerar          (Gerar Jogos Inteligentes via Puter)
  GET  /api/ai/resumo         (dados para o frontend)
  POST /api/chat              (chat contextual)
  GET  /api/chat/historico
  DELETE /api/chat/limpar
  GET  /api/especialista/status
  GET  /api/node/status       (status do servidor Node.js)
"""

import sys, socket, threading, webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import configurar_terminal
configurar_terminal()

from flask import Flask, jsonify, send_from_directory, request
import api
import statistics as stats_mod
import ranking as ranking_mod
import fechamento as fech_mod
import validator
import simulator
import acumulacao
from filtros import filtrar_jogos, MODO_AVISO
from pool_selector import selecionar_pool, validar_pool
from hibrido_pesos import carregar_pesos, salvar_pesos, _normalizar
from hibrido_score import calcular_scores as hibrido_calc, ranking_hibrido
from hibrido_tendencia import classificar_todas
from hibrido_perfis import top18_por_perfil, PERFIS_VALIDOS
from hibrido_autoaprendizado import executar_ciclo_autoaprendizado
from ai_provider import analisar as ai_analisar, montar_dados_para_ia, get_provider
from chat_engine import get_chat
from config import CONCURSO_INICIO_2026

try:
    from ai_engine import analisar as engine_analisar, relatorio_engine
    HAS_ENGINE = True
except Exception:
    HAS_ENGINE = False

try:
    from ml_model import treinar as ml_treinar, prever_probabilidades
    from ml_ranking import ranking_ml, comparar_rankings
    HAS_ML = True
except Exception:
    HAS_ML = False

app = Flask(__name__, static_folder="webapp", static_url_path="")

_estado = {
    "status": "idle", "progresso": 0, "etapa": "",
    "resultado": None, "erro": None, "modo": "basico",
}
_lock = threading.Lock()

def _set(**kw):
    with _lock: _estado.update(kw)
def _get():
    with _lock: return dict(_estado)

def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except: return "127.0.0.1"


# ── Pipeline principal ────────────────────────────────────────────────────────

def _rodar_analise(pool_size: int = 18, modo: str = "basico"):
    try:
        _set(modo=modo)

        # P1: Acumulacao
        _set(progresso=2, etapa="Verificando acumulacao...")
        info_acum = acumulacao.verificar_acumulacao()

        # P2: Download
        _set(progresso=5, etapa="Verificando ultimo concurso...")
        ultimo = api.ultimo_concurso()
        _set(progresso=8, etapa=f"Baixando ate #{ultimo}...")
        concursos = api.buscar_intervalo(CONCURSO_INICIO_2026, ultimo)
        if not concursos:
            raise RuntimeError("Nenhum concurso carregado.")

        # P3: Estatisticas
        _set(progresso=18, etapa="Calculando estatisticas...")
        dados = stats_mod.consolidar(concursos)

        # P4: Pares e trios
        _set(progresso=24, etapa="Calculando pares e trios quentes...")
        pares = ranking_mod.calcular_pares_quentes(concursos)
        trios = ranking_mod.calcular_trios_quentes(concursos)

        # P5: Tendencias
        _set(progresso=30, etapa="Detectando tendencias...")
        historico_dz = [c["dezenas"] for c in concursos]
        clasf = classificar_todas(historico_dz)

        # P6: Scores hibridos
        _set(progresso=36, etapa="Gerando scores hibridos...")
        pesos_base = carregar_pesos()
        rows_h = ranking_hibrido(concursos, pesos_base, None, clasf)

        # P7: Autoaprendizado
        _set(progresso=44, etapa="Autoaprendizado dos pesos...")
        res_auto = executar_ciclo_autoaprendizado(concursos, ml_probas=None, verbose=False)
        pesos_base = carregar_pesos()
        rows_h = ranking_hibrido(concursos, pesos_base, None, clasf)

        # P8: ML
        _set(progresso=54, etapa="Modelo ML...")
        ml_probas = None
        resultado_ml = {"disponivel": False}
        if HAS_ML:
            try:
                meta_ml = ml_treinar(concursos, verbose=False)
                ml_probas = prever_probabilidades(historico_dz)
                rows_h = ranking_hibrido(concursos, pesos_base, ml_probas, clasf)
                resultado_ml = {
                    "disponivel": True,
                    "auc": meta_ml.get("auc_medio", 0),
                    "modelo": meta_ml.get("modelo", ""),
                }
            except Exception as e:
                resultado_ml = {"disponivel": False, "erro": str(e)}

        # P9: Modo Especialista (se ativado)
        resultado_especialista = {}
        if modo == "especialista":
            _set(progresso=58, etapa="Modo Especialista — backtests massivos...")
            from modo_especialista import executar_modo_especialista, resumo_especialista
            def cb(msg, pct):
                _set(progresso=58 + int(pct * 0.12), etapa=f"Especialista: {msg}")
            res_esp = executar_modo_especialista(concursos, verbose=False, callback_progresso=cb)
            # Usar pesos e pool do especialista
            pesos_base = res_esp["melhores_pesos"]
            rows_h = ranking_hibrido(concursos, pesos_base, ml_probas, clasf)
            resultado_especialista = {
                "disponivel":      True,
                "melhor_variante": res_esp["melhor_variante"],
                "melhor_score":    res_esp["melhor_score"],
                "cobertura":       res_esp["melhor_cobertura"],
                "n_testes":        res_esp["n_testes"],
                "top5":            res_esp["top5_estrategias"][:5],
                "pool_sugerido":   res_esp["pool_recomendado"],
                "relatorio":       res_esp["relatorio"],
            }

        # P9/10: Selecao do pool
        _set(progresso=72, etapa="Selecionando pool de dezenas...")
        sel_ps = selecionar_pool(concursos, tamanho=pool_size,
                                  n_atrasadas=2, janela_recente=20, atraso_min=8)
        # Modo especialista: usar pool sugerido se disponivel
        if resultado_especialista.get("pool_sugerido"):
            pool_final = resultado_especialista["pool_sugerido"]
        else:
            pool_final = sel_ps["pool"]

        # P10: Validar pool
        _set(progresso=76, etapa="Validando pool...")
        val_pool = validar_pool(pool_final, historico_dz)
        pools_p = top18_por_perfil(hibrido_calc, concursos, pesos_base, ml_probas)

        resultado_pool_sel = {
            "disponivel": True,
            "pool": pool_final, "base": sel_ps["base"],
            "forcadas": sel_ps["forcadas"],
            "atrasos_forcadas": {str(d): sel_ps["atrasos"][d] for d in sel_ps["forcadas"]},
            "score_qualidade": val_pool["score_qualidade"],
            "aprovado": val_pool["aprovado"],
            "sobreposicao": val_pool["sobreposicao"],
            "pares_pool": val_pool["pares_pool"],
            "impares_pool": val_pool["impares_pool"],
            "n_moldura": val_pool["n_moldura"], "n_centro": val_pool["n_centro"],
            "checklist": {
                nome: {"ok": c["ok"], "detalhe": c["detalhe"]}
                for nome, c in val_pool["criterios"].items()
            },
        }

        # P11: AI Provider (Puter.js -> Node.js -> fallback heuristico)
        _set(progresso=80, etapa="Consultando AI Provider...")
        payload_ia = {
            "concurso_base":  ultimo,
            "estado_mercado": "",
            "ranking": [
                {"dezena": r["dezena"], "score": r.get("score",0),
                 "atraso": r.get("atraso",0), "tendencia": r.get("tendencia","?")}
                for r in rows_h
            ],
            "tendencias": {
                "esquentando": [c["dezena"] for c in clasf if c["tendencia"]=="ESQUENTANDO"],
                "esfriando":   [c["dezena"] for c in clasf if c["tendencia"]=="ESFRIANDO"],
                "ciclo":       [c["dezena"] for c in clasf if c["tendencia"]=="CICLO_RETORNO"],
            },
            "pares_quentes": [[a,b,cnt] for a,b,cnt in pares[:12]],
            "backtest": {"pct_dentro_pool": 0},
            "pool_atual": pool_final,
        }
        if resultado_especialista.get("relatorio"):
            payload_ia.update(resultado_especialista["relatorio"])

        resp_ia = ai_analisar(payload_ia, verbose=False)
        # Aplicar pool sugerido pela IA se valido
        pool_ia = resp_ia.get("pool_final", [])
        if pool_ia and len(pool_ia) == 18:
            pool_final = pool_ia
            val_pool = validar_pool(pool_final, historico_dz)

        # P12: Validacao matematica
        _set(progresso=84, etapa="Validando fechamento matematico...")
        val_mat = validator.validar_matriz()
        pool_18 = pool_final[:18]
        jogos_brutos = fech_mod.gerar_jogos(pool_18)

        # P13: Filtros (modo aviso)
        _set(progresso=87, etapa="Analisando filtros...")
        jogos_finais, _ = filtrar_jogos(jogos_brutos, modo=MODO_AVISO)

        # P14: Backtests
        _set(progresso=90, etapa="Executando backtests...")
        bt_fixo = simulator.backtest(concursos, pool_18)
        bt_din  = simulator.backtest_dinamico(concursos, tamanho_pool=18, janela_treino=60)
        bt_usar = bt_din if "erro" not in bt_din else bt_fixo
        # Atualizar payload com cobertura real
        payload_ia["backtest"]["pct_dentro_pool"] = bt_usar.get("pct_dentro_pool", 0)

        # AI Engine (rankear e explicar jogos)
        _set(progresso=93, etapa="AI Engine rankear jogos...")
        resultado_ai = {"disponivel": False}
        if HAS_ENGINE:
            try:
                analise_ai = engine_analisar(
                    concursos=concursos, clasf=clasf, rows_h=rows_h,
                    pares_quentes=[(a,b,c) for a,b,c in pares[:20]],
                    bt_fixo=bt_fixo, bt_din=bt_din,
                    jogos=jogos_finais, pool_final=pool_18,
                    val_pool=val_pool, verbose=False,
                )
                resultado_ai = {
                    "disponivel": True,
                    "estado_mercado": analise_ai.estado_mercado,
                    "estrategia_perfil": analise_ai.estrategia.perfil,
                    "estrategia_confianca": analise_ai.estrategia.confianca,
                    "estrategia_motivo": analise_ai.estrategia.motivo,
                    "n_alta": analise_ai.n_jogos_alta_confianca,
                    "n_media": analise_ai.n_jogos_media_confianca,
                    "n_baixa": analise_ai.n_jogos_baixa_confianca,
                    "explicacao": analise_ai.explicacao_geral,
                    "alertas": analise_ai.alertas,
                    "jogos_rankeados": [
                        {"numero": j["numero"], "dezenas": j["dezenas"],
                         "score": j["score_confianca"], "nivel": j["nivel"],
                         "soma": j["soma"], "pares": j["pares"],
                         "explicacao": j["explicacao"], "alertas": j["alertas"]}
                        for j in analise_ai.jogos_rankeados
                    ],
                }
                jogos_finais = [j["dezenas"] for j in analise_ai.jogos_rankeados]
            except Exception as e:
                resultado_ai = {"disponivel": False, "erro": str(e)}

        # Adicionar info do AI Provider ao resultado_ai
        resultado_ai["provider"] = resp_ia.get("provider", "local")
        resultado_ai["provider_estrategia"] = resp_ia.get("estrategia", {})
        resultado_ai["provider_pesos"] = resp_ia.get("pesos", {})
        resultado_ai["provider_explicacao"] = (
            (resp_ia.get("estrategia") or {}).get("explicacao", "")
        )

        # Atualizar chat com contexto
        get_chat().atualizar_contexto({
            "dezenas_18": pool_18, "jogos": jogos_finais,
            "concursos_total": len(concursos),
            "periodo_inicio": concursos[0]["data"],
            "periodo_fim": concursos[-1]["data"],
            "backtest": {"pct_dentro_pool": bt_usar.get("pct_dentro_pool",0),
                         "faixas": {str(k):v for k,v in bt_usar["faixas"].items()}},
            "ai": resultado_ai,
            "pool_inteligente": resultado_pool_sel,
            "custo_total": round(len(jogos_finais)*3.0, 2),
        })

        _set(progresso=97, etapa="Finalizando...")

        resultado = {
            "concursos_total":  len(concursos),
            "periodo_inicio":   concursos[0]["data"],
            "periodo_fim":      concursos[-1]["data"],
            "ultimo_concurso":  ultimo,
            "modo_analise":     modo,
            "ranking": [
                {"posicao": r["posicao"], "dezena": r["dezena"],
                 "score": r["score"], "seta": r["seta"],
                 "label_tend": r["label_tend"], "freq_10": r["freq_10"],
                 "freq_20": r["freq_20"], "freq_50": r["freq_50"],
                 "atraso": r["atraso"], "pressao": r["pressao"],
                 "freq_abs": dados["freq_abs"].get(r["dezena"],0),
                 "freq_pct": dados["freq_pct"].get(r["dezena"],0.0),
                 "freq_decay": 0.0}
                for r in rows_h
            ],
            "dezenas_18":    pool_18,
            "pares_quentes": [{"a":a,"b":b,"count":c} for a,b,c in pares[:30]],
            "trios_quentes": [{"a":a,"b":b,"c":c,"count":cnt} for a,b,c,cnt in trios[:15]],
            "pools": [],
            "pool_escolhido": pool_size,
            "validacao": {
                "valida": val_mat["valida"],
                "cenarios_testados": val_mat["total_cenarios"],
                "cenarios_cobertos": val_mat["cenarios_cobertos"],
                "min_acertos": val_mat["min_acertos"],
            },
            "jogos": jogos_finais,
            "jogos_total_gerados": len(jogos_brutos),
            "jogos_aprovados_filtro": len(jogos_finais),
            "custo_total": round(len(jogos_finais)*3.0, 2),
            "backtest": {
                "tipo": bt_usar.get("tipo","fixo"),
                "total_concursos": bt_usar["total_concursos"],
                "pct_dentro_pool": bt_usar["pct_dentro_pool"],
                "faixas": {str(k):v for k,v in bt_usar["faixas"].items()},
            },
            "acumulacao": info_acum if info_acum.get("ok") else None,
            "estatisticas": {
                "soma": dados["stats_soma"],
                "freq_abs": {str(k):v for k,v in dados["freq_abs"].items()},
                "freq_pct": {str(k):v for k,v in dados["freq_pct"].items()},
                "atraso":   {str(k):v for k,v in dados["atraso"].items()},
            },
            "ml": resultado_ml,
            "hibrido": {
                "disponivel": True,
                "pool_18": [r["dezena"] for r in rows_h[:18]],
                "ranking": [
                    {"posicao":r["posicao"],"dezena":r["dezena"],"score":r["score"],
                     "tendencia":r["tendencia"],"seta":r["seta"],"label_tend":r["label_tend"],
                     "freq_10":r["freq_10"],"freq_20":r["freq_20"],"freq_50":r["freq_50"],
                     "atraso":r["atraso"],"pressao":r["pressao"],
                     "no_pool":r["dezena"] in set(pool_18)}
                    for r in rows_h
                ],
                "tendencias": [
                    {"dezena":c["dezena"],"tendencia":c["tendencia"],"seta":c["seta"],
                     "label":c["label"],"freq_10":round(c["freq_10"]*100,1),
                     "atraso":c["atraso"],"pressao":c["pressao"]}
                    for c in clasf
                ],
                "perfis": {nome:{"pool":pools_p[nome]} for nome in PERFIS_VALIDOS},
                "autoaprendizado": {
                    "status": res_auto.get("status"),
                    "hits_media_antes": res_auto.get("metricas_antes",{}).get("hits_media"),
                    "hits_media_depois": res_auto.get("metricas_depois",{}).get("hits_media"),
                    "pesos_atualizados": res_auto.get("pesos_atualizados"),
                },
                "pesos": pesos_base,
            },
            "pool_inteligente": resultado_pool_sel,
            "ai": resultado_ai,
            "especialista": resultado_especialista,
        }

        _set(status="pronto", progresso=100, etapa="Concluido!",
             resultado=resultado, erro=None)

    except Exception as exc:
        import traceback; traceback.print_exc()
        _set(status="erro", erro=str(exc))


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("webapp", "index.html")

@app.route("/ai.js")
def ai_js():
    return send_from_directory("webapp", "ai.js") if \
        Path("webapp/ai.js").exists() else ("", 404)

@app.route("/api/analisar", methods=["POST"])
def api_analisar():
    estado = _get()
    if estado["status"] == "carregando":
        return jsonify({"ok": False, "mensagem": "Analise em andamento."})
    pool_size = 18
    modo = "basico"
    if request.is_json:
        pool_size = int(request.json.get("pool_size", 18))
        modo = request.json.get("modo", "basico")
    _set(status="carregando", progresso=0, etapa="Iniciando...", erro=None)
    t = threading.Thread(target=_rodar_analise, args=(pool_size, modo), daemon=True)
    t.start()
    return jsonify({"ok": True, "modo": modo})

@app.route("/api/status")
def api_status():
    e = _get()
    return jsonify({"status":e["status"],"progresso":e["progresso"],
                    "etapa":e["etapa"],"erro":e["erro"],"modo":e.get("modo","basico")})

@app.route("/api/resultado")
def api_resultado():
    e = _get()
    if e["status"] != "pronto" or not e["resultado"]:
        return jsonify({"ok":False,"mensagem":"Resultado nao disponivel."}), 404
    return jsonify({"ok":True,"dados":e["resultado"]})

@app.route("/api/ai/resumo")
def api_ai_resumo():
    e = _get()
    if e["status"] != "pronto" or not e["resultado"]:
        return jsonify({"ok":False,"mensagem":"Analise nao concluida."}), 404
    d = e["resultado"]
    hib = d.get("hibrido",{})
    ranking_src = hib.get("ranking", d.get("ranking",[]))
    bt = d.get("backtest",{})
    pi = d.get("pool_inteligente",{})
    resumo = {
        "concursos_analisados": d.get("concursos_total",0),
        "periodo": f"{d.get('periodo_inicio','')} a {d.get('periodo_fim','')}",
        "ultimo_concurso": d.get("ultimo_concurso",0),
        "pool_atual": d.get("dezenas_18",[]),
        "pool_qualidade": pi.get("score_qualidade",0),
        "pool_forcadas": pi.get("forcadas",[]),
        "top5_dezenas": [
            {"dezena":r["dezena"],"score":r.get("score",0),
             "tendencia":r.get("tendencia","?"),"atraso":r.get("atraso",0),"freq_10":r.get("freq_10",0)}
            for r in sorted(ranking_src, key=lambda x:-x.get("score",0))[:5]
        ],
        "bottom5_dezenas": [
            {"dezena":r["dezena"],"score":r.get("score",0),
             "tendencia":r.get("tendencia","?"),"atraso":r.get("atraso",0)}
            for r in sorted(ranking_src, key=lambda x:x.get("score",0))[:5]
        ],
        "pares_quentes": [
            {"par":f"{p['a']:02d}+{p['b']:02d}","count":p["count"]}
            for p in d.get("pares_quentes",[])[:5]
        ],
        "backtest": {
            "tipo": bt.get("tipo","fixo"),
            "concursos": bt.get("total_concursos",0),
            "cobertura_pct": bt.get("pct_dentro_pool",0),
            "pts_15": bt.get("faixas",{}).get("15",0),
            "pts_14": bt.get("faixas",{}).get("14",0),
            "pts_13": bt.get("faixas",{}).get("13",0),
        },
        "soma_media": d.get("estatisticas",{}).get("soma",{}).get("media",0),
        "pesos_atuais": hib.get("pesos",{}),
        "acumulou": d.get("acumulacao",{}).get("alerta",False) if d.get("acumulacao") else False,
        "premio_estimado": d.get("acumulacao",{}).get("valor_estimado",0) if d.get("acumulacao") else 0,
    }
    return jsonify({"ok":True,"resumo":resumo})

@app.route("/api/ai/aplicar", methods=["POST"])
def api_ai_aplicar():
    if not request.is_json:
        return jsonify({"ok":False,"mensagem":"Body deve ser JSON."}), 400
    resp_ia = request.json
    e = _get()
    if e["status"] != "pronto" or not e["resultado"]:
        return jsonify({"ok":False,"mensagem":"Analise nao concluida."}), 400
    try:
        resultado = e["resultado"]
        mudancas = []
        novos_pesos = resp_ia.get("pesos")
        if novos_pesos and isinstance(novos_pesos, dict):
            salvar_pesos(_normalizar(novos_pesos), meta={"origem":"puter_ai"})
            mudancas.append(f"Pesos atualizados via IA")
        pool_ia = resp_ia.get("pool_final")
        if pool_ia and isinstance(pool_ia, list) and len(pool_ia) >= 15:
            pool_ia = sorted(set(int(d) for d in pool_ia if 1<=int(d)<=25))[:18]
            if len(pool_ia) == 18:
                val = validator.validar_matriz()
                if val["valida"]:
                    jogos_novos = fech_mod.gerar_jogos(pool_ia)
                    resultado["dezenas_18"] = pool_ia
                    resultado["jogos"] = jogos_novos
                    resultado["custo_total"] = round(len(jogos_novos)*3.0,2)
                    mudancas.append(f"Pool IA: {pool_ia}")
                    mudancas.append(f"{len(jogos_novos)} jogos re-gerados")
        if resp_ia.get("estrategia"):
            resultado["ai_estrategia"] = resp_ia["estrategia"]
            mudancas.append(f"Estrategia: {resp_ia['estrategia'].get('perfil','?')}")
        if resp_ia.get("estrategia",{}).get("explicacao"):
            resultado["ai_explicacao_puter"] = resp_ia["estrategia"]["explicacao"]
        _set(resultado=resultado)
        return jsonify({"ok":True,"mudancas":mudancas,
                        "pool_final":resultado.get("dezenas_18",[]),
                        "n_jogos":len(resultado.get("jogos",[]))})
    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"ok":False,"mensagem":str(exc)}), 500

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not request.is_json:
        return jsonify({"ok":False,"mensagem":"JSON esperado."}), 400
    msg = request.json.get("mensagem","").strip()
    if not msg:
        return jsonify({"ok":False,"mensagem":"Mensagem vazia."}), 400
    chat = get_chat()
    e = _get()
    if e["resultado"]:
        chat.atualizar_contexto(e["resultado"])
    try:
        resp = chat.enviar(msg)
        return jsonify(resp)
    except Exception as exc:
        return jsonify({"ok":False,"mensagem":str(exc)}), 500

@app.route("/api/chat/historico")
def api_chat_historico():
    chat = get_chat()
    return jsonify({"ok":True,"historico":chat.historico[-30:]})

@app.route("/api/chat/limpar", methods=["DELETE"])
def api_chat_limpar():
    get_chat().limpar_historico()
    return jsonify({"ok":True})

@app.route("/api/node/status")
def api_node_status():
    try:
        prov = get_provider("puter")
        ok = prov.disponivel()
        return jsonify({"ok":ok,"url":"http://localhost:3001",
                        "mensagem":"Node.js ativo" if ok else "Node.js inativo (usando fallback)"})
    except Exception as e:
        return jsonify({"ok":False,"mensagem":str(e)})

@app.route("/api/especialista/status")
def api_especialista_status():
    from pathlib import Path
    from config import BASE_DIR
    import json
    log_path = BASE_DIR / "cache" / "especialista_log.json"
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
            ultimo = log[-1] if log else {}
            return jsonify({"ok":True,"ultimo":ultimo,"total_execucoes":len(log)})
        except: pass
    return jsonify({"ok":True,"ultimo":{},"total_execucoes":0})

@app.route("/api/cache/limpar", methods=["POST"])
def api_limpar_cache():
    from utils import limpar_cache
    return jsonify({"ok":True,"removidos":limpar_cache()})



# ── Endpoints de compatibilidade com o index.html original ───────────────────
# O frontend chama /api/gerar-inteligente, /api/status-inteligente
# e /api/resultado-inteligente. Esses endpoints fazem a ponte com
# o AI Provider (Puter.js via Node.js ou fallback heuristico).

_ia_estado = {
    "status": "idle",   # idle | carregando | pronto | erro
    "progresso": 0,
    "etapa": "",
    "dados": None,
    "erro": None,
}
_ia_lock = threading.Lock()

def _ia_set(**kw):
    with _ia_lock: _ia_estado.update(kw)

def _ia_get():
    with _ia_lock: return dict(_ia_estado)


def _rodar_gerar_inteligente():
    """
    Pipeline do botao 'Gerar Jogos Inteligentes'.
    Usa o AI Provider (Puter.js -> Node.js -> heuristico).
    Opera sobre o resultado da analise principal ja concluida.
    """
    try:
        _ia_set(status="carregando", progresso=5, etapa="Verificando analise base...")

        estado = _get()
        if estado["status"] != "pronto" or not estado["resultado"]:
            raise RuntimeError("Execute a analise principal antes de usar a IA.")

        resultado_base = estado["resultado"]

        # 1. Buscar resumo dos dados
        _ia_set(progresso=15, etapa="Preparando dados para a IA...")
        hib = resultado_base.get("hibrido", {})
        ranking_src = hib.get("ranking", resultado_base.get("ranking", []))
        bt = resultado_base.get("backtest", {})
        pi = resultado_base.get("pool_inteligente", {})

        payload_ia = {
            "concurso_base":   resultado_base.get("ultimo_concurso", 0),
            "concursos_total": resultado_base.get("concursos_total", 0),
            "periodo": (f"{resultado_base.get('periodo_inicio','')} a "
                        f"{resultado_base.get('periodo_fim','')}"),
            "ranking": [
                {"dezena": r["dezena"], "score": r.get("score", 0),
                 "atraso": r.get("atraso", 0), "tendencia": r.get("tendencia", "?")}
                for r in sorted(ranking_src, key=lambda x: -x.get("score", 0))
            ],
            "tendencias": {
                t["tendencia"]: t["tendencia"]
                for t in hib.get("tendencias", [])
            },
            "pares_quentes": [
                [p["a"], p["b"], p["count"]]
                for p in resultado_base.get("pares_quentes", [])[:15]
            ],
            "backtest": {
                "pct_dentro_pool": bt.get("pct_dentro_pool", 0),
                "faixas": bt.get("faixas", {}),
            },
            "pool_atual": resultado_base.get("dezenas_18", []),
            "pool_qualidade": pi.get("score_qualidade", 0),
            "soma_media": resultado_base.get("estatisticas", {}).get("soma", {}).get("media", 0),
            "pesos_atuais": hib.get("pesos", {}),
            "acumulou": (resultado_base.get("acumulacao") or {}).get("alerta", False),
        }

        # 2. Chamar AI Provider
        _ia_set(progresso=40, etapa="Consultando AI Provider (Puter.js)...")
        resp_ia = ai_analisar(payload_ia, verbose=False)

        _ia_set(progresso=70, etapa="Processando resposta da IA...")

        # 3. Aplicar pool sugerido
        pool_ia = resp_ia.get("pool_final", [])
        if pool_ia and len(pool_ia) >= 15:
            pool_ia = sorted(set(int(d) for d in pool_ia if 1 <= int(d) <= 25))[:18]
        else:
            pool_ia = resultado_base.get("dezenas_18", [])

        _ia_set(progresso=80, etapa="Validando e gerando jogos...")

        val = validator.validar_matriz()
        if val["valida"] and len(pool_ia) == 18:
            jogos_ia = fech_mod.gerar_jogos(pool_ia)
        else:
            jogos_ia = resultado_base.get("jogos", [])
            pool_ia  = resultado_base.get("dezenas_18", pool_ia)

        # 4. Montar resultado
        _ia_set(progresso=92, etapa="Finalizando...")

        estrategia = resp_ia.get("estrategia", {})
        if isinstance(estrategia, str):
            estrategia = {"perfil": estrategia, "confianca": 65, "explicacao": ""}

        # Pontuacao de confianca para cada jogo (usando ai_engine se disponivel)
        jogos_com_score = []
        try:
            if HAS_ENGINE:
                from hibrido_tendencia import classificar_todas
                historico_dz = []
                # Tentar extrair historico do cache
                from config import CACHE_DIR
                import json as _json
                cached = sorted(CACHE_DIR.glob("*.json"))
                for cf in cached[-200:]:
                    try:
                        cs = _json.loads(cf.read_text(encoding="utf-8"))
                        historico_dz.append(cs.get("dezenas", []))
                    except Exception:
                        pass

                from ai_engine import _rankear_jogos, _nivel_confianca
                pares_qt = [(p["a"], p["b"], p["count"])
                            for p in resultado_base.get("pares_quentes", [])[:20]]
                clasf_dz = classificar_todas(historico_dz) if historico_dz else []
                avaliacoes = _rankear_jogos(jogos_ia, clasf_dz, pares_qt, historico_dz)
                for av in avaliacoes:
                    jogos_com_score.append({
                        "numero":    av.numero,
                        "dezenas":   av.dezenas,
                        "score":     av.score_confianca,
                        "nivel":     av.nivel,
                        "soma":      av.soma,
                        "pares":     av.pares,
                        "alertas":   av.alertas,
                        "explicacao": av.explicacao,
                    })
        except Exception:
            # Fallback simples: score baseado na soma
            soma_ideal = (170 + 230) / 2
            for i, jogo in enumerate(jogos_ia, 1):
                soma = sum(jogo)
                score = max(30, 100 - abs(soma - soma_ideal) / 2)
                jogos_com_score.append({
                    "numero": i, "dezenas": jogo,
                    "score": round(score, 1),
                    "nivel": _nivel_confianca_simples(score),
                    "soma": soma,
                    "pares": sum(1 for d in jogo if d % 2 == 0),
                    "alertas": [], "explicacao": "",
                })

        dados_resultado = {
            "provider":     resp_ia.get("provider", "local"),
            "model":        resp_ia.get("model", ""),
            "pool_final":   pool_ia,
            "n_jogos":      len(jogos_ia),
            "custo":        round(len(jogos_ia) * 3.0, 2),
            "estrategia":   estrategia,
            "jogos":        jogos_com_score,
            "pesos":        resp_ia.get("pesos", {}),
            "fechamento":   resp_ia.get("fechamento", "18x15"),
            "confianca":    resp_ia.get("confianca", estrategia.get("confianca", 65)),
        }

        # Atualizar resultado principal com o pool da IA
        resultado_base["dezenas_18"] = pool_ia
        resultado_base["jogos"]      = jogos_ia
        resultado_base["custo_total"] = round(len(jogos_ia) * 3.0, 2)
        resultado_base["ai_provider_resultado"] = dados_resultado
        _set(resultado=resultado_base)

        _ia_set(status="pronto", progresso=100, etapa="Concluido!",
                dados=dados_resultado, erro=None)

    except Exception as exc:
        import traceback; traceback.print_exc()
        _ia_set(status="erro", erro=str(exc))


def _nivel_confianca_simples(score):
    if score >= 68: return "ALTA"
    if score >= 52: return "MEDIA"
    return "BAIXA"


@app.route("/api/gerar-inteligente", methods=["POST"])
def api_gerar_inteligente():
    """Inicia a geracao de jogos via AI Provider (botao principal do index.html)."""
    ia = _ia_get()
    if ia["status"] == "carregando":
        return jsonify({"ok": False, "mensagem": "Ja em andamento."})

    estado = _get()
    if estado["status"] != "pronto":
        return jsonify({"ok": False,
                        "mensagem": "Execute a analise principal primeiro (botao Analisar)."})

    _ia_set(status="carregando", progresso=0, etapa="Iniciando...", erro=None, dados=None)
    t = threading.Thread(target=_rodar_gerar_inteligente, daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/status-inteligente")
def api_status_inteligente():
    """Retorna o status do processo de geracao inteligente."""
    ia = _ia_get()
    return jsonify({
        "status":    ia["status"],
        "progresso": ia["progresso"],
        "etapa":     ia["etapa"],
        "erro":      ia["erro"],
    })


@app.route("/api/resultado-inteligente")
def api_resultado_inteligente():
    """Retorna o resultado da geracao inteligente."""
    ia = _ia_get()
    if ia["status"] != "pronto" or not ia["dados"]:
        return jsonify({"ok": False, "mensagem": "Resultado nao disponivel."}), 404
    return jsonify({"ok": True, "dados": ia["dados"]})


def main():
    ip = ip_local()
    porta = 5000
    print()
    print("="*62)
    print("  LOTOFACIL PRO v4 — Servidor Web + AI Engine")
    print("="*62)
    print(f"\n  PC     : http://localhost:{porta}")
    print(f"  Celular: http://{ip}:{porta}")
    print(f"\n  Node.js (Puter): http://localhost:3001")
    print("  (execute: cd node_server && npm start)")
    print("\n  CTRL+C para parar.")
    print("="*62)
    try: webbrowser.open(f"http://localhost:{porta}")
    except: pass
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)

if __name__ == "__main__":
    main()
