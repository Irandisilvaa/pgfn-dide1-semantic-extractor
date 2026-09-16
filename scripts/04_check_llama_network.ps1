$ErrorActionPreference = "Stop"

$procs = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue

if (-not $procs) {
    Write-Host "llama-server não está em execução."
    exit 1
}

foreach ($proc in $procs) {
    Write-Host "PID:" $proc.Id

    Get-NetTCPConnection `
        -OwningProcess $proc.Id `
        -ErrorAction SilentlyContinue |
        Select-Object State, LocalAddress, LocalPort, RemoteAddress, RemotePort |
        Format-Table -AutoSize
}

Write-Host ""
Write-Host "Esperado: LISTEN em 127.0.0.1, não em 0.0.0.0."
