$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
& ".\.venv\Scripts\python.exe" -m src.benchmark.run_benchmark `
  --dataset data/benchmark_10.jsonl `
  --label qwen35_9b_synth_10 `
  --show-text
