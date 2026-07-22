; Instalador do Gestão de Arranjo (Windows), gerado no CI com Inno Setup.
; A versão é passada por linha de comando:
;   ISCC /DMyAppVersion=1.2.3 installer.iss
; Empacota a pasta build\windows\ (saída do `flet build windows`) num setup.exe.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "Gestão de Arranjo"
#define MyAppExeName "GestaoArranjo.exe"

[Setup]
; AppId identifica o app para atualizacoes/desinstalacao — NAO mudar entre versoes.
AppId={{7C3D9E2A-1B4F-4A8E-9D6C-2E5F8A1B3C4D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=IonTech
DefaultDirName={autopf}\GestaoArranjo
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir=.
OutputBaseFilename=GestaoArranjo-{#MyAppVersion}-windows-instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Instalacao por usuario (sem pedir admin): pasta gravavel, sem UAC.
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "build\windows\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
