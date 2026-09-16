param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$RunName = "dide1-slm-v1"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Source = "artifacts/models/$RunName"
if (-not (Test-Path $Source)) { throw "Modelo não encontrado: $Source" }
$Target = Join-Path $Destination $RunName
New-Item -ItemType Directory -Force -Path $Target | Out-Null
Copy-Item "$Source\*" $Target -Recurse -Force
Write-Host "Backup concluído em: $Target"
Write-Host "Verifique SHA256SUMS.json no destino."
