; Установщик Metan (Inno Setup 6). Собирается в GitHub Actions:
;   ISCC.exe /DMyAppVersion=1.2.0 installer\metan.iss
; Перед этим PyInstaller должен собрать dist\Metan.

#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif

[Setup]
AppId={{6F3B2A51-8D7C-4E0B-9A6E-4C2D7B1E9F30}
AppName=Metan
AppVersion={#MyAppVersion}
AppVerName=Metan {#MyAppVersion}
AppPublisher=Metan
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=Установщик Metan - расчёт горения метана в камере
; Без прав администратора ставится в %LOCALAPPDATA%\Programs\Metan;
; можно выбрать установку для всех пользователей (тогда в Program Files).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\Metan
DisableProgramGroupPage=yes
DefaultGroupName=Metan
OutputDir=..\dist
OutputBaseFilename=Metan-Setup
SetupIconFile=..\metan\app\assets_data\metan.ico
UninstallDisplayIcon={app}\Metan.exe
UninstallDisplayName=Metan {#MyAppVersion}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\Metan\*"; DestDir: "{app}"; Excludes: "create_shortcut.bat"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Metan"; Filename: "{app}\Metan.exe"; Comment: "Расчёт горения метана в камере"
Name: "{autoprograms}\Metan - руководство пользователя"; Filename: "{app}\Metan_Руководство_пользователя.docx"
Name: "{autodesktop}\Metan"; Filename: "{app}\Metan.exe"; Comment: "Расчёт горения метана в камере"; Tasks: desktopicon

[Run]
Filename: "{app}\Metan.exe"; Description: "Запустить Metan"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
