@echo off
title Limpiador de Marcadores de Chrome
python "%~dp0limpiador_marcadores_chrome_gui.py"
if errorlevel 1 pause
