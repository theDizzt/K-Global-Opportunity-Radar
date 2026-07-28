# 0. Windows Task Scheduler registration options
param(
    [string]$TaskName = "K-Global Opportunity Radar Data Collection",
    [ValidateSet("Daily", "Weekly")]
    [string]$Frequency = "Daily",
    [string]$At = "03:00",
    [ValidateSet(
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday"
    )]
    [string]$DayOfWeek = "Sunday",
    [switch]$IncludeAuthenticatedSources,
    [switch]$IncludeKoica
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run_auto_collection.ps1"


# 1. Validate schedule time and runner path
if (-not (Test-Path -LiteralPath $Runner)) {
    throw "Automatic collection runner was not found: $Runner"
}
try {
    $TriggerTime = [datetime]::ParseExact(
        $At,
        "HH:mm",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "At must use the 24-hour HH:mm format, for example 03:00."
}


# 2. Build the scheduled action and trigger
$RunnerArguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $Runner)
)
if ($IncludeAuthenticatedSources) {
    $RunnerArguments += "-IncludeAuthenticatedSources"
}
if ($IncludeKoica) {
    $RunnerArguments += "-IncludeKoica"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($RunnerArguments -join " ") `
    -WorkingDirectory $ProjectRoot

if ($Frequency -eq "Weekly") {
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $TriggerTime
}
else {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
}

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal `
    -UserId $CurrentUser `
    -LogonType Interactive `
    -RunLevel Limited


# 3. Register the task for the current user
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Collect public cooperation data, recalculate scores, and sync the FastAPI database." `
    -Force | Out-Null

Write-Host "Scheduled task registered." -ForegroundColor Green
Write-Host "Task: $TaskName"
Write-Host "Schedule: $Frequency $At"
Write-Host "Runner: $Runner"
