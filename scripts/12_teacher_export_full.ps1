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
  --limit 0 `
  --output runtime/private_annotations/teacher_review_full.xlsx `
  --checkpoint runtime/private_annotations/teacher_full_checkpoint.json
