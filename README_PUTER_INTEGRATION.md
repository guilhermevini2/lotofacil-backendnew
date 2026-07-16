# 🧠 Integração Puter.js — LotofacilPro v3

Este documento descreve a integração da **IA (Puter.js)** ao LotofacilPro v3,
permitindo que os modelos Claude / GPT / Gemini analisem as estatísticas e
gerem jogos inteligentes — mantendo **toda a lógica Python existente intacta**.

---

## 1. Arquitetura (Opção A — Desktop com Node.js local)

```
┌──────────────────────────────────────────────────────────────────┐
│  Navegador (PWA)  webapp/index.html                                │
│    • Botão "🧠 Gerar Jogos Inteligentes"                           │
│    • Puter.js client-side (análise em linguagem natural, opcional) │
└───────────────┬───────────────────────────────┬───────────────────┘
                │ HTTP (fetch)                    │ (opcional, User-Pays)
                ▼                                 ▼
┌──────────────────────────────┐        ┌─────────────────────────────┐
│  Flask  servidor.py :5000     │        │  Puter.js (nuvem)           │
│    /api/gerar-inteligente     │        │  Claude / GPT / Gemini      │
│    /api/status-inteligente    │        └─────────────────────────────┘
│    /api/resultado-inteligente │                    ▲
│    /api/ia/status             │                    │
└───────────────┬───────────────┘                    │ (token opcional)
                │ HTTP (requests)  ai_provider.py     │
                ▼                                      │
┌──────────────────────────────────────────┐         │
│  Node.js  node_server/server.js :3001     │─────────┘
│    POST /api/ai-analyze                    │
│    • @heyputer/puter.js (Claude/GPT/Gemini)│
│    • Fallback heurístico se IA indisponível│
└────────────────────────────────────────────┘
```

**Fluxo do botão "Gerar Jogos Inteligentes":**

```
Análises (pipeline Python) → AI Engine (ai_provider → Node.js → Puter.js)
   → Validator (validar_matriz, 816 cenários) → Fechamento (24 jogos) → Jogos
```

Se o Node.js ou o Puter.js estiverem indisponíveis, o sistema **degrada
graciosamente** para heurísticas locais (em Node **e** em Python), sempre
retornando um `pool_final` válido de 18 dezenas.

---

## 2. Componentes adicionados

| Arquivo | Papel |
|---------|-------|
| `node_server/server.js` | Servidor Express (porta 3001), endpoint `POST /api/ai-analyze`. |
| `node_server/lib/puterClient.js` | Cliente do `@heyputer/puter.js` (init por token). |
| `node_server/lib/prompt.js` | Monta o prompt e faz o parse/validação do JSON da IA. |
| `node_server/lib/heuristic.js` | Motor heurístico de fallback (Node). |
| `node_server/package.json` | Dependências Node (`express`, `cors`, `@heyputer/puter.js`). |
| `ai_provider.py` | Camada **modular** de provedores (Puter/local) — `analisar(dados)`. |
| `ai_engine.py` | Novo hook `analisar_inteligente(dados)` (lógica antiga intacta). |
| `servidor.py` | Novos endpoints Flask do fluxo inteligente. |
| `webapp/index.html` | Puter.js + botão + UI da estratégia/jogos da IA. |
| `start.sh` / `start.bat` | Sobem Node.js + Flask juntos. |

---

## 3. Instalação

### Pré-requisitos
- **Python 3.10+** (com as dependências de `requirements.txt`)
- **Node.js 18+** e **npm**

### Passos
```bash
# 1) Dependências Python
pip install -r requirements.txt

# 2) Dependências Node.js
cd node_server
npm install
cd ..
```

---

## 4. Como executar

### Opção recomendada (tudo junto)
```bash
# Linux / macOS
chmod +x start.sh
./start.sh

# Windows
start.bat
```

Depois acesse **http://localhost:5000**, rode a análise, vá na aba **AI** e
clique em **🧠 Gerar Jogos Inteligentes**.

### Manualmente (dois terminais)
```bash
# Terminal 1 — Node.js (Puter.js)
cd node_server && node server.js

# Terminal 2 — Flask (PWA)
python servidor.py
```

---

## 5. Habilitar a IA real do Puter.js

Existem **dois caminhos** (ambos já implementados):

### a) No navegador (client-side, sem chave)
O `index.html` carrega `https://js.puter.com/v2/`. Ao clicar em *Gerar Jogos
Inteligentes*, o front chama `puter.ai.chat(...)` para gerar a **análise em
linguagem natural**. Na primeira vez o Puter abre um popup de login (modelo
*User-Pays*). Sem login, mantém a explicação do backend.

### b) No servidor Node.js (server-side, via token)
Para que o **pool e a estratégia** venham de um LLM (e não do fallback),
defina um token do Puter antes de subir o Node:

```bash
export PUTER_AUTH_TOKEN="seu_token_do_puter"   # Linux/macOS
set PUTER_AUTH_TOKEN=seu_token_do_puter        # Windows

# Opcionais:
export PUTER_MODEL="claude-3-5-sonnet"         # modelo (padrão: gpt-4o-mini)
```

Sem token, o Node usa o **fallback heurístico** e o campo `provider` na
resposta virá como `"heuristic"` (o app continua 100% funcional).

---

## 6. Contrato JSON (`POST /api/ai-analyze`)

**Requisição** (enviada pelo Python):
```json
{
  "concurso_base": 3600,
  "estado_mercado": "AQUECIDO",
  "ranking": [{"dezena":1,"score":88.2,"atraso":0,"tendencia":"ESQUENTANDO"}],
  "tendencias": {"esquentando":[1,11],"esfriando":[6],"ciclo":[10,18]},
  "pares_quentes": [[1,11,45]],
  "backtest": {"pct_dentro_pool": 42.0},
  "pool_atual": [1,2,3,"...18 dezenas"],
  "model": "gpt-4o-mini"
}
```

**Resposta** (garantida sempre válida):
```json
{
  "ok": true,
  "provider": "puter",
  "model": "gpt-4o-mini",
  "pesos": {"frequencia":0.3,"atraso":0.18,"tendencia":0.27,"pares_quentes":0.15,"distribuicao":0.1},
  "pool_final": [1,2,3,"...18 dezenas"],
  "fechamento": {"tipo":"18-15-14","jogos":24},
  "estrategia": {
    "perfil":"equilibrado","confianca":70,
    "resumo":"...","explicacao":"...","pontos_chave":["..."]
  }
}
```

---

## 7. Trocar de provedor de IA (extensibilidade)

`ai_provider.py` foi desenhado para ser **modular**:

```python
import ai_provider

# Usa Puter via Node (padrão, com fallback automático)
ai_provider.analisar(dados)

# Força o heurístico local (sem rede)
ai_provider.analisar(dados, provider="local")
```

Para adicionar um novo provedor (ex.: OpenAI direto, modelo local):
1. Crie uma subclasse de `Provider` em `ai_provider.py`.
2. Registre-a no dicionário `_PROVIDERS`.
3. Selecione via `AI_PROVIDER=<nome>` (variável de ambiente) ou parâmetro.

Variáveis de ambiente úteis:
| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `AI_PROVIDER` | `puter` | Provedor padrão (`puter` / `local`). |
| `PUTER_NODE_URL` | `http://localhost:3001` | URL do servidor Node. |
| `PUTER_NODE_TIMEOUT` | `45` | Timeout (s) da chamada ao Node. |
| `PUTER_MODEL` | `gpt-4o-mini` | Modelo padrão da IA. |
| `PUTER_AUTH_TOKEN` | — | Token do Puter (server-side). |

---

## 8. Observações

- **A lógica Python original permanece intacta.** O pipeline clássico
  (`analisar(...)` em `ai_engine.py`) e todos os módulos existentes não foram
  alterados em comportamento.
- **Offline / PWA:** chamadas à IA exigem internet; sem ela o sistema usa o
  fallback local automaticamente.
- **VM / localhost:** as portas 3001 (Node) e 5000 (Flask) referem-se à
  máquina onde o app está rodando.
