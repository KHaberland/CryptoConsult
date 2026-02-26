; Inno Setup Script для Крипто-Консультант
; Версия берётся из version.py — при изменении обновите #define MyAppVersion

#define MyAppName "Крипто-Консультант"
#define MyAppDirName "CryptoConsult"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CryptoConsult"
#define MyAppURL "https://github.com/cryptoconsult"
#define MyAppExeName "Run-CryptoConsult.vbs"
#define MyAppStopBat "Stop-CryptoConsult.bat"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={sd}\CryptoConsult
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CryptoConsult-Setup-{#MyAppVersion}
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Backend
Source: "..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,venv\*,*.pyc,.env,.env.local,*.sqlite3,.git\*"
; Frontend (pre-built standalone, собирается в build-installer.ps1)
Source: "..\dist\frontend-standalone\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs
; Корневые файлы
Source: "..\version.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
; Launcher
Source: "Start-CryptoConsult.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Run-CryptoConsult.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop-CryptoConsult.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; Comment: "Запуск Крипто-Консультант"
Name: "{group}\Остановить Крипто-Консультант"; Filename: "{app}\{#MyAppStopBat}"; Comment: "Остановить серверы"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; Tasks: desktopicon; Comment: "Запуск Крипто-Консультант"

[Run]
Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; ========== Секция Uninstall ==========
; Дополнительные действия при удалении приложения

[UninstallDelete]
; Удалить кэш и временные файлы Python
Type: filesandordirs; Name: "{app}\backend\__pycache__"
Type: filesandordirs; Name: "{app}\backend\*.pyc"
Type: filesandordirs; Name: "{app}\backend\*.pyo"
Type: filesandordirs; Name: "{app}\backend\venv"
; Удалить кэш и временные файлы Node.js
Type: filesandordirs; Name: "{app}\frontend\.next"
Type: filesandordirs; Name: "{app}\frontend\out"
Type: filesandordirs; Name: "{app}\frontend\node_modules\.cache"
Type: filesandordirs; Name: "{app}\frontend\.turbo"
; Удалить логи
Type: files; Name: "{app}\backend\*.log"
; Удалить базу данных (раскомментируйте, если нужно удалять данные пользователя при деинсталляции)
; Type: files; Name: "{app}\backend\db.sqlite3"

[UninstallRun]
; Остановить окна CryptoConsult перед удалением (Backend и Frontend, запущенные через Start-CryptoConsult.bat)
; Дочерние процессы python.exe и node.exe завершатся автоматически при закрытии cmd.exe
Filename: "taskkill"; Parameters: "/F /IM cmd.exe /FI ""WINDOWTITLE eq CryptoConsult Backend"""; Flags: runhidden waituntilterminated; RunOnceId: "StopBackend"
Filename: "taskkill"; Parameters: "/F /IM cmd.exe /FI ""WINDOWTITLE eq CryptoConsult Frontend"""; Flags: runhidden waituntilterminated; RunOnceId: "StopFrontend"

[Code]
// Проверка наличия Python и Node.js при установке
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Опционально: раскомментируйте для проверки зависимостей
  // if not Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  //   MsgBox('Python не найден. Установите Python 3.10+ с https://python.org', mbError, MB_OK);
end;

// Подтверждение при начале удаления
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('Вы уверены, что хотите удалить Крипто-Консультант?' + #13#10 + #13#10 +
    'Если приложение запущено, оно будет автоматически закрыто.' + #13#10 +
    'Данные портфелей (если есть) будут сохранены в базе данных.',
    mbConfirmation, MB_YESNO) = IDYES;
end;
