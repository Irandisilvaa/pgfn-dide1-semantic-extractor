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

$ErrorActionPreference = "Stop"
Import-DotEnv

$PythonExe = Join-Path $PWD ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Ambiente .venv não encontrado."
}

New-Item -ItemType Directory -Force -Path runtime | Out-Null

$BaseUrl = if ($env:LOCAL_LLM_BASE_URL) {
    $env:LOCAL_LLM_BASE_URL
} else {
    "http://127.0.0.1:8081/v1"
}

& $PythonExe -m src.phase3.semantic_dry_run `
    --mode sequential `
    --sample-size 0 `
    --page-size 50 `
    --top-k 3 `
    --max-unit-chars 1000 `
    --max-chunk-chars 3000 `
    --max-candidates-per-chunk 4 `
    --max-global-candidates 30 `
    --validator-batch-size 6 `
    --temperature 0 `
    --base-url $BaseUrl `
    --summary "runtime/summary_full.json" `
    --preview-jsonl "runtime/preview_full.jsonl" `
    --checkpoint "runtime/checkpoint_full.json"
