/**
 * ai.js - Integracao LotofacilPro v3 com Puter.js
 *
 * Fluxo:
 *   Python (Flask) --> /api/ai/resumo --> ai.js --> puter.ai.chat()
 *                                                        |
 *   Python (Flask) <-- /api/ai/aplicar <-- ai.js <-- JSON da IA
 *
 * O modelo recebe um resumo compacto (nao o historico completo)
 * e responde sempre em JSON estruturado.
 */

// -- Configuracao -------------------------------------------------------------

const AI_CONFIG = {
  // Modelo padrao. O usuario pode trocar na interface.
  // Opcoes rapidas: "gpt-5.4-nano", "claude-haiku-4-5", "google/gemini-2.5-flash"
  modelo: "gpt-5.4-nano",

  // Temperatura: 0.2 = respostas mais determinísticas (bom para decisoes)
  temperatura: 0.2,

  // Timeout em ms para aguardar resposta da IA
  timeout: 30000,
};

// Modelos disponiveis para selecao na interface
const MODELOS_DISPONIVEIS = [
  { id: "gpt-5.4-nano",               label: "GPT-5.4 Nano (rapido, gratis)"   },
  { id: "openai/gpt-5.4",             label: "GPT-5.4 (mais capaz)"           },
  { id: "claude-haiku-4-5",           label: "Claude Haiku 4.5 (Anthropic)"   },
  { id: "google/gemini-2.5-flash",    label: "Gemini 2.5 Flash (Google)"      },
  { id: "deepseek/deepseek-r1",       label: "DeepSeek R1 (raciocinio)"       },
  { id: "openai/gpt-5.5",             label: "GPT-5.5 (mais avancado)"        },
];

// -- Prompt do sistema --------------------------------------------------------

const SYSTEM_PROMPT = `Voce e um especialista em analise estatistica da Lotofacil brasileira.
Sua funcao e receber dados estatisticos do sistema LotofacilPro e sugerir:
1. Os pesos otimizados para o motor de score hibrido
2. O melhor pool de 18 dezenas para o proximo concurso
3. A estrategia de aposta recomendada

REGRAS CRITICAS:
- Responda APENAS com JSON valido. Zero texto antes ou depois.
- Nao use markdown, nao use blocos de codigo.
- O pool_final deve ter EXATAMENTE 18 numeros entre 1 e 25, sem repeticao.
- Os pesos devem somar aproximadamente 1.0.
- Seja conservador: priorize padroes historicos solidos sobre tendencias volateis.

FORMATO OBRIGATORIO DA RESPOSTA:
{
  "pesos": {
    "freq_100": 0.15,
    "freq_50": 0.10,
    "freq_20": 0.15,
    "freq_10": 0.20,
    "tendencia": 0.10,
    "atraso": 0.08,
    "repeticao": 0.05,
    "linhas_cols": 0.05,
    "paridade": 0.03,
    "moldura": 0.03,
    "soma_ideal": 0.03,
    "ml": 0.03
  },
  "pool_final": [1,2,4,5,7,8,10,11,13,14,16,17,18,19,20,22,23,24],
  "estrategia": "equilibrado",
  "fechamento": "18x15",
  "confianca": 72,
  "explicacao": "Texto curto explicando a decisao em portugues"
}`;

// -- Estado local -------------------------------------------------------------

let aiState = {
  disponivel:  false,   // Puter.js carregado?
  autenticado: false,   // Usuario logado no Puter?
  processando: false,
  ultimaResposta: null,
  erro: null,
};

// -- Inicializacao ------------------------------------------------------------

async function inicializarPuter() {
  // Puter.js e carregado via CDN no index.html
  if (typeof puter === "undefined") {
    console.warn("[AI] Puter.js nao encontrado. Verifique a tag <script>.");
    aiState.disponivel = false;
    return false;
  }

  aiState.disponivel = true;

  // Verificar se o usuario ja esta autenticado
  try {
    const user = await puter.auth.getUser();
    if (user) {
      aiState.autenticado = true;
      console.log(`[AI] Puter.js pronto. Usuario: ${user.username}`);
    }
  } catch (e) {
    // Nao autenticado ainda — ok, pediremos login antes de usar
    aiState.autenticado = false;
  }

  return true;
}

async function garantirLogin() {
  if (aiState.autenticado) return true;
  try {
    await puter.auth.signIn();
    aiState.autenticado = true;
    return true;
  } catch (e) {
    aiState.erro = "Login no Puter cancelado ou falhou.";
    return false;
  }
}

// -- Funcao principal: Gerar Jogos Inteligentes -------------------------------

async function gerarJogosInteligentes(onProgresso) {
  if (!aiState.disponivel) {
    throw new Error("Puter.js nao disponivel. Verifique sua conexao com a internet.");
  }

  aiState.processando = true;
  aiState.erro = null;

  try {
    // 1. Login se necessario
    onProgresso?.("Verificando autenticacao Puter...", 5);
    const logado = await garantirLogin();
    if (!logado) throw new Error(aiState.erro || "Falha no login Puter.");

    // 2. Buscar resumo do backend Python
    onProgresso?.("Buscando dados do sistema...", 15);
    const respBackend = await fetch("/api/ai/resumo");
    if (!respBackend.ok) {
      const err = await respBackend.json();
      throw new Error(err.mensagem || "Falha ao buscar dados do backend.");
    }
    const { resumo } = await respBackend.json();

    // 3. Montar prompt com os dados
    onProgresso?.("Preparando contexto para a IA...", 25);
    const promptUsuario = montarPrompt(resumo);

    // 4. Chamar Puter.js
    onProgresso?.(`Consultando ${AI_CONFIG.modelo}...`, 40);
    const respostaRaw = await Promise.race([
      puter.ai.chat(promptUsuario, {
        model:       AI_CONFIG.modelo,
        system:      SYSTEM_PROMPT,
        temperature: AI_CONFIG.temperatura,
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Timeout: IA demorou mais de 30s.")),
        AI_CONFIG.timeout)
      ),
    ]);

    // 5. Extrair texto da resposta
    onProgresso?.("Processando resposta da IA...", 65);
    const textoResposta = extrairTexto(respostaRaw);

    // 6. Parsear JSON
    const jsonIA = parsearResposta(textoResposta);
    aiState.ultimaResposta = jsonIA;

    // 7. Validar estrutura minima
    validarResposta(jsonIA);

    // 8. Enviar para o backend aplicar
    onProgresso?.("Aplicando configuracao ao sistema...", 80);
    const respAplicar = await fetch("/api/ai/aplicar", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        ...jsonIA,
        timestamp: new Date().toISOString(),
        modelo_usado: AI_CONFIG.modelo,
      }),
    });

    const resultadoAplicar = await respAplicar.json();
    if (!resultadoAplicar.ok) {
      throw new Error(resultadoAplicar.mensagem || "Falha ao aplicar configuracao.");
    }

    onProgresso?.("Concluido!", 100);
    aiState.processando = false;

    return {
      jsonIA,
      resultadoAplicar,
      resumo_usado: resumo,
    };

  } catch (err) {
    aiState.processando = false;
    aiState.erro = err.message;
    throw err;
  }
}

// -- Helpers ------------------------------------------------------------------

function montarPrompt(resumo) {
  const top5 = (resumo.top5_dezenas || [])
    .map(d => `${String(d.dezena).padStart(2,"0")} (score:${d.score?.toFixed?.(1)||d.score}, tend:${d.tendencia}, atraso:${d.atraso})`)
    .join(", ");

  const bottom5 = (resumo.bottom5_dezenas || [])
    .map(d => `${String(d.dezena).padStart(2,"0")} (tend:${d.tendencia}, atraso:${d.atraso})`)
    .join(", ");

  const pares = (resumo.pares_quentes || [])
    .map(p => `${p.par}(${p.count}x)`)
    .join(", ");

  const bt = resumo.backtest || {};
  const pesos = resumo.pesos_atuais || {};
  const pesosStr = Object.entries(pesos)
    .map(([k,v]) => `${k}:${(v*100).toFixed(1)}%`)
    .join(", ");

  return `DADOS DO SISTEMA LOTOFACIL PRO

Periodo: ${resumo.periodo}
Concursos analisados: ${resumo.concursos_analisados}
Concurso mais recente: #${resumo.ultimo_concurso}
Concurso acumulado: ${resumo.acumulou ? `SIM (R$ ${(resumo.premio_estimado||0).toLocaleString("pt-BR")})` : "NAO"}

POOL ATUAL (18 dezenas): ${(resumo.pool_atual||[]).map(d=>String(d).padStart(2,"0")).join(" ")}
Qualidade do pool: ${resumo.pool_qualidade}/100
Dezenas forcadas (atrasadas): ${(resumo.pool_forcadas||[]).join(", ") || "nenhuma"}

TOP-5 DEZENAS POR SCORE: ${top5}
BOTTOM-5 DEZENAS (mais frias): ${bottom5}
TOP-5 PARES QUENTES: ${pares}

BACKTEST (${bt.tipo||"fixo"}):
- Concursos testados: ${bt.concursos}
- Cobertura do pool: ${bt.cobertura_pct?.toFixed?.(1)||bt.cobertura_pct}%
- 15 pontos: ${bt.pts_15} vezes | 14 pontos: ${bt.pts_14} vezes | 13 pontos: ${bt.pts_13} vezes

SOMA MEDIA DAS DEZENAS: ${resumo.soma_media}

PESOS ATUAIS DO MOTOR HIBRIDO: ${pesosStr}

Com base nesses dados, sugira os melhores pesos, o pool ideal de 18 dezenas e a estrategia recomendada. Responda APENAS em JSON, sem nenhum texto adicional.`;
}

function extrairTexto(resposta) {
  // Puter.js pode retornar string, objeto com .text, ou objeto com .content
  if (typeof resposta === "string") return resposta;
  if (resposta?.text)    return resposta.text;
  if (resposta?.content) {
    if (typeof resposta.content === "string") return resposta.content;
    if (Array.isArray(resposta.content)) {
      return resposta.content
        .filter(b => b.type === "text")
        .map(b => b.text)
        .join("");
    }
  }
  if (resposta?.message?.content) return resposta.message.content;
  return String(resposta);
}

function parsearResposta(texto) {
  // Limpar markdown se o modelo insistir em usar
  let limpo = texto
    .replace(/```json\s*/gi, "")
    .replace(/```\s*/g, "")
    .trim();

  // Encontrar o primeiro { ... } valido
  const inicio = limpo.indexOf("{");
  const fim    = limpo.lastIndexOf("}");
  if (inicio === -1 || fim === -1) {
    throw new Error(`IA nao retornou JSON valido. Resposta: "${limpo.slice(0, 200)}"`);
  }
  limpo = limpo.slice(inicio, fim + 1);

  try {
    return JSON.parse(limpo);
  } catch (e) {
    throw new Error(`JSON invalido da IA: ${e.message}. Trecho: "${limpo.slice(0,200)}"`);
  }
}

function validarResposta(json) {
  if (!json.pool_final || !Array.isArray(json.pool_final)) {
    throw new Error("IA nao retornou pool_final.");
  }
  if (json.pool_final.length < 15) {
    throw new Error(`Pool com apenas ${json.pool_final.length} dezenas (minimo 15).`);
  }
  // Garantir que todos os numeros sao inteiros validos
  json.pool_final = json.pool_final
    .map(d => parseInt(d))
    .filter(d => d >= 1 && d <= 25);
}

// -- UI: Botao "Gerar Jogos Inteligentes" ------------------------------------

function renderBotaoAI() {
  return `
<div id="aiContainer" style="margin-bottom:20px">
  <div class="section-head">
    <h3>Gerar Jogos Inteligentes</h3>
    <span class="meta">via Puter.js</span>
  </div>

  <!-- Seletor de modelo -->
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
    <select id="aiModeloSelect" style="
      background:var(--bg-elev-2);border:1px solid var(--line);color:var(--cream);
      font-family:var(--font-mono);font-size:11px;padding:7px 10px;
      border-radius:var(--radius-sm);flex:1;min-width:200px">
      ${MODELOS_DISPONIVEIS.map(m =>
        `<option value="${m.id}" ${m.id===AI_CONFIG.modelo?"selected":""}>${m.label}</option>`
      ).join("")}
    </select>
  </div>

  <!-- Botao principal -->
  <button id="btnAI" class="btn btn-primary" style="width:100%;font-size:15px;padding:16px;gap:10px"
    onclick="onClickAI()">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5V12l3 3-3 3v2h-4v-2l-3-3 3-3V9.5A4 4 0 0 1 8 6a4 4 0 0 1 4-4z"/>
      <circle cx="12" cy="6" r="1.5" fill="currentColor"/>
    </svg>
    Gerar Jogos Inteligentes
  </button>

  <!-- Barra de progresso (oculta) -->
  <div id="aiProgress" style="display:none;margin-top:12px">
    <div class="progress-track"><div class="progress-fill" id="aiProgressFill"></div></div>
    <div id="aiProgressText" style="font-family:var(--font-mono);font-size:11px;
      color:var(--cream-dim);margin-top:6px;text-align:center"></div>
  </div>

  <!-- Resultado (oculto) -->
  <div id="aiResultado" style="display:none;margin-top:16px"></div>
</div>`;
}

async function onClickAI() {
  const btn    = document.getElementById("btnAI");
  const prog   = document.getElementById("aiProgress");
  const fill   = document.getElementById("aiProgressFill");
  const ptxt   = document.getElementById("aiProgressText");
  const result = document.getElementById("aiResultado");

  // Atualizar modelo selecionado
  const sel = document.getElementById("aiModeloSelect");
  if (sel) AI_CONFIG.modelo = sel.value;

  btn.disabled = true;
  prog.style.display = "";
  result.style.display = "none";
  result.innerHTML = "";

  const onProgresso = (msg, pct) => {
    fill.style.width  = pct + "%";
    ptxt.textContent  = msg;
  };

  try {
    const { jsonIA, resultadoAplicar } = await gerarJogosInteligentes(onProgresso);

    // Exibir resultado
    const pool = (jsonIA.pool_final || []).map(d => String(d).padStart(2,"0")).join("  ");
    const mudancas = (resultadoAplicar.mudancas || []).map(m => `<li>${m}</li>`).join("");
    const estratColor = {
      conservador:"var(--cream)", equilibrado:"var(--green)", agressivo:"var(--amber)"
    }[jsonIA.estrategia] || "var(--cream)";

    result.style.display = "";
    result.innerHTML = `
<div class="card" style="border-color:var(--green-dim)">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <span style="font-family:var(--font-mono);font-size:11px;color:var(--green);
      text-transform:uppercase;letter-spacing:.08em">IA Aplicada com Sucesso</span>
    <span style="font-family:var(--font-mono);font-size:11px;color:var(--cream-faint)">${AI_CONFIG.modelo}</span>
  </div>

  <div style="margin-bottom:12px">
    <div style="font-family:var(--font-mono);font-size:9.5px;color:var(--cream-faint);
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Estrategia escolhida</div>
    <div style="font-family:var(--font-mono);font-size:16px;font-weight:700;color:${estratColor}">
      ${(jsonIA.estrategia||"equilibrado").toUpperCase()}
      <span style="font-size:12px;font-weight:400;color:var(--cream-faint);margin-left:6px">
        confianca ${jsonIA.confianca||0}%
      </span>
    </div>
  </div>

  <div style="margin-bottom:12px">
    <div style="font-family:var(--font-mono);font-size:9.5px;color:var(--cream-faint);
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Pool sugerido pela IA</div>
    <div style="font-family:var(--font-mono);font-size:13px;color:var(--cream);
      letter-spacing:.04em;line-height:1.8">${pool}</div>
  </div>

  ${jsonIA.explicacao ? `
  <div style="border-top:1px solid var(--line-soft);padding-top:10px;margin-top:4px">
    <div style="font-family:var(--font-mono);font-size:9.5px;color:var(--cream-faint);
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Analise da IA</div>
    <p style="font-size:13px;color:var(--cream-dim);line-height:1.6">${jsonIA.explicacao}</p>
  </div>` : ""}

  ${mudancas ? `
  <div style="border-top:1px solid var(--line-soft);padding-top:10px;margin-top:8px">
    <div style="font-family:var(--font-mono);font-size:9.5px;color:var(--cream-faint);
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Alteracoes aplicadas</div>
    <ul style="list-style:none;font-family:var(--font-mono);font-size:11px;color:var(--green)">${mudancas}</ul>
  </div>` : ""}

  <button class="btn btn-ghost" style="width:100%;margin-top:12px;font-size:12px"
    onclick="location.reload()">
    Recarregar para ver jogos atualizados
  </button>
</div>`;

    // Recarregar dados da aba Jogos automaticamente
    await carregarResultado();

  } catch (err) {
    result.style.display = "";
    result.innerHTML = `
<div class="error-card">
  <div class="icon">⚠</div>
  <strong>Falha na consulta com a IA</strong>
  <p>${err.message}</p>
  <p style="font-size:11px;color:var(--cream-faint);margin-top:6px">
    Verifique sua conexao com internet e que o Puter.js esta carregado.
    O sistema continua funcionando normalmente sem a IA.
  </p>
</div>`;
  }

  btn.disabled = false;
  prog.style.display = "none";
}

// Inicializar quando o DOM estiver pronto
document.addEventListener("DOMContentLoaded", () => {
  inicializarPuter().then(ok => {
    if (!ok) console.warn("[AI] Puter.js nao disponivel.");
  });
});
