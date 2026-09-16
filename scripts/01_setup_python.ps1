$ErrorActionPreference = "Stop"

$py = Get-Command py -ErrorAction SilentlyContinue

if ($py) {
    try {
        & py -3.12 -m venv .venv
    } catch {
        & py -3 -m venv .venv
    }
} else {
    python -m venv .venv
}

$pythonExe = Join-Path $PWD ".venv\Scripts\python.exe"

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Ambiente Python criado."
Write-Host "Ative com:"
Write-Host ".\.venv\Scripts\Activate.ps1"
