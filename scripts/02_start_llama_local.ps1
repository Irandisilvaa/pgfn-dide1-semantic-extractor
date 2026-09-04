function Import-DotEnv {
    param([string]$Path = ".env")

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()

        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (
            $value.Length -ge 2 -and
            (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            )
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$ErrorActionPreference = "Stop"
Import-DotEnv

$LlamaServer = $env:LLAMA_SERVER_BIN
$Model = $env:MODEL_PATH
$Port = if ($env:LLAMA_PORT) { [int]$env:LLAMA_PORT } else { 8081 }
$Context = if ($env:LLAMA_CTX) { [int]$env:LLAMA_CTX } else { 8192 }
$Threads = if ($env:LLAMA_THREADS) { [int]$env:LLAMA_THREADS } else { 8 }
$GpuLayers = if ($env:LLAMA_GPU_LAYERS) { $env:LLAMA_GPU_LAYERS } else { "999" }
$Parallel = if ($env:LLAMA_PARALLEL) { [int]$env:LLAMA_PARALLEL } else { 1 }

if (-not $LlamaServer) {
    throw "LLAMA_SERVER_BIN não definido no .env"
}

if (-not $Model) {
    throw "MODEL_PATH não definido no .env"
}

if (-not (Test-Path $LlamaServer)) {
    throw "llama-server.exe não encontrado: $LlamaServer"
}

if (-not (Test-Path $Model)) {
    throw "Modelo GGUF não encontrado: $Model"
}

Write-Host "=== LLM LOCAL PGFN / WINDOWS ==="
Write-Host "Executável: $LlamaServer"
Write-Host "Modelo:     $Model"
Write-Host "Host:       127.0.0.1"
Write-Host "Porta:      $Port"
Write-Host "Contexto:   $Context"
Write-Host "GPU layers: $GpuLayers"
Write-Host "Parallel:   $Parallel"
Write-Host ""
Write-Host "O servidor NÃO será exposto na rede."

# Verifica opções suportadas pela versão instalada.
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

if ($help -match "--no-webui") {
    $argsList += "--no-webui"
}

if ($help -match "--offline") {
    $argsList += "--offline"
}

& $LlamaServer @argsList
