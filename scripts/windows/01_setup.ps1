$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../..")

python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

& ".\.venv\Scripts\python.exe" -m src.benchmark.validate_dataset `
  --dataset data/benchmark_100.jsonl

Write-Host "Setup concluído."
