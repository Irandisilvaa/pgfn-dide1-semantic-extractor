Write-Host "=== GPU ==="
nvidia-smi
Write-Host "`n=== CPU ==="
Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors
Write-Host "`n=== RAM ==="
Get-CimInstance Win32_ComputerSystem | Select @{N='RAM_GB';E={[math]::Round($_.TotalPhysicalMemory/1GB,1)}}
Write-Host "`n=== Python ==="
python --version
