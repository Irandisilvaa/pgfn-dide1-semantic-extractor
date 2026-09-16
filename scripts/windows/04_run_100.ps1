$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../..")

& ".\.venv\Scripts\python.exe" -m src.benchmark.run_benchmark `
  --dataset data/benchmark_100.jsonl `
  --label qwen35_9b_pilot_100

& ".\.venv\Scripts\python.exe" -m src.benchmark.render_report `
  runtime/summary_qwen35_9b_pilot_100.json
