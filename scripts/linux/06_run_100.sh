#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source .venv/bin/activate

time python -m src.benchmark.run_benchmark \
  --dataset data/benchmark_100.jsonl \
  --label qwen35_9b_pilot_100

python -m src.benchmark.render_report \
  runtime/summary_qwen35_9b_pilot_100.json
