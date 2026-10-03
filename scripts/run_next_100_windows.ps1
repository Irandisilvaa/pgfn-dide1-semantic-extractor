$ErrorActionPreference = "Stop"
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 20 --limit 100 --teacher llama --output runtime\lote_0021_0120
