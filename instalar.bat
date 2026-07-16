@echo off
chcp 65001 >nul 2>&1
title LotofacilPro v4 - Instalador
color 0B
echo.
echo  +--------------------------------------------------+
echo  ^|     LOTOFACIL PRO v4.0 -- Instalador            ^|
echo  +--------------------------------------------------+
echo.

echo  [1/4] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERRO: Python nao encontrado!
    echo  Baixe em: https://python.org/downloads
    echo  IMPORTANTE: marque "Add Python to PATH"
    start https://python.org/downloads
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  OK - %%v

echo.
echo  [2/4] Instalando dependencias Python...
python -m pip install --upgrade pip --quiet
python -m pip install requests openpyxl matplotlib reportlab flask scikit-learn numpy scipy --quiet
if %errorlevel% neq 0 (
    echo  ERRO ao instalar dependencias Python.
    echo  Tente executar como Administrador.
    pause
    exit /b 1
)
echo  OK

echo.
echo  [3/4] Criando diretorios...
if not exist "cache"      mkdir cache
if not exist "relatorios" mkdir relatorios
if not exist "jogos"      mkdir jogos
echo  OK

echo.
echo  [4/4] Verificando Node.js (opcional - para Puter.js)...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Node.js NAO encontrado.
    echo  O sistema funcionara normalmente sem ele.
    echo.
    echo  Para ativar o Puter.js no futuro:
    echo    1. Baixe Node.js em: https://nodejs.org
    echo    2. Execute instalar.bat novamente
    echo  Continuando sem Node.js...
    goto SEM_NODE
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo  Node.js %%v encontrado
if exist "node_server\package.json" (
    echo  Instalando dependencias do servidor Node.js...
    cd node_server
    call npm install --quiet 2>nul
    cd ..
    echo  OK - Puter.js pronto
) else (
    echo  pasta node_server nao encontrada - pulando
)
goto FIM_NODE

:SEM_NODE
:FIM_NODE

echo.
echo  +--------------------------------------------------+
echo  ^|  Instalacao concluida!                           ^|
echo  ^|                                                  ^|
echo  ^|  Execute rodar.bat para iniciar o programa.      ^|
echo  +--------------------------------------------------+
echo.
pause
