@echo off
chcp 65001 >nul
rem Прежняя (классическая) версия интерфейса
cd /d "%~dp0"
python -m metan gui-classic
if errorlevel 1 pause
