@echo off
cd /d %~dp0
title Consulta CNPJ - diagnostico (janela visivel)
echo Modo de diagnostico: mostra o que o app esta fazendo e qualquer erro.
echo Feche com Ctrl+C quando terminar.
python servidor.py
pause
