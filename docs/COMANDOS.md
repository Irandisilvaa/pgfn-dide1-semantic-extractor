# Comandos de execução — DIDE1 v4.2

## Preparação na máquina PGFN

```powershell
cd C:\PGFN\DIDE1\v3.1\pgfn-dide1-semantic-extractor
.\.venv\Scripts\python.exe -m pip install . --no-deps --no-cache-dir --force-reinstall
.\.venv\Scripts\python.exe -m pytest -q
Get-Content VERSION
Get-Item .\dados\entarda.xlsx
```

## Qwen3.5-9B

Em outro PowerShell:

```powershell
C:\PGFN\DIDE1\llama\llama-server.exe -m C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf -c 8192 -t 8 -np 1 -ngl 999 --host 127.0.0.1 --port 8081 --no-webui --reasoning off
```

Na janela do projeto:

```powershell
Invoke-RestMethod http://127.0.0.1:8081/health
$env:DIDE1_LLM_BASE_URL = "http://127.0.0.1:8081"
$env:DIDE1_LLM_MODEL = "Qwen3.5-9B"
$env:DIDE1_LLM_TIMEOUT = "300"
$env:DIDE1_LLM_RETRIES = "1"
```

## Piloto de 500 decisões únicas

Mais simples:

```powershell
.\scripts\run_500_windows_v42.ps1
```

Manual:

```powershell
Remove-Item .\runtime\piloto500_qwen_v42 -Recurse -Force -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m dide1.cli run `
    --input .\dados\entarda.xlsx `
    --start-index 0 `
    --unique-limit 500 `
    --teacher llama `
    --max-candidates 3 `
    --output .\runtime\piloto500_qwen_v42

Get-Content .\runtime\piloto500_qwen_v42\manifest.json
Get-Content .\runtime\piloto500_qwen_v42\errors.jsonl
Start-Process .\runtime\piloto500_qwen_v42\review.xlsx
```

## Revisão
Use `revisao_consolidada`. Cada linha representa uma decisão única e pode conter até 3 candidatos independentes. Aprove todos os recortes corretos; ajuste ou rejeite individualmente. Use `adicao_1..3` para recortes que o teacher perdeu. Só então marque `VALIDADO_COMPLETO`.

## GOLD

```powershell
.\.venv\Scripts\python.exe -m dide1.cli build-gold `
    --review .\runtime\piloto500_qwen_v42\review.xlsx `
    --output .\runtime\gold\gold_500.jsonl
```
