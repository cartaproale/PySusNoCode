; ===========================================================================
;  Instalador do PySusNoCode (Inno Setup 6)
;
;  Duas versoes saem deste mesmo arquivo:
;
;    ISCC.exe PySusNoCode.iss
;        Versao enxuta (~14 MB). Baixa as bibliotecas do pypi.org durante a
;        instalacao. Serve para a maioria dos computadores domesticos.
;
;    ISCC.exe /DOFFLINE=1 PySusNoCode.iss
;        Versao completa (~350 MB). Traz todas as bibliotecas dentro e nao
;        acessa a internet para instalar. E a indicada para prefeituras,
;        hospitais e unidades de saude, onde o pypi.org costuma ser bloqueado.
;        Exige rodar antes: pwsh installer\baixar_wheels.ps1
; ===========================================================================

#define MyAppName "PySusNoCode"
; No GitHub Actions a versao vem da tag (ISCC /DMyAppVersion=X.Y.Z);
; este valor e o padrao para compilacoes locais.
#ifndef MyAppVersion
  #define MyAppVersion "1.8.29"
#endif
#define MyAppPublisher "PySusNoCode"
#define MyAppURL "https://pysus.readthedocs.io"

; A mensagem da barra de progresso muda conforme a versao. O pre-processador
; nao pode ser usado dentro de uma linha continuada da secao [Run], por isso
; o texto vira uma variavel aqui em cima.
#ifdef OFFLINE
  #define StatusInstalar "Instalando o ambiente Python e as bibliotecas (sem internet)..."
#else
  #define StatusInstalar "Instalando o ambiente Python e as bibliotecas (varios minutos)..."
#endif

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
#ifdef OFFLINE
OutputBaseFilename=PySusNoCode-Setup-Completo-{#MyAppVersion}
; Os .whl ja sao arquivos comprimidos: comprimir de novo no modo maximo
; gastaria muito tempo de compilacao para economizar quase nada.
Compression=lzma2/normal
SolidCompression=no
#else
OutputBaseFilename=PySusNoCode-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
#endif
SetupIconFile=assets\pysusnocode.ico
UninstallDisplayIcon={app}\pysusnocode.ico
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
; O aplicativo e MIT, mas distribui bibliotecas GPL, LGPL e AGPL. Estes
; dois arquivos sao a atribuicao devida — vao nas duas versoes, porque a
; versao leve baixa exatamente as mesmas bibliotecas na primeira execucao.
Source: "..\LICENSE"; DestDir: "{app}"
Source: "..\TERCEIROS.md"; DestDir: "{app}"
Source: "bootstrap.ps1"; DestDir: "{app}"
Source: "assets\pysusnocode.ico"; DestDir: "{app}"
; Tambem um zip: comprimir de novo so gasta memoria do compressor, que
; ja estourou duas vezes hoje no islzma.dll.
Source: "vendor\python-embed-amd64.zip"; DestDir: "{app}\vendor"; Flags: nocompression
Source: "vendor\get-pip.py"; DestDir: "{app}\vendor"
; Notebooks de exemplo, ~3 MB. Vao nas duas versoes do instalador: e o que faz
; a lista de exemplos abrir na hora e funcionar sem internet.
Source: "exemplos\*"; DestDir: "{app}\exemplos"; Flags: recursesubdirs createallsubdirs
#ifdef OFFLINE
; Todas as bibliotecas, em .whl. A presenca desta pasta e o que faz o
; bootstrap.ps1 instalar sem tocar na internet.
; nocompression: os .whl ja sao zips. Passa-los pelo LZMA nao encolhe nada e
; derruba o compilador — a wheel do claude-agent-sdk tem 92 MB e carrega um
; claude.exe de 207 MB dentro; comprimir isso estourou o islzma.dll duas vezes
; seguidas na 1.8.22, e na 1.8.20 so passou depois de 3,6 horas de compilacao.
Source: "vendor\wheels\*"; DestDir: "{app}\vendor\wheels"; Flags: recursesubdirs nocompression
#endif

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
    StatusMsg: "{#StatusInstalar}"; \
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


