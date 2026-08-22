# ============================================================================
#  PySusNoCode - preparacao do ambiente (roda no computador do usuario)
#  1. Extrai o Python embarcado (python.org) para a pasta do aplicativo
#  2. Ativa o pip
#  3. Instala todas as bibliotecas (pysus, PySide6, anthropic, claude-agent-sdk,
#     jupyter, matplotlib...)
#  Este script tambem serve como "Reparar instalacao".
#
#  Nota: ErrorActionPreference fica em Continue porque comandos nativos (pip)
#  escrevem avisos no stderr; falhas sao detectadas por $LASTEXITCODE.
# ============================================================================
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root "python"
$pyExe = Join-Path $py "python.exe"
$marker = Join-Path $root ".ambiente-ok"

function Falha($msg) {
    Write-Host ""
    Write-Host "ERRO: $msg" -ForegroundColor Red
    Write-Host "Verifique sua conexao com a internet e rode novamente pelo atalho"
    Write-Host "'Reparar PySusNoCode' no Menu Iniciar."
    Read-Host "Pressione Enter para fechar"
    exit 1
}

Write-Host "=============================================================="
Write-Host " PySusNoCode - preparando o ambiente (isso demora alguns"
Write-Host " minutos na primeira vez; precisa de conexao com a internet)"
Write-Host "=============================================================="
Write-Host ""

# 1. Python embarcado -------------------------------------------------------
if (-not (Test-Path $pyExe)) {
    Write-Host "[1/4] Extraindo o Python embarcado..."
    $zip = Join-Path $root "vendor\python-embed-amd64.zip"
    if (-not (Test-Path $zip)) { Falha "arquivo do Python nao encontrado em $zip" }
    try {
        Expand-Archive -Path $zip -DestinationPath $py -Force -ErrorAction Stop
    } catch {
        Falha "nao consegui extrair o Python: $($_.Exception.Message)"
    }
} else {
    Write-Host "[1/4] Python ja extraido."
}

# 2. Configura os caminhos do Python ----------------------------------------
# IMPORTANTE: sem "import site" — o site do usuario do Windows
# (%APPDATA%\Python\...) NUNCA deve entrar no sys.path, senao pacotes de
# outros Pythons do usuario sombreiam os do aplicativo. O site-packages
# embarcado e listado explicitamente.
Write-Host "[2/4] Configurando o Python..."
$pthFile = Get-ChildItem -Path $py -Filter "python3*._pth" | Select-Object -First 1
if ($null -eq $pthFile) { Falha "arquivo ._pth nao encontrado no Python embarcado" }
$zipLine = (Get-ChildItem -Path $py -Filter "python3*.zip" | Select-Object -First 1).Name
# Os tres caminhos do pywin32 substituem o processamento do pywin32.pth
# (sem "import site" nenhum arquivo .pth e processado).
try {
    @($zipLine, ".", "..\app", "Lib\site-packages",
      "Lib\site-packages\win32", "Lib\site-packages\win32\lib",
      "Lib\site-packages\Pythonwin") |
        Set-Content -Path $pthFile.FullName -Encoding ASCII -ErrorAction Stop
} catch {
    Falha "nao consegui configurar o Python: $($_.Exception.Message)"
}

# 3. pip --------------------------------------------------------------------
cmd /c "`"$pyExe`" -m pip --version >nul 2>&1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[3/4] Instalando o pip..."
    & $pyExe (Join-Path $root "vendor\get-pip.py") --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { Falha "nao consegui instalar o pip" }
} else {
    Write-Host "[3/4] pip ja instalado."
}

# 4. Bibliotecas ------------------------------------------------------------
Write-Host "[4/4] Instalando as bibliotecas (pysus, PySide6, anthropic,"
Write-Host "      claude-agent-sdk, jupyter, matplotlib...). Aguarde..."
& $pyExe -m pip install --no-warn-script-location -r (Join-Path $root "app\requirements.txt")
if ($LASTEXITCODE -ne 0) { Falha "a instalacao das bibliotecas falhou" }

# Verificacao final ---------------------------------------------------------
& $pyExe -c "import pysusnocode, pysus, PySide6, anthropic, claude_agent_sdk, jupyter_client, ipykernel, nbformat, matplotlib"
if ($LASTEXITCODE -ne 0) { Falha "a verificacao final das bibliotecas falhou" }

Set-Content -Path $marker -Value (Get-Date -Format "s") -Encoding ASCII
Write-Host ""
Write-Host "Ambiente pronto! Voce ja pode abrir o PySusNoCode." -ForegroundColor Green
Start-Sleep -Seconds 2
exit 0
