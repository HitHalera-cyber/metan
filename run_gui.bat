@echo off
chcp 65001 >nul
rem Запуск десктопной программы
cd /d "%~dp0"
python -m metan gui
if errorlevel 1 pause
