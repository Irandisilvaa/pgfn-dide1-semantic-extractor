#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m src.benchmark.validate_dataset \
  --dataset data/benchmark_100.jsonl

echo "Setup concluído."
