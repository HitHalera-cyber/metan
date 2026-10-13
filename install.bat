@echo off
chcp 65001 >nul
rem Установка зависимостей (нужен Python 3.9+ с python.org, галочка "Add to PATH")
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pause
