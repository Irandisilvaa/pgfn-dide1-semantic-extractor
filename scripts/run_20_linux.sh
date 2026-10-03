#!/usr/bin/env bash
set -euo pipefail
# Para PC pessoal, use somente amostra sanitizada/autorizada.
python -m dide1.cli run --input dados/amostra_20.xlsx --limit 20 --start-index 0 --teacher rules --output runtime/piloto20_local
