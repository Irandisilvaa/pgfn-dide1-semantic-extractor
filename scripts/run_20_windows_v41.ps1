$ErrorActionPreference = "Stop"
$env:DIDE1_LLM_BASE_URL = "http://127.0.0.1:8081"
$env:DIDE1_LLM_MODEL = "Qwen3.5-9B"
$env:DIDE1_LLM_TIMEOUT = "300"
$env:DIDE1_LLM_RETRIES = "1"

Remove-Item .\runtime\piloto20_qwen_v41 -Recurse -Force -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m dide1.cli run `
  --input .\dados\entarda.xlsx `
  --start-index 0 `
  --limit 20 `
  --teacher llama `
  --max-candidates 3 `
  --output .\runtime\piloto20_qwen_v41

Get-Content .\runtime\piloto20_qwen_v41\manifest.json
