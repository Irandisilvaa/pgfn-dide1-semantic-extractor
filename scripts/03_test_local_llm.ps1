param([int]$Port = 8081)
$ErrorActionPreference = "Stop"

Write-Host "=== HEALTH ==="
Invoke-RestMethod "http://127.0.0.1:$Port/health" | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "=== MODELS ==="
Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "=== STRUCTURED JSON TEST ==="
$schema = @{
    type = "object"
    properties = @{
        status = @{ type = "string"; enum = @("OK") }
    }
    required = @("status")
    additionalProperties = $false
}
$body = @{
    messages = @(
        @{ role = "system"; content = "Responda apenas no formato solicitado." },
        @{ role = "user"; content = "Confirme funcionamento retornando status OK." }
    )
    temperature = 0
    max_tokens = 32
    response_format = @{
        type = "json_object"
        schema = $schema
    }
    chat_template_kwargs = @{ enable_thinking = $false }
} | ConvertTo-Json -Depth 20

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$content = $response.choices[0].message.content
Write-Host $content
if ($content -notmatch '"status"\s*:\s*"OK"') {
    throw "Qwen respondeu, mas o teste JSON estruturado não retornou status=OK."
}
Write-Host "QWEN_LOCAL_OK"
