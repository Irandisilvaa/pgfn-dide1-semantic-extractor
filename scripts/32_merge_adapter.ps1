param(
    [string]$BaseModel = "Qwen/Qwen3-4B",
    [string]$RunName = "dide1-slm-v1"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv-train\Scripts\python.exe"
$Adapter = "artifacts/models/$RunName/adapter_final"
$Output = "artifacts/models/$RunName/merged_model"
& $PythonExe -m src.training.merge_adapter --base-model $BaseModel --adapter $Adapter --output $Output
