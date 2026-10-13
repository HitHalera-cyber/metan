@echo off
chcp 65001 >nul
rem Создаёт ярлык «Metan» со значком-ракетой на рабочем столе.
rem Работает и в папке с Metan.exe, и в папке с исходниками (запуск через Python).
cd /d "%~dp0"
set "HERE=%~dp0"
if exist "%HERE%Metan.exe" (
  set "TARGET=%HERE%Metan.exe"
  set "ARGS="
  set "ICON=%HERE%Metan.exe"
) else (
  set "TARGET=pythonw.exe"
  set "ARGS=-m metan gui"
  set "ICON=%HERE%metan\app\assets_data\metan.ico"
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Metan.lnk');" ^
  "$s.TargetPath=$env:TARGET; $s.Arguments=$env:ARGS; $s.WorkingDirectory=$env:HERE;" ^
  "$s.IconLocation=$env:ICON; $s.Description='Metan - methane combustion'; $s.Save()"
if errorlevel 1 (echo Не удалось создать ярлык) else (echo Ярлык Metan создан на рабочем столе)
pause
