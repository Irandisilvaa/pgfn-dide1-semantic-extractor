param(
    [string]$BaseModel = "Qwen/Qwen3-4B",
    [string]$RunName = "dide1-slm-v1"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv-train\Scripts\python.exe"
& $PythonExe -m src.training.train_qlora --base-model $BaseModel --run-name $RunName --resume
