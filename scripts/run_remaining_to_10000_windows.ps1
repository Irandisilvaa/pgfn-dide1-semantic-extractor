$ErrorActionPreference = "Stop"
# 20 + 100 + 1000 + 8880 = 10.000 decisões avaliadas em lotes progressivos.
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 1120 --limit 8880 --teacher llama --output runtime\lote_1121_10000
