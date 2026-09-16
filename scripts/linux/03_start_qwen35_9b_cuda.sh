#!/usr/bin/env bash
set -euo pipefail

MODEL="bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M"
PORT="${PORT:-8081}"

if command -v llama >/dev/null 2>&1; then
  CMD=(llama serve)
elif command -v llama-server >/dev/null 2>&1; then
  CMD=(llama-server)
else
  echo "llama.cpp não encontrado."
  exit 1
fi

EXTRA=()
if "${CMD[@]}" --help 2>&1 | grep -q -- "--reasoning"; then
  EXTRA+=(--reasoning off)
fi

exec "${CMD[@]}" \
  -hf "$MODEL" \
  -c 8192 \
  -t 6 \
  -ngl 999 \
  -np 1 \
  --host 127.0.0.1 \
  --port "$PORT" \
  --no-webui \
  "${EXTRA[@]}"
