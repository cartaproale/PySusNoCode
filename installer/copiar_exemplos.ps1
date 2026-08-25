# ============================================================================
#  Traz os notebooks de exemplo para dentro do instalador.
#
#  Os exemplos moram noutro repositorio (PySusNoCode-Exemplos), onde cada um e
#  executado com dados reais antes de publicado. Uma copia vai junto com o
#  aplicativo para que a lista abra na hora e funcione mesmo sem internet - o
#  caso das unidades de saude e prefeituras, onde a rede e controlada. Com
#  internet o aplicativo busca a versao mais recente no GitHub; a copia local
#  e a rede de seguranca.
#
#  Sao cerca de 3 MB: cabe ate no instalador enxuto.
#
#  Uso:
#      pwsh installer\copiar_exemplos.ps1
# ============================================================================
$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$projeto = Split-Path -Parent $raiz
$destino = Join-Path $raiz "exemplos"
$vizinho = Join-Path (Split-Path -Parent $projeto) "PySusNoCode-Exemplos"

if (Test-Path $destino) { Remove-Item $destino -Recurse -Force }
New-Item -ItemType Directory -Force $destino | Out-Null

if (Test-Path (Join-Path $vizinho "exemplos.json")) {
    Write-Host "Copiando do repositorio vizinho: $vizinho"
    $origem = $vizinho
} else {
    Write-Host "Repositorio de exemplos nao encontrado ao lado; clonando do GitHub"
    $temp = Join-Path ([System.IO.Path]::GetTempPath()) "exemplos-$(Get-Random)"
    git clone --depth 1 https://github.com/cartaproale/PySusNoCode-Exemplos.git $temp
    if ($LASTEXITCODE -ne 0) { throw "nao consegui obter os exemplos" }
    $origem = $temp
}

$catalogo = Join-Path $origem "exemplos.json"
if (-not (Test-Path $catalogo)) {
    throw "o catalogo exemplos.json nao existe. Rode _ferramentas\gerar_catalogo.py no repositorio de exemplos."
}
Copy-Item $catalogo $destino

# So os notebooks e o catalogo: nada de ferramentas, .git ou documentacao.
$lista = (Get-Content $catalogo -Raw -Encoding UTF8 | ConvertFrom-Json).exemplos
foreach ($item in $lista) {
    $de = Join-Path $origem ($item.arquivo -replace "/", "\")
    if (-not (Test-Path $de)) {
        throw "o catalogo cita $($item.arquivo), que nao existe. Regere o catalogo."
    }
    $para = Join-Path $destino ($item.arquivo -replace "/", "\")
    New-Item -ItemType Directory -Force (Split-Path -Parent $para) | Out-Null
    Copy-Item $de $para
}

$arquivos = Get-ChildItem $destino -Recurse -File
$tamanho = ($arquivos | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("{0} exemplos copiados, {1:N1} MB" -f $lista.Count, $tamanho) -ForegroundColor Green
