param(
    [string]$Input = ".\dados\entrada.xlsx",
    [string]$Output = ".\runtime\piloto500_qwen_v42"
)

$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "DIDE1 v4.2 - PILOTO 500 DECISOES UNICAS"
Write-Host "======================================"

if (!(Test-Path $Input)) {
    throw "Planilha de entrada nao encontrada: $Input"
}

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Ambiente virtual nao encontrado em .venv"
}

Write-Host "Versao do repositorio:"
Get-Content .\VERSION

try {
    $health = Invoke-RestMethod http://127.0.0.1:8081/health -TimeoutSec 5
    Write-Host "Qwen/llama-server: $($health.status)"
} catch {
    Write-Host ""
    Write-Host "ERRO: llama-server nao respondeu em http://127.0.0.1:8081"
    Write-Host "Abra outro PowerShell e execute:"
    Write-Host 'C:\PGFN\DIDE1\llama\llama-server.exe -m C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf -c 8192 -t 8 -np 1 -ngl 999 --host 127.0.0.1 --port 8081 --no-webui --reasoning off'
    throw
}

if (-not $env:DIDE1_LLM_BASE_URL) { $env:DIDE1_LLM_BASE_URL = "http://127.0.0.1:8081" }
if (-not $env:DIDE1_LLM_MODEL) { $env:DIDE1_LLM_MODEL = "Qwen3.5-9B" }
if (-not $env:DIDE1_LLM_TIMEOUT) { $env:DIDE1_LLM_TIMEOUT = "300" }
if (-not $env:DIDE1_LLM_RETRIES) { $env:DIDE1_LLM_RETRIES = "1" }

Remove-Item $Output -Recurse -Force -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m dide1.cli run `
    --input $Input `
    --start-index 0 `
    --unique-limit 500 `
    --teacher llama `
    --max-candidates 3 `
    --output $Output

Write-Host ""
Write-Host "===== MANIFEST ====="
Get-Content "$Output\manifest.json"

Write-Host ""
Write-Host "===== ERROS / RECUPERACOES ====="
if ((Get-Item "$Output\errors.jsonl").Length -eq 0) {
    Write-Host "Nenhum erro ou fallback registrado."
} else {
    Get-Content "$Output\errors.jsonl"
}

Write-Host ""
Write-Host "Workbook de revisao: $Output\review.xlsx"
Write-Host "Aba principal: revisao_consolidada"
Write-Host "Aba de qualidade: metricas"
