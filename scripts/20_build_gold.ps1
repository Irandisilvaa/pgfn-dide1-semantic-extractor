param([Parameter(Mandatory=$true)][string]$ReviewXlsx)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv\Scripts\python.exe"
& $PythonExe -m src.annotation.build_gold --review-xlsx $ReviewXlsx --output-dir runtime/private_gold
