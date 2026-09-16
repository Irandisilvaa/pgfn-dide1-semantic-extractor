$ErrorActionPreference = "Stop"

$Model = "bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M"
$Port = 8081

$Server = (Get-Command llama-server -ErrorAction SilentlyContinue)
if (-not $Server) {
  Write-Host "llama-server não está no PATH."
  Write-Host "Coloque llama-server.exe (build CUDA) no PATH e rode novamente."
  exit 1
}

$help = (& $Server.Source --help 2>&1 | Out-String)
$extra = @()
if ($help -match "--reasoning") {
  $extra += @("--reasoning", "off")
}

& $Server.Source `
  -hf $Model `
  -c 8192 `
  -t 6 `
  -ngl 999 `
  -np 1 `
  --host 127.0.0.1 `
  --port $Port `
  --no-webui `
  @extra
