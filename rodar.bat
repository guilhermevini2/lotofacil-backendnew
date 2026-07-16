@echo off
chcp 65001 >nul 2>&1
title LotofacilPro v4

:MENU
cls
echo.
echo  +--------------------------------------------------+
echo  ^|     LOTOFACIL PRO v4.0 — AI Premium             ^|
echo  ^|     Puter.js + AI Engine + Modo Especialista     ^|
echo  +--------------------------------------------------+
echo.
echo  [1] Abrir App Web (recomendado)
echo  [2] Analise basica (terminal)
echo  [3] Analise modo ESPECIALISTA (terminal)
echo  [4] Iniciar servidor Node.js (Puter.js)
echo  [5] Limpar cache
echo  [6] Abrir relatorios
echo  [7] Abrir jogos
echo  [8] Verificar dependencias
echo  [9] Sair
echo.
set /p OPCAO="  Escolha [1-9]: "

if "%OPCAO%"=="1" goto APP_WEB
if "%OPCAO%"=="2" goto BASICO
if "%OPCAO%"=="3" goto ESPECIALISTA
if "%OPCAO%"=="4" goto NODE
if "%OPCAO%"=="5" goto LIMPAR
if "%OPCAO%"=="6" goto REL
if "%OPCAO%"=="7" goto JOGOS
if "%OPCAO%"=="8" goto DEPS
if "%OPCAO%"=="9" goto FIM
goto MENU

:APP_WEB
cls
echo.
echo  Iniciando LotofacilPro v4...
echo  (Node.js + Flask serao iniciados automaticamente se disponiveis)
echo.
call start.bat
goto MENU

:BASICO
cls
echo.
echo  Iniciando analise basica...
echo.
python main.py
pause
goto MENU

:ESPECIALISTA
cls
echo.
echo  Iniciando modo ESPECIALISTA...
echo  (backtests massivos + AI completa — pode demorar alguns minutos)
echo.
python main.py --especialista
pause
goto MENU

:NODE
cls
echo.
echo  Iniciando servidor Node.js (Puter.js)...
echo  Mantenha essa janela aberta para usar o Puter.js.
echo.
if not exist "node_server" (
    echo  ERRO: pasta node_server nao encontrada.
    pause
    goto MENU
)
cd node_server
npm start
cd ..
pause
goto MENU

:LIMPAR
cls
echo.
python main.py --limpar-cache --sem-graficos --sem-excel
pause
goto MENU

:REL
if exist "relatorios\" ( explorer relatorios ) else (
    echo  Execute a analise primeiro.
    timeout /t 2 >nul
)
goto MENU

:JOGOS
if exist "jogos\" ( explorer jogos ) else (
    echo  Execute a analise primeiro.
    timeout /t 2 >nul
)
goto MENU

:DEPS
cls
echo.
python -c "
pkgs=['requests','openpyxl','matplotlib','reportlab','flask','scikit-learn','numpy','xgboost']
for p in pkgs:
    try: __import__(p); print(f'  OK       {p}')
    except: print(f'  FALTANDO {p}')
print()
try:
    import subprocess
    r = subprocess.run(['node','--version'], capture_output=True, text=True)
    print(f'  OK       Node.js {r.stdout.strip()}')
except:
    print('  FALTANDO Node.js  --> https://nodejs.org')
"
echo.
pause
goto MENU

:FIM
exit
