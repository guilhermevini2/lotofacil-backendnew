=============================================================
  LOTOFACIL PRO v4.0 - AI Premium
  Puter.js + AI Engine + Modo Especialista + Chat
=============================================================

INSTALACAO RAPIDA
-----------------
1. Extraia o ZIP em qualquer pasta (ex: C:\LotofacilPro\)
2. Duplo clique em instalar.bat
3. Duplo clique em start.bat (ou rodar.bat)


FORMAS DE USAR
--------------

[A] start.bat (RECOMENDADO)
    Inicia Node.js (Puter.js) + Flask automaticamente.
    Abre o app no navegador. Celular acessa pelo IP da rede.

[B] rodar.bat
    Menu interativo com todas as opcoes.

[C] python main.py
    Analise completa no terminal.

[D] python main.py --especialista
    Modo Especialista: backtests massivos + AI completa.


FLUXO DO SISTEMA (v4)
---------------------
  1. Download concursos (API Caixa)
  2. Estatisticas completas
  3. Tendencias das 25 dezenas
  4. Scores hibridos (12 criterios)
  5. Autoaprendizado dos pesos
  6. Modelo ML (Gradient Boosting)
  7. [ESPECIALISTA] Backtests massivos (40+ variantes)
  8. AI Provider (Puter.js -> Node.js -> heuristico local)
  9. Selecao do pool de dezenas
  10. Validacao do pool (checklist)
  11. Fechamento matematico (ultima etapa inteligente)
  12. Filtros modo aviso (sem exclusao)
  13. Backtests (fixo + dinamico)
  14. AI Engine (rankear jogos por confianca)
  15. Exportar (Excel, CSV, TXT, PDF)


MODOS DE IA
-----------
  Basico        : AI Provider com resumo dos dados
  Especialista  : 40+ variantes de pesos testadas + relatorio completo para IA
  Autoaprendizado: usa pesos ja otimizados por sessoes anteriores


PUTER.JS (IA externa)
---------------------
  - Requer Node.js: https://nodejs.org
  - Sem Node.js: usa modo heuristico local automaticamente
  - Sem API key, sem custo para voce (usuario paga via conta Puter)
  - Modelos: GPT-5.4, Claude, Gemini, DeepSeek e outros


ABAS DO APP WEB
---------------
  RESUMO    : painel principal, botao "Gerar Jogos Inteligentes"
  JOGOS     : os 24 jogos do fechamento
  RANKING   : ranking das 25 dezenas por score
  BACKTEST  : historico de cobertura
  HIBRIDO   : motor hibrido, perfis e tendencias
  AI        : AI Engine - jogos rankeados por confianca
  CHAT      : chat contextual sobre os dados do sistema


ENDPOINTS DA API
----------------
  GET  /api/status              - status da analise principal
  GET  /api/resultado           - resultado completo
  POST /api/analisar            - iniciar analise (modo: basico|especialista)
  POST /api/gerar-inteligente   - botao "Gerar Jogos Inteligentes"
  GET  /api/status-inteligente  - progresso do gerar-inteligente
  GET  /api/resultado-inteligente - jogos com score de confianca
  POST /api/chat                - chat com IA
  GET  /api/node/status         - status do Node.js/Puter.js
  GET  /api/ai/resumo           - dados compactos para Puter.js


AVISO IMPORTANTE
----------------
Este sistema e descritivo - analisa padroes historicos.
Nenhum sistema pode prever resultados de loteria.
A Lotofacil e um jogo de probabilidade.
A Caixa retém ~35% da arrecadacao.

=============================================================
