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

Write-Host "=== WINDOWS ==="
Get-ComputerInfo |
    Select-Object WindowsProductName, WindowsVersion, OsArchitecture |
    Format-List

Write-Host ""
Write-Host "=== CPU ==="
Get-CimInstance Win32_Processor |
    Select-Object Name, NumberOfCores, NumberOfLogicalProcessors |
    Format-Table -AutoSize

Write-Host ""
Write-Host "=== RAM ==="
Get-CimInstance Win32_OperatingSystem |
    Select-Object `
        @{Name="RAM_Total_GB";Expression={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}}, `
        @{Name="RAM_Livre_GB";Expression={[math]::Round($_.FreePhysicalMemory/1MB,2)}} |
    Format-Table -AutoSize

Write-Host ""
Write-Host "=== GPU ==="
Get-CimInstance Win32_VideoController |
    Select-Object Name, DriverVersion, AdapterRAM |
    Format-Table -AutoSize

Write-Host ""
Write-Host "=== NVIDIA-SMI ==="
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidia) {
    & nvidia-smi
} else {
    Write-Host "nvidia-smi não encontrado."
}

Write-Host ""
Write-Host "=== PYTHON ==="
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -0p
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & python --version
    } else {
        Write-Host "Python não encontrado."
    }
}
