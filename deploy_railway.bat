@echo off
chcp 65001 >nul 2>&1
title LotofacilPro v4 - Deploy Railway
echo.
echo  +--------------------------------------------------+
echo  ^|   LotofacilPro v4 - Deploy na Nuvem (Railway)   ^|
echo  +--------------------------------------------------+
echo.

REM Verificar se Railway CLI esta instalado
railway --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Railway CLI nao encontrado. Instalando...
    npm install -g @railway/cli
    if %errorlevel% neq 0 (
        echo  ERRO: npm nao encontrado.
        echo  Instale Node.js em https://nodejs.org e tente novamente.
        pause
        exit /b 1
    )
)
echo  Railway CLI: OK

REM Verificar Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Git nao encontrado. Instale em https://git-scm.com
    pause
    exit /b 1
)
echo  Git: OK
echo.

REM Inicializar git se necessario
if not exist ".git" (
    echo  Inicializando repositorio Git...
    git init
    git add .
    git commit -m "LotofacilPro v4 - Deploy inicial"
)

echo  Fazendo login no Railway...
railway login

echo.
echo  Criando projeto no Railway...
railway init

echo.
echo  Fazendo deploy...
railway up

echo.
echo  +--------------------------------------------------+
echo  ^|  Deploy concluido!                               ^|
echo  ^|                                                  ^|
echo  ^|  Acesse: railway open                            ^|
echo  ^|  Copie a URL e acesse do iPhone/Android          ^|
echo  +--------------------------------------------------+
echo.
railway open
pause
