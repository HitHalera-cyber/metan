@echo off
chcp 65001 >nul
rem Сборка Metan.exe (папка dist\Metan), Python для запуска не нужен
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name Metan metan_gui.pyw
echo.
echo Готово: dist\Metan\Metan.exe
pause
