$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Сначала создайте .venv и установите requirements-lock.txt по README.md.'
}
$env:PYTHONPATH = Join-Path $projectRoot 'src'
& $pythonPath -m password_manager
exit $LASTEXITCODE
