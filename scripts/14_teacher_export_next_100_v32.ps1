param(
    [string]$InputXlsx = "data_private\entrada_pgfn.xlsx",
    [string]$Sheet = "input",
    [int]$StartExcelRow = 0
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PythonExe = ".\.venv\Scripts\python.exe"

if ($StartExcelRow -le 0) {
    $PreviousCheckpoint = "runtime/private_annotations/teacher_100_checkpoint.json"
    if (Test-Path $PreviousCheckpoint) {
        try {
            $cp = Get-Content $PreviousCheckpoint -Raw | ConvertFrom-Json
            $StartExcelRow = [int]$cp.next_excel_row
        } catch {
            $StartExcelRow = 102
        }
    } else {
        $StartExcelRow = 102
    }
}

Write-Host "=== DIDE1 v3.2 / NOVO LOTE DE 100 ==="
Write-Host "Inicio na linha Excel: $StartExcelRow"
Write-Host "A linha inicial foi obtida do checkpoint anterior quando disponível."

& $PythonExe -m src.annotation.export_teacher_xlsx `
  --input-xlsx $InputXlsx `
  --sheet $Sheet `
  --start-excel-row $StartExcelRow `
  --limit 100 `
  --output runtime/private_annotations/teacher_review_v32_next100.xlsx `
  --checkpoint runtime/private_annotations/teacher_v32_next100_checkpoint.json
