; ===========================================================================
;  Instalador do PySusNoCode (Inno Setup 6)
;  Compilar com: ISCC.exe PySusNoCode.iss
;  Resultado: Output\PySusNoCode-Setup-<versao>.exe
; ===========================================================================

#define MyAppName "PySusNoCode"
; No GitHub Actions a versao vem da tag (ISCC /DMyAppVersion=X.Y.Z);
; este valor e o padrao para compilacoes locais.
#ifndef MyAppVersion
  #define MyAppVersion "1.5.1"
#endif
#define MyAppPublisher "PySusNoCode"
#define MyAppURL "https://pysus.readthedocs.io"

[Setup]
AppId={{9C2C41E7-5B8A-4F1D-9A47-3D5C1B7A2E90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={userpf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=PySusNoCode-Setup-{#MyAppVersion}
SetupIconFile=assets\pysusnocode.ico
UninstallDisplayIcon={app}\pysusnocode.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de trabalho"
; O claude-agent-sdk ja traz o claude.exe embutido, entao esta tarefa deixou
; de ser necessaria; fica disponivel (desmarcada) para quem quiser o Claude
; Code tambem fora do aplicativo.
Name: "installclaude"; Description: "Instalar tambem o Claude Code no sistema (opcional)"; Flags: unchecked

[Files]
Source: "..\pysusnocode\*"; DestDir: "{app}\app\pysusnocode"; \
    Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs createallsubdirs
Source: "..\requirements.txt"; DestDir: "{app}\app"
Source: "..\README.md"; DestDir: "{app}"
Source: "bootstrap.ps1"; DestDir: "{app}"
Source: "assets\pysusnocode.ico"; DestDir: "{app}"
Source: "vendor\python-embed-amd64.zip"; DestDir: "{app}\vendor"
Source: "vendor\get-pip.py"; DestDir: "{app}\vendor"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; \
    Parameters: "-m pysusnocode"; WorkingDir: "{app}\app"; \
    IconFilename: "{app}\pysusnocode.ico"; Comment: "Analises do DATASUS sem programar"
Name: "{autoprograms}\Reparar {#MyAppName}"; Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\bootstrap.ps1"""; \
    IconFilename: "{app}\pysusnocode.ico"; Comment: "Reinstalar o ambiente Python e as bibliotecas"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; \
    Parameters: "-m pysusnocode"; WorkingDir: "{app}\app"; \
    IconFilename: "{app}\pysusnocode.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\bootstrap.ps1"""; \
    StatusMsg: "Instalando o ambiente Python e as bibliotecas (varios minutos)..."; \
    Flags: waituntilterminated
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""irm https://claude.ai/install.ps1 | iex"""; \
    StatusMsg: "Instalando o Claude Code (claude.ai)..."; \
    Tasks: installclaude; Flags: waituntilterminated
Filename: "{app}\python\pythonw.exe"; Parameters: "-m pysusnocode"; \
    WorkingDir: "{app}\app"; Description: "Abrir o {#MyAppName} agora"; \
    Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
