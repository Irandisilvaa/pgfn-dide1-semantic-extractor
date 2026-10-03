$ErrorActionPreference = "Stop"
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 120 --limit 1000 --teacher llama --output runtime\lote_0121_1120
