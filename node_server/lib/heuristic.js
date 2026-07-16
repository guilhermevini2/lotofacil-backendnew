/*
 * heuristic.js — Motor heuristico local de fallback.
 *
 * Quando o Puter.js nao esta disponivel (sem token / sem internet / erro),
 * este modulo gera uma resposta ESTRUTURADA no mesmo formato que a IA
 * retornaria, usando apenas as estatisticas recebidas do Python.
 *
 * Contrato de saida (identico ao da IA):
 *   { pesos, pool_final, fechamento, estrategia }
 */

// Constroi um pool de 18 dezenas a partir do ranking + dezenas atrasadas.
export function construirPoolHeuristico(dados) {
  const ranking = Array.isArray(dados.ranking) ? dados.ranking : [];
  const tend = dados.tendencias || {};
  const esquentando = new Set(tend.esquentando || []);
  const ciclo = new Set(tend.ciclo || []);

  // Ordena por score decrescente (ja costuma vir ordenado, mas garantimos).
  const ordenado = [...ranking].sort((a, b) => (b.score || 0) - (a.score || 0));

  const pool = [];
  const usados = new Set();

  // 1) Top dezenas por score (nucleo do pool).
  for (const r of ordenado) {
    if (pool.length >= 16) break;
    if (!usados.has(r.dezena)) {
      pool.push(r.dezena);
      usados.add(r.dezena);
    }
  }

  // 2) Forca ate 2 dezenas muito atrasadas (ciclo de retorno) que ainda nao entraram.
  const atrasadas = [...ordenado]
    .filter((r) => !usados.has(r.dezena))
    .sort((a, b) => (b.atraso || 0) - (a.atraso || 0));
  for (const r of atrasadas) {
    if (pool.length >= 18) break;
    pool.push(r.dezena);
    usados.add(r.dezena);
  }

  // 3) Completa se faltar (caso ranking curto): usa dezenas 1..25.
  for (let d = 1; d <= 25 && pool.length < 18; d++) {
    if (!usados.has(d)) {
      pool.push(d);
      usados.add(d);
    }
  }

  return pool.slice(0, 18).sort((a, b) => a - b);
}

// Decide o perfil de estrategia a partir do estado do mercado / tendencias.
function decidirPerfil(dados) {
  const tend = dados.tendencias || {};
  const nEsq = (tend.esquentando || []).length;
  const nCiclo = (tend.ciclo || []).length;
  const pctPool = (dados.backtest && dados.backtest.pct_dentro_pool) || 0;

  if (pctPool < 25) {
    return {
      perfil: "conservador",
      confianca: 72,
      motivo:
        "Cobertura historica baixa nos backtests. Priorizando padroes solidos e dezenas de alta frequencia de longo prazo.",
    };
  }
  if (nEsq >= 8) {
    return {
      perfil: "agressivo",
      confianca: 66,
      motivo: `${nEsq} dezenas esquentando. Tendencias recentes fortes favorecem uma abordagem mais dinamica.`,
    };
  }
  if (nCiclo >= 4) {
    return {
      perfil: "equilibrado",
      confianca: 70,
      motivo: `${nCiclo} dezenas em ciclo de retorno. Mix de estatistica solida com dezenas atrasadas prontas para voltar.`,
    };
  }
  return {
    perfil: "equilibrado",
    confianca: 68,
    motivo:
      "Mercado sem padrao dominante claro. Estrategia balanceada tende a ser a mais robusta.",
  };
}

export function analisarHeuristico(dados) {
  const pool = construirPoolHeuristico(dados);
  const dec = decidirPerfil(dados);
  const tend = dados.tendencias || {};

  // Pesos por criterio (0..1) — ajustados conforme o perfil.
  let pesos;
  if (dec.perfil === "conservador") {
    pesos = { frequencia: 0.4, atraso: 0.15, tendencia: 0.2, pares_quentes: 0.15, distribuicao: 0.1 };
  } else if (dec.perfil === "agressivo") {
    pesos = { frequencia: 0.2, atraso: 0.2, tendencia: 0.35, pares_quentes: 0.15, distribuicao: 0.1 };
  } else {
    pesos = { frequencia: 0.3, atraso: 0.18, tendencia: 0.27, pares_quentes: 0.15, distribuicao: 0.1 };
  }

  const esqNoPool = pool.filter((d) => (tend.esquentando || []).includes(d));
  const cicloNoPool = pool.filter((d) => (tend.ciclo || []).includes(d));

  const explicacao =
    `Estrategia ${dec.perfil.toUpperCase()} escolhida (confianca ${dec.confianca}%). ` +
    `${dec.motivo} ` +
    `O pool de 18 dezenas prioriza as de maior score consolidado` +
    (esqNoPool.length ? `, incluindo ${esqNoPool.length} em alta (${esqNoPool.slice(0, 4).join(", ")})` : "") +
    (cicloNoPool.length ? ` e ${cicloNoPool.length} em ciclo de retorno` : "") +
    `. Sobre essas 18 dezenas aplica-se o fechamento matematico 18-15-14, que gera 24 jogos com garantia de ao menos 14 acertos caso as 15 dezenas sorteadas estejam dentro do pool.`;

  return {
    pesos,
    pool_final: pool,
    fechamento: { tipo: "18-15-14", jogos: 24, garantia: "14 pontos se as 15 sorteadas estiverem no pool" },
    estrategia: {
      perfil: dec.perfil,
      confianca: dec.confianca,
      resumo: dec.motivo,
      explicacao,
      pontos_chave: [
        `Perfil: ${dec.perfil}`,
        `${esqNoPool.length} dezenas em alta no pool`,
        `${cicloNoPool.length} dezenas em ciclo de retorno no pool`,
        `Fechamento 18-15-14 (24 jogos)`,
      ],
    },
  };
}
