@echo off
chcp 65001 >nul
rem Расчёт без окна; результаты в папке results
cd /d "%~dp0"
python -m metan -o results %*
pause
