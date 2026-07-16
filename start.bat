@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LotofacilPro v4 - Iniciando...

echo.
echo  +--------------------------------------------------+
echo  ^|     LOTOFACIL PRO v4.0 - Iniciando              ^|
echo  +--------------------------------------------------+
echo.

REM --- Node.js (Puter.js) - opcional ---
node --version >nul 2>&1
if %errorlevel% equ 0 (
    if exist "node_server\package.json" (
        if not exist "node_server\node_modules" (
            echo  [Node] Instalando dependencias npm...
            pushd node_server
            call npm install --no-audit --no-fund --quiet
            popd
        )
        echo  [Node] Iniciando servidor Puter.js na porta 3001...
        start "LotofacilPro - Puter.js" cmd /k "cd /d %~dp0node_server && node server.js"
        timeout /t 3 /nobreak >nul
        echo  [Node] OK - Puter.js disponivel
    )
) else (
    echo  [Node] Node.js nao encontrado - usando modo local (OK)
)

echo.
echo  [Flask] Iniciando servidor web na porta 5000...
echo  Acesse no PC    : http://localhost:5000
echo  Acesse no celular: veja o IP exibido abaixo
echo.
echo  +--------------------------------------------------+

python servidor.py

pause
