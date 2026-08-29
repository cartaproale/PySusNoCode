# ============================================================================
#  PySusNoCode - preparacao do ambiente (roda no computador do usuario)
#  1. Extrai o Python embarcado (python.org) para a pasta do aplicativo
#  2. Ativa o pip
#  3. Instala todas as bibliotecas (pysus, PySide6, anthropic, openai,
#     claude-agent-sdk, jupyter, matplotlib...)
#  Este script tambem serve como "Reparar instalacao".
#
#  Notas de manutencao:
#  - ErrorActionPreference fica em Continue porque comandos nativos (pip)
#    escrevem avisos no stderr; falhas sao detectadas por $LASTEXITCODE.
#  - A instalacao usa --only-binary=:all: de proposito: o Python embarcado
#    nao compila pacotes (nao tem compilador C e o isolamento de build do
#    pip nao funciona com ._pth, que ignora PYTHONPATH). Sem essa opcao, um
#    pacote publicado apenas como codigo-fonte quebra toda a instalacao com
#    "Cannot import 'hatchling.build'".
#  - Tudo o que aparece na tela tambem vai para instalacao.log, para permitir
#    diagnostico depois.
# ============================================================================
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root "python"
$pyExe = Join-Path $py "python.exe"
$marker = Join-Path $root ".ambiente-ok"

# Instalador offline: quando a pasta vendor\wheels existe, todas as bibliotecas
# ja vieram dentro do instalador e nada e baixado da internet. E o que permite
# instalar em prefeituras, hospitais e unidades de saude, onde o acesso ao
# pypi.org costuma ser bloqueado pelo setor de TI.
$wheels = Join-Path $root "vendor\wheels"
$offline = Test-Path $wheels

# Onde gravar o registro. APPDATA pode nao estar definido no ambiente em que o
# instalador executa este script; sem uma alternativa, $logDir viraria um
# caminho relativo e o registro iria parar em lugar nenhum. Ja aconteceu: as
# instalacoes de 25 a 28/08/2026 rodaram sem deixar uma linha sequer, e a
# investigacao ficou sem o unico registro que importava.
$logDir = if ($env:APPDATA) {
    Join-Path $env:APPDATA "PySusNoCode"
} elseif ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE "AppData\Roaming\PySusNoCode"
} else {
    Join-Path $root "registro"
}
New-Item -ItemType Directory -Force $logDir -ErrorAction SilentlyContinue | Out-Null
$log = Join-Path $logDir "instalacao.log"
try {
    "=== $(Get-Date -Format s) - preparando ambiente em $root ===" |
        Out-File -FilePath $log -Append -Encoding UTF8 -ErrorAction Stop
} catch {
    # Sem registro em arquivo, ao menos a tela diz onde ele deveria estar.
    Write-Host "AVISO: nao consegui gravar o registro em $log ($($_.Exception.Message))" `
        -ForegroundColor Yellow
}
Write-Host "Registro desta instalacao: $log" -ForegroundColor DarkGray

function Escrever($texto, $cor = "Gray") {
    Write-Host $texto -ForegroundColor $cor
    $texto | Out-File -FilePath $log -Append -Encoding UTF8
}

function Registrar-Saida {
    # Mostra na tela e grava no log em UTF-8. Nao usar "Tee-Object -FilePath":
    # no Windows PowerShell ele grava em UTF-16, deixando o log ilegivel.
    process {
        Write-Host $_
        ($_ | Out-String).TrimEnd() | Out-File -FilePath $log -Append -Encoding UTF8
    }
}

function Falha($resumo, $dica) {
    Escrever ""
    Escrever "NAO FOI POSSIVEL CONCLUIR A INSTALACAO" "Red"
    Escrever "Motivo: $resumo" "Red"
    if ($dica) { Escrever "" ; Escrever $dica "Yellow" }
    Escrever ""
    Escrever "O registro completo esta em:"
    Escrever "  $log"
    Escrever "Depois de resolver, use o atalho 'Reparar PySusNoCode' no Menu Iniciar."
    Read-Host "Pressione Enter para fechar"
    exit 1
}

function Testar-Internet {
    try {
        $r = Invoke-WebRequest -Uri "https://pypi.org/simple/" -UseBasicParsing `
             -Method Head -TimeoutSec 15
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 400
    } catch {
        return $false
    }
}

Escrever "=============================================================="
Escrever " PySusNoCode - preparando o ambiente"
if ($offline) {
    Escrever " Versao completa: as bibliotecas ja vieram no instalador."
    Escrever " Nao e preciso internet nesta etapa."
} else {
    Escrever " Na primeira vez leva alguns minutos e precisa de internet."
}
Escrever "=============================================================="
Escrever ""

# 1. Python embarcado -------------------------------------------------------
if (-not (Test-Path $pyExe)) {
    Escrever "[1/4] Extraindo o Python..."
    $zip = Join-Path $root "vendor\python-embed-amd64.zip"
    if (-not (Test-Path $zip)) { Falha "o arquivo do Python nao foi encontrado em $zip" "Reinstale o PySusNoCode." }
    try {
        Expand-Archive -Path $zip -DestinationPath $py -Force -ErrorAction Stop
    } catch {
        Falha "nao consegui extrair o Python: $($_.Exception.Message)" `
              "Verifique se o antivirus nao bloqueou a pasta do aplicativo."
    }
} else {
    Escrever "[1/4] Python ja extraido."
}

# 2. Caminhos do Python -----------------------------------------------------
# Sem "import site": o site do usuario (%APPDATA%\Python) nao pode entrar no
# sys.path, senao pacotes de outros Pythons sombreiam os do aplicativo.
Escrever "[2/4] Configurando o Python..."
$pthFile = Get-ChildItem -Path $py -Filter "python3*._pth" | Select-Object -First 1
if ($null -eq $pthFile) { Falha "instalacao do Python incompleta (arquivo ._pth ausente)" "Use 'Reparar PySusNoCode'." }
$zipLine = (Get-ChildItem -Path $py -Filter "python3*.zip" | Select-Object -First 1).Name
try {
    @($zipLine, ".", "..\app", "Lib\site-packages",
      "Lib\site-packages\win32", "Lib\site-packages\win32\lib",
      "Lib\site-packages\Pythonwin") |
        Set-Content -Path $pthFile.FullName -Encoding ASCII -ErrorAction Stop
} catch {
    Falha "nao consegui configurar o Python: $($_.Exception.Message)" ""
}

# 3. pip --------------------------------------------------------------------
cmd /c "`"$pyExe`" -m pip --version >nul 2>&1"
if ($LASTEXITCODE -ne 0) {
    Escrever "[3/4] Instalando o gerenciador de pacotes (pip)..."
    # No modo offline o get-pip.py e apontado para os arquivos que vieram no
    # instalador: sem isso ele tenta buscar o pip no pypi.org, que e onde a
    # instalacao morre em rede controlada.
    $argsPip = @((Join-Path $root "vendor\get-pip.py"), "--no-warn-script-location")
    if ($offline) { $argsPip += @("--no-index", "--find-links", $wheels) }
    & $pyExe @argsPip 2>&1 | Registrar-Saida
    cmd /c "`"$pyExe`" -m pip --version >nul 2>&1"
    if ($LASTEXITCODE -ne 0) {
        if ($offline) {
            Falha "nao consegui ativar o gerenciador de pacotes com os arquivos do instalador" `
                  "O instalador pode estar incompleto ou o antivirus pode ter apagado arquivos da pasta do aplicativo. Libere a pasta no antivirus e use 'Reparar PySusNoCode'; se persistir, baixe o instalador de novo."
        }
        if (-not (Testar-Internet)) {
            Falha "nao consegui instalar o pip e o computador parece estar sem acesso ao pypi.org" `
                  "Duas saidas: (1) baixe a VERSAO COMPLETA do instalador, que traz todas as bibliotecas dentro e nao precisa de internet - e a indicada para prefeituras, hospitais e unidades de saude; ou (2) peca ao setor de TI para liberar pypi.org e files.pythonhosted.org."
        }
        Falha "nao consegui instalar o pip" "Veja o registro para detalhes."
    }
} else {
    Escrever "[3/4] Gerenciador de pacotes pronto."
}

# 4. Bibliotecas ------------------------------------------------------------
if ($offline) {
    Escrever "[4/4] Instalando as bibliotecas que vieram no instalador"
    Escrever "      (pysus, PySide6, anthropic, openai, claude-agent-sdk,"
    Escrever "      jupyter, matplotlib...). Sem internet. Aguarde..."
} else {
    Escrever "[4/4] Baixando e instalando as bibliotecas (pysus, PySide6, anthropic,"
    Escrever "      openai, claude-agent-sdk, jupyter, matplotlib...)."
    Escrever "      Sao cerca de 320 MB; pode levar varios minutos. Aguarde..."
}

$requisitos = Join-Path $root "app\requirements.txt"
$argumentos = @(
    "-m", "pip", "install",
    # Sem --upgrade, o pip nao mexe no que ja satisfaz o requisito: como quase
    # tudo aqui usa piso (>=), quem instalava uma versao nova do aplicativo
    # continuava com as bibliotecas da primeira instalacao. Foi o que
    # aconteceu ate a 1.8.17: o aplicativo estava na 1.8.17 e o
    # claude-agent-sdk parado na 0.2.143, cinco versoes atras, com um
    # claude.exe embutido de cinco dias antes. Correcoes das bibliotecas nunca
    # chegavam a quem ja tinha instalado, e o instalador Completo carregava
    # rodas novas que eram ignoradas.
    "--upgrade",
    "--only-binary=:all:",       # nunca compilar: veja a nota no topo
    "--no-warn-script-location",
    "--disable-pip-version-check",
    "--retries", "5",            # redes instaveis
    "--timeout", "60",
    "-r", $requisitos
)
if ($offline) {
    # --no-index proibe qualquer acesso a rede: se faltar algo, o erro aponta o
    # pacote que falta em vez de ficar minutos tentando alcancar o pypi.org.
    $argumentos += @("--no-index", "--find-links", $wheels)
}

$tentativas = if ($offline) { 1 } else { 2 }
for ($i = 1; $i -le $tentativas; $i++) {
    if ($i -gt 1) {
        Escrever ""
        Escrever "Tentando novamente ($i de $tentativas)..." "Yellow"
        Start-Sleep -Seconds 5
    }
    & $pyExe @argumentos 2>&1 | Registrar-Saida
    if ($LASTEXITCODE -eq 0) { break }
}

if ($LASTEXITCODE -ne 0) {
    if ($offline) {
        Falha "a instalacao das bibliotecas que vieram no instalador falhou" `
              "Procure no registro a linha que comeca com 'ERROR:'. Se aparecer falta de espaco, libere disco (o aplicativo ocupa cerca de 1,1 GB). Se aparecer arquivo ausente ou corrompido, o antivirus pode ter apagado parte da pasta: libere a pasta do aplicativo e use 'Reparar PySusNoCode'."
    }
    if (-not (Testar-Internet)) {
        Falha "o download das bibliotecas falhou e o computador nao esta conseguindo acessar o pypi.org" `
              "A saida mais simples e baixar a VERSAO COMPLETA do instalador, que traz todas as bibliotecas dentro e dispensa internet nesta etapa - foi feita para prefeituras, hospitais e unidades de saude. As outras opcoes sao pedir ao setor de TI para liberar pypi.org e files.pythonhosted.org, ou instalar usando outra rede (um celular como roteador, por exemplo)."
    }
    Falha "a instalacao das bibliotecas falhou (a internet esta funcionando)" `
          "Abra o registro indicado abaixo e procure a linha que comeca com 'ERROR:'. Se aparecer falta de espaco em disco, libere espaco (o aplicativo ocupa cerca de 1,1 GB). Se aparecer bloqueio de antivirus, libere a pasta do aplicativo e tente de novo."
}

# Verificacao final ---------------------------------------------------------
Escrever ""
Escrever "Conferindo a instalacao..."
& $pyExe -c "import pysusnocode, pysus, PySide6, anthropic, openai, claude_agent_sdk, jupyter_client, ipykernel, nbformat, matplotlib" 2>&1 |
    Registrar-Saida
if ($LASTEXITCODE -ne 0) {
    Falha "as bibliotecas foram baixadas, mas o aplicativo nao conseguiu carrega-las" `
          "Use o atalho 'Reparar PySusNoCode' no Menu Iniciar. Se persistir, desinstale e instale novamente."
}

Set-Content -Path $marker -Value (Get-Date -Format "s") -Encoding ASCII
Escrever ""
Escrever "Tudo pronto! Voce ja pode abrir o PySusNoCode." "Green"
Start-Sleep -Seconds 3
exit 0
