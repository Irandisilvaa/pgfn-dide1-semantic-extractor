param(
    [string]$Input = ".\runtime\piloto500_qwen_v42\review.xlsx",
    [string]$Output = ".\runtime\piloto500_qwen_v42\review_compacto_v43.xlsx"
)

$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "DIDE1 v4.3 - REBUILD REVIEW COMPACTO"
Write-Host "SEM NOVA INFERENCIA / SEM QWEN"
Write-Host "======================================"

if (!(Test-Path $Input)) {
    throw "Review de origem nao encontrado: $Input"
}

.\.venv\Scripts\python.exe -m dide1.cli rebuild-review `
    --review $Input `
    --output $Output

Write-Host ""
Write-Host "Novo workbook: $Output"
Write-Host "Aba principal: revisao"
Write-Host "Aba para leitura integral: leitura_decisoes"
Write-Host "Aba de qualidade: metricas"
Start-Process $Output
