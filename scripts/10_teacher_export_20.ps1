param(
    [string]$InputXlsx = "data_private\entrada_pgfn.xlsx",
    [string]$Sheet = "input"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv\Scripts\python.exe"
& $PythonExe -m src.annotation.export_teacher_xlsx `
  --input-xlsx $InputXlsx `
  --sheet $Sheet `
  --limit 20 `
  --output runtime/private_annotations/teacher_review_20.xlsx `
  --checkpoint runtime/private_annotations/teacher_20_checkpoint.json
