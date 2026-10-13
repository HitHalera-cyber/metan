@echo off
chcp 65001 >nul
rem Сборка Metan.exe (новая версия) и Metan-Classic.exe (прежняя) в папку dist
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name Metan --collect-data customtkinter --collect-data docx metan_gui.pyw
python -m PyInstaller --noconfirm --windowed --name Metan-Classic metan_classic.pyw
echo.
echo Готово: dist\Metan\Metan.exe и dist\Metan-Classic\Metan-Classic.exe
pause
