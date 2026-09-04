function Import-DotEnv {
    param([string]$Path = ".env")

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()

        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (
            $value.Length -ge 2 -and
            (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            )
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

param(
    [Parameter(Mandatory=$true)]
    [int]$N
)

$ErrorActionPreference = "Stop"
Import-DotEnv

if ($N -lt 1) {
    throw "N deve ser >= 1."
}

if ($N -le 20) {
    $Blocks = $N
} else {
    $Blocks = [math]::Ceiling($N / 50.0)

    if ($Blocks -lt 20) {
        $Blocks = 20
    }
}

if ($Blocks -gt $N) {
    $Blocks = $N
}

$PythonExe = Join-Path $PWD ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Ambiente .venv não encontrado. Rode .\scripts\01_setup_python.ps1"
}

New-Item -ItemType Directory -Force -Path runtime | Out-Null

$BaseUrl = if ($env:LOCAL_LLM_BASE_URL) {
    $env:LOCAL_LLM_BASE_URL
} else {
    "http://127.0.0.1:8081/v1"
}

& $PythonExe -m src.phase3.semantic_dry_run `
    --mode distributed `
    --sample-size $N `
    --blocks $Blocks `
    --top-k 3 `
    --max-unit-chars 1000 `
    --max-chunk-chars 3000 `
    --max-candidates-per-chunk 4 `
    --max-global-candidates 30 `
    --validator-batch-size 6 `
    --temperature 0 `
    --base-url $BaseUrl `
    --show-text `
    --summary "runtime/summary_$N.json" `
    --preview-jsonl "runtime/preview_$N.jsonl"
