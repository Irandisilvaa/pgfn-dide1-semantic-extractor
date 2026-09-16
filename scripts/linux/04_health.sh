#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://127.0.0.1:8081/health
echo
curl -fsS http://127.0.0.1:8081/v1/models
echo
