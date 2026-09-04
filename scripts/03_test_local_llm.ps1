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

$Port = if ($env:LLAMA_PORT) { [int]$env:LLAMA_PORT } else { 8081 }

Write-Host "=== HEALTH ==="
Invoke-RestMethod "http://127.0.0.1:$Port/health" |
    ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "=== MODELS ==="
Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" |
    ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "=== CHAT ==="

$body = @{
    messages = @(
        @{
            role = "user"
            content = "Responda somente com OK."
        }
    )
    temperature = 0
    max_tokens = 10
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

Write-Host $response.choices[0].message.content
