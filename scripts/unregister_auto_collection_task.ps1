# 0. Scheduled task name to remove
param(
    [string]$TaskName = "K-Global Opportunity Radar Data Collection"
)

$ErrorActionPreference = "Stop"


# 1. Remove the task when it exists
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "Scheduled task was not found: $TaskName" -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Scheduled task removed: $TaskName" -ForegroundColor Green
