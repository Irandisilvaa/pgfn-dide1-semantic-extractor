param(
    [string]$LlamaServer = "C:\PGFN\DIDE1\llama\llama-server.exe",
    [string]$Model = "C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf",
    [int]$Port = 8081,
    [int]$Context = 8192,
    [int]$Threads = 8,
    [string]$GpuLayers = "999",
    [int]$Parallel = 1,
    [string]$Reasoning = "off"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $LlamaServer)) { throw "llama-server.exe não encontrado: $LlamaServer" }
if (-not (Test-Path $Model)) { throw "Modelo GGUF não encontrado: $Model" }

Write-Host "=== DIDE1 QWEN3.5 LOCAL / WINDOWS ==="
Write-Host "Executável: $LlamaServer"
Write-Host "Modelo:     $Model"
Write-Host "Host:       127.0.0.1"
Write-Host "Porta:      $Port"
Write-Host "Contexto:   $Context"
Write-Host "GPU layers: $GpuLayers"
Write-Host "Parallel:   $Parallel"
Write-Host "Reasoning:  $Reasoning"
Write-Host "API planilha: NÃO"
Write-Host "O servidor NÃO será exposto na rede."

$help = (& $LlamaServer --help 2>&1 | Out-String)
$argsList = @(
    "-m", $Model,
    "-c", "$Context",
    "-t", "$Threads",
    "-np", "$Parallel",
    "-ngl", "$GpuLayers",
    "--host", "127.0.0.1",
    "--port", "$Port"
)
if ($help -match "--no-webui") { $argsList += "--no-webui" }
if ($help -match "--offline") { $argsList += "--offline" }
if ($help -match "--reasoning") { $argsList += @("--reasoning", $Reasoning) }

& $LlamaServer @argsList
