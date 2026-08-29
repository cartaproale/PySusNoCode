# ============================================================================
#  Baixa todas as bibliotecas em formato .whl para dentro do instalador.
#
#  Este script roda na MAQUINA DE COMPILACAO (com internet livre), nao no
#  computador do usuario. O resultado, a pasta vendor\wheels, e o que permite
#  instalar o PySusNoCode em redes que bloqueiam o pypi.org - o caso de boa
#  parte das prefeituras, hospitais e unidades de saude.
#
#  Por que extrair o Python embarcado antes de baixar:
#  os arquivos .whl sao especificos da versao e da arquitetura do Python. Se
#  baixassemos com o Python da maquina de compilacao, poderiamos gerar wheels
#  de outra versao (3.11, 3.13...) que o Python embarcado nao consegue
#  instalar. Usando o proprio Python que vai ser distribuido, a compatibilidade
#  e garantida por construcao.
#
#  Uso:
#      pwsh installer\baixar_wheels.ps1
# ============================================================================
$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$projeto = Split-Path -Parent $raiz
$vendor = Join-Path $raiz "vendor"
$destino = Join-Path $vendor "wheels"
$requisitos = Join-Path $projeto "requirements.txt"

Write-Host "== Preparando o Python embarcado para resolver as dependencias =="
$temp = Join-Path ([System.IO.Path]::GetTempPath()) "pysusnocode-wheels-$(Get-Random)"
New-Item -ItemType Directory -Force $temp | Out-Null
Expand-Archive -Path (Join-Path $vendor "python-embed-amd64.zip") -DestinationPath $temp -Force

# O ._pth do Python embarcado ignora PYTHONPATH e desliga o site; sem ajustar,
# o pip nem chega a ser importado.
$pth = Get-ChildItem -Path $temp -Filter "python3*._pth" | Select-Object -First 1
$zipLine = (Get-ChildItem -Path $temp -Filter "python3*.zip" | Select-Object -First 1).Name
@($zipLine, ".", "Lib\site-packages", "import site") |
    Set-Content -Path $pth.FullName -Encoding ASCII

$pyExe = Join-Path $temp "python.exe"
$versao = & $pyExe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Host "   Python embarcado: $versao"

& $pyExe (Join-Path $vendor "get-pip.py") --no-warn-script-location | Out-Null
if ($LASTEXITCODE -ne 0) { throw "nao consegui ativar o pip no Python embarcado" }

Write-Host ""
Write-Host "== Baixando os arquivos .whl (varios minutos, ~350 MB) =="
if (Test-Path $destino) { Remove-Item $destino -Recurse -Force }
New-Item -ItemType Directory -Force $destino | Out-Null

# O proprio pip precisa estar disponivel offline: no computador do usuario o
# get-pip.py tenta buscar o pip no pypi.org e e exatamente ai que a instalacao
# morre em rede controlada.
& $pyExe -m pip download pip setuptools wheel `
    --only-binary=:all: --dest $destino --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "falha ao baixar o proprio pip" }

# --only-binary=:all: pelo mesmo motivo da instalacao: o Python embarcado nao
# compila nada. Se um pacote so existir como codigo-fonte, e melhor descobrir
# aqui, na compilacao, do que no computador da unidade de saude.
& $pyExe -m pip download -r $requisitos `
    --only-binary=:all: --dest $destino --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "falha ao baixar as bibliotecas" }

Write-Host ""
Write-Host "== Conferindo se o conjunto se instala sozinho, sem internet =="
# Prova real: instalar num ambiente vazio com --no-index. Se faltar qualquer
# dependencia transitiva, falha aqui e nao na prefeitura.
# Instalamos no proprio Python de teste, e nao com --target: o ._pth do Python
# embarcado ignora o PYTHONPATH, entao uma pasta separada nunca seria
# encontrada na hora de conferir os imports.
& $pyExe -m pip install -r $requisitos `
    --only-binary=:all: --no-index --find-links $destino `
    --no-warn-script-location --disable-pip-version-check | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "o conjunto de wheels esta incompleto: a instalacao offline falhou"
}

# Instalar sem erro nao basta: um pacote pode importar algo que ele esqueceu de
# declarar como dependencia, e ai a instalacao "da certo" e o aplicativo quebra
# no primeiro uso. Foi o que aconteceu com a pysus 2.10 e o PyYAML. Por isso
# carregamos de verdade tudo o que o aplicativo usa.
Write-Host "== Conferindo se as bibliotecas realmente carregam =="
& $pyExe -c "import pysus, PySide6, anthropic, openai, claude_agent_sdk, jupyter_client, ipykernel, nbformat, matplotlib, duckdb, nest_asyncio, openpyxl; print('   todos os imports OK')"
$importsOk = ($LASTEXITCODE -eq 0)
if (-not $importsOk) {
    throw "as bibliotecas foram instaladas mas nao carregam: falta alguma dependencia nao declarada. Acrescente-a ao requirements.txt."
}

$arquivos = Get-ChildItem $destino -Filter *.whl
$tamanho = ($arquivos | Measure-Object Length -Sum).Sum / 1MB
Write-Host ""
Write-Host ("   {0} arquivos .whl, {1:N0} MB" -f $arquivos.Count, $tamanho) -ForegroundColor Green
Write-Host "   Pasta: $destino"

Write-Host ""
Write-Host "== Atualizando TERCEIROS.md a partir das wheels =="
& $pyExe (Join-Path $projeto "installer\gerar_terceiros.py")
if ($LASTEXITCODE -ne 0) { throw "nao consegui gerar o TERCEIROS.md" }

Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Pronto. Agora compile com:" -ForegroundColor Green
Write-Host '   ISCC.exe /DOFFLINE=1 installer\PySusNoCode.iss'
