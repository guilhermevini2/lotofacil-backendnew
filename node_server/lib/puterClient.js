/*
 * puterClient.js — Cliente do Puter.js para o servidor Node.js.
 *
 * O Puter.js no Node.js precisa de um token de autenticacao
 * (variavel de ambiente PUTER_AUTH_TOKEN). Se o token nao estiver
 * presente ou a inicializacao falhar, este modulo fica "indisponivel"
 * e o servidor cai automaticamente no motor heuristico local.
 *
 * Modelos suportados via Puter (User-Pays): Claude, GPT, Gemini, etc.
 */

let _puter = null;
let _initTried = false;
let _initError = null;

// Modelo padrao — pode ser trocado por env PUTER_MODEL.
export const MODELO_PADRAO = process.env.PUTER_MODEL || "gpt-4o-mini";

export async function inicializarPuter() {
  if (_initTried) return _puter;
  _initTried = true;

  const token = process.env.PUTER_AUTH_TOKEN;
  if (!token) {
    _initError = "PUTER_AUTH_TOKEN nao definido — usando fallback heuristico.";
    return null;
  }

  try {
    // Import dinamico para nao quebrar caso o pacote nao esteja instalado.
    const mod = await import("@heyputer/puter.js/src/init.cjs");
    const init = mod.init || (mod.default && mod.default.init);
    if (!init) throw new Error("funcao init() nao encontrada no pacote @heyputer/puter.js");
    _puter = init(token);
    return _puter;
  } catch (err) {
    _initError = `Falha ao inicializar Puter.js: ${err.message}`;
    _puter = null;
    return null;
  }
}

export function puterStatus() {
  return {
    disponivel: !!_puter,
    modelo: MODELO_PADRAO,
    erro: _initError,
  };
}

/*
 * Chama o modelo de IA via Puter e retorna o texto bruto da resposta.
 * Lanca erro se indisponivel — o chamador deve tratar o fallback.
 */
export async function chatPuter(prompt, model, system) {
  const puter = await inicializarPuter();
  if (!puter) {
    throw new Error(_initError || "Puter.js indisponivel");
  }
  const opcoes = { model: model || MODELO_PADRAO };
  if (system) opcoes.system = system;
  const resp = await puter.ai.chat(prompt, opcoes);

  // Normaliza os diferentes formatos de retorno do Puter.
  if (typeof resp === "string") return resp;
  if (resp && resp.message && resp.message.content) {
    const c = resp.message.content;
    return typeof c === "string" ? c : c.toString();
  }
  if (resp && resp.text) return resp.text;
  return JSON.stringify(resp);
}
