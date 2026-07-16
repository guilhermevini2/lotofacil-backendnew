#!/usr/bin/env bash
# ============================================================
#  LotofacilPro v3 — Inicializador (Linux / macOS)
#  Sobe o servidor Node.js (Puter.js, porta 3001) e o
#  servidor Flask (PWA + API, porta 5000) juntos.
# ============================================================
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  LotofacilPro v3 — Iniciando servidores"
echo "============================================================"

# --- 1) Servidor Node.js (Puter.js) --------------------------
if [ ! -d "node_server/node_modules" ]; then
  echo "[Node] Instalando dependencias (npm install)..."
  ( cd node_server && npm install --no-audit --no-fund )
fi

echo "[Node] Iniciando servidor Puter.js na porta 3001..."
( cd node_server && node server.js ) &
NODE_PID=$!

# Garante que o Node seja encerrado ao sair do script.
trap "echo; echo 'Encerrando servidores...'; kill $NODE_PID 2>/dev/null || true" EXIT INT TERM

sleep 2

# --- 2) Servidor Flask (PWA) ---------------------------------
echo "[Flask] Iniciando servidor web na porta 5000..."
echo "  Acesse: http://localhost:5000"
echo "  (CTRL+C encerra ambos os servidores)"
echo "============================================================"

python3 servidor.py

# Ao encerrar o Flask, o trap acima mata o Node.
