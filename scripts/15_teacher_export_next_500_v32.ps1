param(
    [string]$InputXlsx = "data_private\entrada_pgfn.xlsx",
    [string]$Sheet = "input",
    [int]$StartExcelRow = 0
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv\Scripts\python.exe"

if ($StartExcelRow -le 0) {
    $PreviousCheckpoint = "runtime/private_annotations/teacher_v32_next100_checkpoint.json"
    if (Test-Path $PreviousCheckpoint) {
        try {
            $cp = Get-Content $PreviousCheckpoint -Raw | ConvertFrom-Json
            $StartExcelRow = [int]$cp.next_excel_row
        } catch {
            $StartExcelRow = 202
        }
    } else {
        $StartExcelRow = 202
    }
}

Write-Host "=== DIDE1 v3.2 / LOTE DE 500 ==="
Write-Host "Inicio na linha Excel: $StartExcelRow"
Write-Host "Use somente depois de revisar o novo lote de 100."

& $PythonExe -m src.annotation.export_teacher_xlsx `
  --input-xlsx $InputXlsx `
  --sheet $Sheet `
  --start-excel-row $StartExcelRow `
  --limit 500 `
  --output runtime/private_annotations/teacher_review_v32_next500.xlsx `
  --checkpoint runtime/private_annotations/teacher_v32_next500_checkpoint.json
