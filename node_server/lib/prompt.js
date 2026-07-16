/*
 * prompt.js — Monta o prompt enviado ao modelo de IA e faz o parse
 * robusto da resposta JSON.
 */

export function montarPrompt(dados) {
  const ranking = (dados.ranking || []).slice(0, 25);
  const tend = dados.tendencias || {};
  const pares = (dados.pares_quentes || []).slice(0, 12);
  const bt = dados.backtest || {};

  const rankingTxt = ranking
    .map(
      (r) =>
        `  dezena ${String(r.dezena).padStart(2, "0")}: score=${(r.score ?? 0).toFixed ? r.score.toFixed(1) : r.score}, atraso=${r.atraso ?? "?"}, tendencia=${r.tendencia || "?"}`
    )
    .join("\n");

  const paresTxt = pares
    .map((p) => `  (${p[0]}, ${p[1]}) x${p[2]}`)
    .join("\n");

  return `Voce e um analista estatistico especialista na Lotofacil (loteria brasileira, 25 dezenas, 15 sorteadas por concurso).

Sua tarefa: analisar as estatisticas abaixo e escolher as MELHORES 18 dezenas para montar um fechamento matematico 18-15-14 (que gera 24 jogos com garantia de 14 pontos se as 15 dezenas sorteadas estiverem entre as 18 escolhidas).

CONTEXTO:
- Concurso base: ${dados.concurso_base ?? "?"}
- Estado do mercado: ${dados.estado_mercado || "nao informado"}
- Cobertura historica (backtest): ${bt.pct_dentro_pool ?? "?"}%

RANKING DAS DEZENAS (score consolidado, atraso e tendencia):
${rankingTxt || "  (sem dados)"}

TENDENCIAS:
- Esquentando: ${(tend.esquentando || []).join(", ") || "nenhuma"}
- Esfriando: ${(tend.esfriando || []).join(", ") || "nenhuma"}
- Ciclo de retorno: ${(tend.ciclo || []).join(", ") || "nenhuma"}

PARES QUENTES (aparecem juntos com frequencia):
${paresTxt || "  (sem dados)"}

REGRAS:
1. Escolha EXATAMENTE 18 dezenas distintas entre 1 e 25.
2. Combine dezenas de alto score com algumas atrasadas (ciclo de retorno) para equilibrar.
3. Decida um perfil de estrategia: "conservador", "equilibrado" ou "agressivo".
4. Defina pesos (0 a 1, somando ~1) para os criterios: frequencia, atraso, tendencia, pares_quentes, distribuicao.
5. Explique a estrategia em portugues claro, em 3 a 6 frases.

RESPONDA APENAS COM JSON VALIDO (sem texto antes ou depois), no formato EXATO:
{
  "pesos": {"frequencia": 0.3, "atraso": 0.18, "tendencia": 0.27, "pares_quentes": 0.15, "distribuicao": 0.1},
  "pool_final": [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18],
  "fechamento": {"tipo": "18-15-14", "jogos": 24},
  "estrategia": {
    "perfil": "equilibrado",
    "confianca": 70,
    "resumo": "frase curta",
    "explicacao": "explicacao detalhada em portugues",
    "pontos_chave": ["ponto 1", "ponto 2", "ponto 3"]
  }
}`;
}

// Extrai e valida o JSON retornado pela IA. Lanca erro se invalido.
export function parseRespostaIA(texto) {
  if (!texto || typeof texto !== "string") {
    throw new Error("Resposta vazia da IA");
  }

  // Tenta achar o primeiro bloco {...} da resposta.
  let jsonStr = texto.trim();

  // Remove cercas de codigo markdown se houver.
  const fence = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) jsonStr = fence[1].trim();

  // Se ainda houver texto ao redor, recorta do primeiro { ao ultimo }.
  const first = jsonStr.indexOf("{");
  const last = jsonStr.lastIndexOf("}");
  if (first !== -1 && last !== -1 && last > first) {
    jsonStr = jsonStr.slice(first, last + 1);
  }

  let obj;
  try {
    obj = JSON.parse(jsonStr);
  } catch (e) {
    throw new Error("JSON invalido da IA: " + e.message);
  }

  // Validacao do pool_final.
  const pool = obj.pool_final;
  if (!Array.isArray(pool)) throw new Error("pool_final ausente ou nao e array");
  const limpo = [...new Set(pool.map((n) => parseInt(n, 10)))].filter(
    (n) => Number.isInteger(n) && n >= 1 && n <= 25
  );
  if (limpo.length !== 18) {
    throw new Error(`pool_final deve ter 18 dezenas validas (recebeu ${limpo.length})`);
  }
  obj.pool_final = limpo.sort((a, b) => a - b);

  // Normaliza estrategia.
  obj.estrategia = obj.estrategia || {};
  obj.pesos = obj.pesos || {};
  obj.fechamento = obj.fechamento || { tipo: "18-15-14", jogos: 24 };

  return obj;
}
