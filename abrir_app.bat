@echo off
chcp 65001 >nul 2>&1
title Lotofacil Pro - App Web

cls
echo.
echo  +--------------------------------------------------+
echo  ^|        LOTOFACIL PRO - App Web                   ^|
echo  +--------------------------------------------------+
echo.
echo  Iniciando servidor local...
echo  O navegador vai abrir automaticamente.
echo.
echo  Para instalar como app no CELULAR:
echo    1. Conecte o celular na MESMA rede Wi-Fi deste PC
echo    2. Veja o endereco "No celular, acesse: ..." abaixo
echo    3. Abra esse endereco no navegador do celular
echo    4. Toque em "Adicionar a tela inicial" ou "Instalar app"
echo.
echo  Mantenha esta janela aberta enquanto usa o app.
echo  Para parar, feche esta janela ou pressione CTRL+C.
echo.
echo  --------------------------------------------------
echo.

python servidor.py

echo.
echo  --------------------------------------------------
echo  Servidor encerrado.
pause
