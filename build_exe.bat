@echo off
chcp 65001 >nul
rem Сборка Metan.exe (новая версия) и Metan-Classic.exe (прежняя) в папку dist
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name Metan --icon metan\app\assets_data\metan.ico --collect-data customtkinter --collect-data docx --collect-data metan metan_gui.pyw
copy /y "docs\Metan_Руководство_пользователя.docx" dist\Metan\
copy /y create_shortcut.bat dist\Metan\
python -m PyInstaller --noconfirm --windowed --name Metan-Classic --icon metan\app\assets_data\metan.ico --collect-data metan metan_classic.pyw
echo.
echo Готово: dist\Metan\Metan.exe и dist\Metan-Classic\Metan-Classic.exe
pause
