"""
main.py - LotofacilPro v4.0
Fluxo: statistics -> ranking -> ML -> pool_selector -> AI Provider
       -> validator -> fechamento -> exports
"""
import sys, time
from utils import configurar_terminal
configurar_terminal()

from config import CONCURSO_INICIO_2026
from utils import banner, verificar_dependencias, formatar_dezenas, limpar_cache

args = sys.argv[1:]
LIMPAR_CACHE  = "--limpar-cache"   in args
SEM_GRAFICOS  = "--sem-graficos"   in args
SEM_EXCEL     = "--sem-excel"      in args
MODO          = "especialista" if "--especialista" in args else "basico"
POOL_SIZE     = 18
for i, a in enumerate(args):
    if a == "--pool" and i+1 < len(args):
        try: POOL_SIZE = int(args[i+1])
        except: pass

try:
    import graphs as _g; HAS_GRAPHS = True
except ImportError:
    HAS_GRAPHS = False

def sep(n=62): print("=" * n)
def titulo(txt): print(); sep(); print(f"  {txt}"); sep()


def main():
    print(banner())
    deps = verificar_dependencias()
    for pkg, ok in deps.items():
        print(f"    {pkg:<15} {'OK' if ok else 'NAO INSTALADO'}")
    print()

    if LIMPAR_CACHE:
        print(f"  Cache limpo: {limpar_cache()} arquivo(s).\n")

    if MODO == "especialista":
        print("  MODO: ESPECIALISTA (backtests massivos + AI completa)\n")
    else:
        print("  MODO: BASICO\n")

    # P1
    titulo("P1 — ACUMULACAO")
    import acumulacao
    print(acumulacao.resumo_acumulacao(acumulacao.verificar_acumulacao()))

    # P2
    titulo("P2 — DOWNLOAD (API Caixa)")
    import api
    try:
        ultimo = api.ultimo_concurso()
        print(f"  Ultimo concurso: #{ultimo}")
    except Exception as e:
        print(f"  ERRO: {e}")
        if sys.platform == "win32": input("\n  ENTER para sair...")
        sys.exit(1)
    concursos = api.buscar_intervalo(CONCURSO_INICIO_2026, ultimo)
    if not concursos: sys.exit(1)
    print(f"  {len(concursos)} concursos | {concursos[0]['data']} -> {concursos[-1]['data']}")

    # P3
    titulo("P3 — ESTATISTICAS")
    import statistics as stats_mod
    t0 = time.time()
    dados = stats_mod.consolidar(concursos)
    st = dados["stats_soma"]
    print(f"  em {time.time()-t0:.2f}s | soma media={st['media']} min={st['minimo']} max={st['maximo']}")

    # P4
    titulo("P4 — PARES E TRIOS QUENTES")
    import ranking as ranking_mod
    pares = ranking_mod.calcular_pares_quentes(concursos)
    trios = ranking_mod.calcular_trios_quentes(concursos)
    print(f"  Top par : {pares[0][0]:02d}+{pares[0][1]:02d} ({pares[0][2]}x)")
    print(f"  Top trio: {trios[0][0]:02d}+{trios[0][1]:02d}+{trios[0][2]:02d} ({trios[0][3]}x)")

    # P5
    titulo("P5 — TENDENCIAS")
    from hibrido_tendencia import classificar_todas, resumo_tendencias
    historico_dz = [c["dezenas"] for c in concursos]
    clasf = classificar_todas(historico_dz)
    print(resumo_tendencias(clasf))

    # P6
    titulo("P6 — SCORES HIBRIDOS")
    from hibrido_pesos import carregar_pesos, resumo_pesos
    from hibrido_score import calcular_scores, ranking_hibrido, tabela_ranking
    pesos = carregar_pesos()
    print(resumo_pesos(pesos))
    rows_h = ranking_hibrido(concursos, pesos, None, clasf)
    print(tabela_ranking(rows_h, set(r["dezena"] for r in rows_h[:18])))

    # P7
    titulo("P7 — AUTOAPRENDIZADO")
    from hibrido_autoaprendizado import executar_ciclo_autoaprendizado, resumo_ultimo_ciclo
    res_auto = executar_ciclo_autoaprendizado(concursos, ml_probas=None, verbose=True)
    print(resumo_ultimo_ciclo(res_auto))
    pesos = carregar_pesos()
    rows_h = ranking_hibrido(concursos, pesos, None, clasf)

    # P8
    titulo("P8 — MODELO ML")
    ml_probas = None
    try:
        from ml_model import treinar, prever_probabilidades, resumo_modelo
        meta_ml = treinar(concursos, verbose=True)
        print(resumo_modelo(meta_ml))
        ml_probas = prever_probabilidades(historico_dz)
        rows_h = ranking_hibrido(concursos, pesos, ml_probas, clasf)
        print("  Scores hibridos atualizados com ML.")
    except Exception as e:
        print(f"  ML ignorado: {e}")

    # P9 — Modo Especialista (opcional)
    pool_especialista = None
    if MODO == "especialista":
        titulo("P9 — MODO ESPECIALISTA (backtests massivos)")
        from modo_especialista import executar_modo_especialista, resumo_especialista
        t0 = time.time()
        res_esp = executar_modo_especialista(concursos, verbose=True)
        print(f"\n  Concluido em {time.time()-t0:.1f}s")
        print(resumo_especialista(res_esp))
        pesos = res_esp["melhores_pesos"]
        rows_h = ranking_hibrido(concursos, pesos, ml_probas, clasf)
        pool_especialista = res_esp["pool_recomendado"]
        print(f"\n  Enviando relatorio completo ao AI Provider...")

    # P10 — AI Provider (Puter.js -> Node -> Heuristico)
    titulo("P10 — AI PROVIDER (Puter.js via Node.js)")
    from ai_provider import analisar as ai_analisar
    payload_ia = {
        "concurso_base": ultimo,
        "ranking": [
            {"dezena":r["dezena"],"score":r.get("score",0),
             "atraso":r.get("atraso",0),"tendencia":r.get("tendencia","?")}
            for r in rows_h
        ],
        "tendencias": {
            "esquentando": [c["dezena"] for c in clasf if c["tendencia"]=="ESQUENTANDO"],
            "esfriando":   [c["dezena"] for c in clasf if c["tendencia"]=="ESFRIANDO"],
        },
        "pares_quentes": [[a,b,cnt] for a,b,cnt in pares[:10]],
        "backtest": {"pct_dentro_pool": 0},
        "pool_atual": pool_especialista or [r["dezena"] for r in rows_h[:18]],
    }
    if MODO == "especialista":
        payload_ia.update(res_esp.get("relatorio", {}))

    resp_ia = ai_analisar(payload_ia, verbose=True)
    pool_ia = resp_ia.get("pool_final", [])
    estrategia_ia = resp_ia.get("estrategia", {})

    print(f"\n  Provider usado  : {resp_ia.get('provider','local')}")
    print(f"  Estrategia      : {estrategia_ia.get('perfil','?')}")
    print(f"  Confianca       : {estrategia_ia.get('confianca','?')}%")
    if estrategia_ia.get("explicacao"):
        print(f"  Explicacao      : {estrategia_ia['explicacao'][:120]}...")
    if pool_ia:
        print(f"  Pool sugerido   : {formatar_dezenas(pool_ia)}")

    # P11 — Selecao do pool (combinando tudo)
    titulo("P11 — SELECAO DO POOL")
    from pool_selector import selecionar_pool, validar_pool, relatorio_selecao
    from hibrido_perfis import top18_por_perfil, resumo_perfis, PERFIS_VALIDOS
    sel = selecionar_pool(concursos, tamanho=POOL_SIZE,
                          n_atrasadas=2, janela_recente=20, atraso_min=8)
    # Prioridade: pool da IA > pool do especialista > pool do selector
    if pool_ia and len(pool_ia) == 18:
        pool_final = sorted(set(int(d) for d in pool_ia if 1<=d<=25))[:18]
        print("  Pool: sugerido pela IA")
    elif pool_especialista:
        pool_final = pool_especialista[:18]
        print("  Pool: otimizado pelo modo Especialista")
    else:
        pool_final = sel["pool"][:18]
        print("  Pool: selector hibrido (recentes + atrasadas)")

    pools_p = top18_por_perfil(calcular_scores, concursos, pesos, ml_probas)
    print(resumo_perfis(pools_p))
    print(f"\n  Pool final: {formatar_dezenas(pool_final)}")

    # P12
    titulo("P12 — VALIDACAO DO POOL")
    val_pool = validar_pool(pool_final, historico_dz)
    print(relatorio_selecao(sel, val_pool))

    # P13 — Validator + Fechamento
    titulo("P13 — VALIDACAO MATEMATICA + FECHAMENTO")
    import validator, fechamento as fech_mod
    val_mat = validator.validar_matriz()
    print(validator.resumo_validacao(val_mat))
    if not val_mat["valida"]: sys.exit(1)
    pool_18 = pool_final[:18]
    jogos = fech_mod.gerar_jogos(pool_18)
    print(fech_mod.resumo_jogos(jogos, pool_18))
    custo = fech_mod.custo_fechamento(jogos)
    print(f"\n  Custo: R$ {custo['custo_total']:.2f} ({custo['jogos']} jogos)")

    # P14 — Filtros modo aviso
    titulo("P14 — FILTROS (modo aviso)")
    from filtros import filtrar_jogos, resumo_filtros, MODO_AVISO
    jogos_f, rel_f = filtrar_jogos(jogos, modo=MODO_AVISO)
    print(resumo_filtros(rel_f, modo=MODO_AVISO))

    # P15 — Backtests
    titulo("P15 — BACKTESTS")
    import simulator
    bt_fixo = simulator.backtest(concursos, pool_18)
    print(simulator.resumo_backtest(bt_fixo))
    bt_din = simulator.backtest_dinamico(concursos, tamanho_pool=18, janela_treino=60)
    print(simulator.resumo_backtest(bt_din))
    bt_usar = bt_din if "erro" not in bt_din else bt_fixo

    # AI Engine
    titulo("AI ENGINE — RANKEAR E EXPLICAR JOGOS")
    from ai_engine import analisar as engine_analisar, relatorio_engine, historico_decisoes
    analise = engine_analisar(
        concursos=concursos, clasf=clasf, rows_h=rows_h,
        pares_quentes=[(a,b,c) for a,b,c in pares[:20]],
        bt_fixo=bt_fixo, bt_din=bt_din, jogos=jogos_f,
        pool_final=pool_18, val_pool=val_pool, verbose=True,
    )
    print(relatorio_engine(analise))
    print(historico_decisoes(5))
    jogos_rankeados = [j["dezenas"] for j in analise.jogos_rankeados]

    # Graficos
    if HAS_GRAPHS and not SEM_GRAFICOS:
        titulo("GRAFICOS")
        from pool_adaptativo import analisar_pools
        ap = analisar_pools([r["dezena"] for r in rows_h])
        paths = _g.gerar_todos(dados, pool_18, bt_usar,
                               pares_quentes=pares, analise_pools=ap, concursos=concursos)
        for p in paths: print(f"  OK  {p.name}")

    # P16 — Exports
    titulo("P16 — EXPORTANDO")
    import exports
    rows_cls = ranking_mod.ranking_completo(dados, len(concursos), concursos)
    txt_val = validator.resumo_validacao(val_mat)
    txt_bt  = simulator.resumo_backtest(bt_usar)

    p_txt = exports.exportar_txt(concursos, dados, rows_cls, jogos_rankeados,
        pool_18, bt_usar, val_mat, txt_val, txt_bt,
        pares_quentes=pares[:30], trios_quentes=trios[:15], analise_pools=None)
    p_cr  = exports.exportar_csv_ranking(rows_cls)
    p_cj  = exports.exportar_csv_jogos(jogos_rankeados)
    p_ch  = exports.exportar_csv_historico(concursos)
    p_cp  = exports.exportar_csv_pares(pares[:30])
    for label, p in [("TXT",p_txt),("CSV rank",p_cr),
                      ("CSV jogos",p_cj),("CSV hist",p_ch),("CSV pares",p_cp)]:
        print(f"  OK  {label:<12}: {p.name}")
    if not SEM_EXCEL and deps.get("openpyxl"):
        try:
            p_xl = exports.exportar_excel(concursos, dados, rows_cls,
                                          jogos_rankeados, pool_18, bt_usar)
            print(f"  OK  Excel        : {p_xl.name}")
        except Exception as e:
            print(f"  AVISO Excel: {e}")
    try:
        p_pdf = exports.exportar_pdf("", p_txt)
        if p_pdf.suffix == ".pdf": print(f"  OK  PDF          : {p_pdf.name}")
    except: pass

    sep()
    print()
    print("  RESUMO FINAL — LotofacilPro v4.0")
    print(f"  Modo              : {MODO.upper()}")
    print(f"  Provider IA       : {resp_ia.get('provider','local')}")
    print(f"  Concursos         : {len(concursos)}")
    print(f"  Pool final        : {formatar_dezenas(pool_18)}")
    print(f"  Qualidade pool    : {val_pool['score_qualidade']}/100")
    print(f"  Estrategia AI     : {analise.estrategia.perfil.upper()} ({analise.estrategia.confianca:.0f}%)")
    print(f"  Alta confianca    : {analise.n_jogos_alta_confianca} jogos")
    print(f"  Custo total       : R$ {round(len(jogos_rankeados)*3.0,2):.2f}")
    print(f"  Cobertura hist    : {bt_usar.get('pct_dentro_pool',0)}%")
    print()
    print("  LotofacilPro v4.0 concluido!")
    sep()

    if sys.platform == "win32":
        input("\n  Pressione ENTER para voltar ao menu...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelado.")
        if sys.platform == "win32": input("\n  ENTER...")
    except Exception as exc:
        import traceback
        print("\n" + "="*62)
        print("  ERRO INESPERADO:")
        print("="*62)
        traceback.print_exc()
        print("="*62)
        if sys.platform == "win32": input("\n  ENTER para voltar ao menu...")
