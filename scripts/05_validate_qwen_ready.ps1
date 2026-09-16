$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
Write-Host "=== TESTES PYTHON ==="
& ".\.venv\Scripts\python.exe" -m pytest -q
Write-Host ""
Write-Host "=== LLM ==="
& ".\scripts\03_test_local_llm.ps1"
Write-Host ""
Write-Host "=== REDE ==="
& ".\scripts\04_check_llama_network.ps1"
Write-Host ""
Write-Host "=== GPU ==="
nvidia-smi
