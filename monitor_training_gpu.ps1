param(
    [string]$Output = "outputs/missing_hole_v1/gpu_monitor.csv",
    [string]$StopFile = "outputs/missing_hole_v1/stop_gpu_monitor.flag",
    [int]$IntervalSeconds = 30
)

$outputPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Output))
$stopPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $StopFile))
$directory = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $directory -Force | Out-Null
if (Test-Path -LiteralPath $stopPath) {
    Remove-Item -LiteralPath $stopPath -Force
}
"timestamp,utilization_gpu_percent,memory_used_mib,memory_total_mib,temperature_c,power_w" | Set-Content -LiteralPath $outputPath -Encoding utf8

while (-not (Test-Path -LiteralPath $stopPath)) {
    $line = & nvidia-smi.exe --query-gpu=timestamp,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits
    if ($LASTEXITCODE -eq 0 -and $line) {
        Add-Content -LiteralPath $outputPath -Value $line -Encoding utf8
    }
    Start-Sleep -Seconds $IntervalSeconds
}
