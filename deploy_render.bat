@echo off
chcp 65001 >nul 2>&1
title LotofacilPro v4 - Deploy Render
echo.
echo  +--------------------------------------------------+
echo  ^|   LotofacilPro v4 - Deploy no Render.com        ^|
echo  +--------------------------------------------------+
echo.
echo  Passos para fazer o deploy no Render.com (gratuito):
echo.
echo  1. Acesse https://github.com e crie uma conta (se nao tiver)
echo.
echo  2. Crie um repositorio novo no GitHub:
echo     - Clique em "New repository"
echo     - Nome: lotofacil-pro
echo     - Deixe publico
echo.
echo  3. Faca upload dos arquivos:
echo     git init
echo     git add .
echo     git commit -m "LotofacilPro v4"
echo     git remote add origin https://github.com/SEU_USUARIO/lotofacil-pro.git
echo     git push -u origin main
echo.
echo  4. Acesse https://render.com e crie uma conta
echo.
echo  5. Clique em "New Web Service"
echo     - Conecte seu repositorio GitHub
echo     - Build Command: pip install -r requirements_nuvem.txt
echo     - Start Command: gunicorn servidor_nuvem:app --workers 2 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT
echo.
echo  6. Clique em "Create Web Service"
echo     - Aguarde o deploy (2-5 minutos)
echo     - Copie a URL: https://lotofacil-pro.onrender.com
echo.
echo  7. Abra a URL no iPhone ou Android
echo     iPhone: Safari - menu compartilhar - "Adicionar a Tela Inicial"
echo     Android: Chrome - menu - "Adicionar a tela inicial"
echo.
echo  Abrindo GitHub e Render no navegador...
start https://github.com/new
timeout /t 2 >nul
start https://render.com
echo.
pause
