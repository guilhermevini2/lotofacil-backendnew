/*
 * server.js — Servidor Node.js local (porta 3001) do LotofacilPro v3.
 *
 * Faz a ponte entre o backend Python/Flask e os modelos de IA do Puter.js.
 *
 * Endpoints:
 *   GET  /health          -> status do servidor + disponibilidade do Puter
 *   POST /api/ai-analyze  -> recebe estatisticas, retorna {pesos, pool_final,
 *                            fechamento, estrategia} gerado pela IA (Puter.js)
 *                            ou pelo motor heuristico local (fallback).
 *
 * O servidor NUNCA falha silenciosamente: se a IA nao estiver disponivel,
 * cai automaticamente no fallback heuristico e sinaliza isso no campo
 * "provider" da resposta.
 */

import express from "express";
import cors from "cors";
import { analisarHeuristico } from "./lib/heuristic.js";
import { chatPuter, inicializarPuter, puterStatus, MODELO_PADRAO } from "./lib/puterClient.js";
import { montarPrompt, parseRespostaIA } from "./lib/prompt.js";

const PORT = process.env.PORT || 3001;
const app = express();

app.use(cors());
app.use(express.json({ limit: "5mb" }));

// Log simples de cada requisicao.
app.use((req, _res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

app.get("/health", async (_req, res) => {
  await inicializarPuter();
  res.json({
    ok: true,
    servico: "lotofacilpro-puter-server",
    porta: PORT,
    puter: puterStatus(),
  });
});

app.post("/api/ai-analyze", async (req, res) => {
  const dados = req.body || {};
  const modeloReq = dados.model || MODELO_PADRAO;

  // 1) Tenta usar a IA via Puter.js.
  try {
    const prompt = montarPrompt(dados);
    const texto = await chatPuter(prompt, modeloReq);
    const parsed = parseRespostaIA(texto);
    return res.json({
      ok: true,
      provider: "puter",
      model: modeloReq,
      ...parsed,
    });
  } catch (err) {
    console.warn(`[ai-analyze] Puter indisponivel/falhou: ${err.message}. Usando fallback heuristico.`);
  }

  // 2) Fallback heuristico local — sempre retorna JSON valido.
  try {
    const resultado = analisarHeuristico(dados);
    return res.json({
      ok: true,
      provider: "heuristic",
      model: null,
      motivo_fallback: puterStatus().erro || "Puter.js indisponivel",
      ...resultado,
    });
  } catch (err) {
    return res.status(500).json({ ok: false, erro: err.message });
  }
});

// POST /api/chat -> usado pelo chat_engine.py (aba "Chat" da interface).
// Recebe { mensagem, contexto, historico, system } e retorna { resposta }.
app.post("/api/chat", async (req, res) => {
  const { mensagem, contexto, historico, system } = req.body || {};

  if (!mensagem) {
    return res.status(400).json({ ok: false, erro: "campo 'mensagem' e obrigatorio" });
  }

  let historicoTxt = "";
  if (Array.isArray(historico)) {
    for (const msg of historico) {
      historicoTxt += `Usuario: ${msg.usuario}\nAssistente: ${msg.resposta}\n\n`;
    }
  }

  const prompt = [
    contexto || "",
    historicoTxt ? `=== HISTORICO RECENTE ===\n${historicoTxt}` : "",
    `=== PERGUNTA ===\n${mensagem}`,
  ].filter(Boolean).join("\n\n");

  try {
    const texto = await chatPuter(prompt, MODELO_PADRAO, system);
    return res.json({ ok: true, provider: "puter", resposta: texto.trim() });
  } catch (err) {
    console.warn(`[chat] Puter indisponivel/falhou: ${err.message}. Sem fallback de texto no Node.`);
    // Sem Puter disponivel, devolve erro — o chat_engine.py (Python) ja tem seu
    // proprio fallback baseado em regras para este caso.
    return res.status(503).json({ ok: false, erro: err.message || "Puter.js indisponivel" });
  }
});

app.listen(PORT, () => {
  console.log("=".repeat(60));
  console.log("  LotofacilPro v3 — Servidor Puter.js (Node.js)");
  console.log("=".repeat(60));
  console.log(`  Rodando em: http://localhost:${PORT}`);
  console.log(`  Modelo IA padrao: ${MODELO_PADRAO}`);
  console.log(`  Puter token: ${process.env.PUTER_AUTH_TOKEN ? "definido" : "NAO definido (usara fallback heuristico)"}`);
  console.log("=".repeat(60));
});
