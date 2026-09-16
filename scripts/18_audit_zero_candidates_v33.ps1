param(
    [string]$InputXlsx = "data_private\entrada_pgfn.xlsx",
    [string]$ReviewXlsx = "runtime\private_annotations\teacher_review_v32_next100.xlsx",
    [string]$Sheet = "input",
    [string]$OutputXlsx = "runtime\private_annotations\zero_candidates_v32_audit.xlsx"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv\Scripts\python.exe"

& $PythonExe -m src.annotation.export_zero_candidate_audit `
  --input-xlsx $InputXlsx `
  --review-xlsx $ReviewXlsx `
  --sheet $Sheet `
  --output $OutputXlsx
