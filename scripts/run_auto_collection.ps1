# 0. Automatic collection and follow-up options
param(
    [string]$Sources = "lod,kf_eschool",
    [switch]$IncludeAuthenticatedSources,
    [switch]$IncludeKoica,
    [int]$KoicaFromYear = ((Get-Date).Year - 2),
    [int]$KoicaToYear = (Get-Date).Year,
    [switch]$SkipScoring,
    [switch]$Strict,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AlgorithmRoot = Join-Path $ProjectRoot "data_algorithm"
$AlgorithmSource = Join-Path $AlgorithmRoot "src"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Collector = Join-Path $AlgorithmRoot "scripts\collect_public_sources.py"
$KoicaCollector = Join-Path $AlgorithmRoot "scripts\collect_koica.py"
$BackendInitializer = "backend.database.init_db"
$BackendSync = Join-Path $AlgorithmRoot "scripts\sync_backend.py"
$AlgorithmDatabase = Join-Path $AlgorithmRoot "data\radar_real.db"
$BackendDatabase = Join-Path $ProjectRoot "data\k_global_radar.db"
$OutputDirectory = Join-Path $AlgorithmRoot "outputs\automation"
$CollectionReport = Join-Path $OutputDirectory "latest_collection.json"
$AutomationReport = Join-Path $OutputDirectory "latest_run.json"
$LogDirectory = Join-Path $OutputDirectory "logs"
$LockPath = Join-Path $OutputDirectory "collection.lock"


# 1. Validate paths and requested sources
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}
if ($KoicaFromYear -gt $KoicaToYear) {
    throw "KoicaFromYear must be less than or equal to KoicaToYear."
}

$SupportedSources = @(
    "lod",
    "kf_eschool",
    "kf",
    "mofa",
    "kf_academic"
)
$RequestedSources = [System.Collections.Generic.List[string]]::new()
foreach ($Source in ($Sources -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    if ($Source -notin $SupportedSources) {
        throw "Unsupported source: $Source"
    }
    if (-not $RequestedSources.Contains($Source)) {
        $RequestedSources.Add($Source)
    }
}
if ($IncludeAuthenticatedSources) {
    foreach ($Source in @("kf", "mofa")) {
        if (-not $RequestedSources.Contains($Source)) {
            $RequestedSources.Add($Source)
        }
    }
}
if ($RequestedSources.Count -eq 0 -and -not $IncludeKoica) {
    throw "Select at least one source or enable IncludeKoica."
}

$Plan = [ordered]@{
    sources = @($RequestedSources)
    include_koica = [bool]$IncludeKoica
    koica_years = "$KoicaFromYear-$KoicaToYear"
    score_and_sync = -not [bool]$SkipScoring
    algorithm_database = $AlgorithmDatabase
    backend_database = $BackendDatabase
}
if ($DryRun) {
    $Plan | ConvertTo-Json -Depth 4
    exit 0
}


# 2. Prevent overlapping collection runs
New-Item -ItemType Directory -Force -Path $OutputDirectory, $LogDirectory | Out-Null
$LockStream = $null
$TranscriptStarted = $false
$StartedAt = (Get-Date).ToUniversalTime()
$RunStatus = "failed"
$FailureMessage = $null
$AnySourceCompleted = $false
$CompletedSources = [System.Collections.Generic.List[string]]::new()
$LogPath = Join-Path $LogDirectory ("collection-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

try {
    try {
        $LockStream = [System.IO.File]::Open(
            $LockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch [System.IO.IOException] {
        Write-Host "Another automatic collection run is already active." -ForegroundColor Yellow
        exit 0
    }

    Start-Transcript -Path $LogPath -Force | Out-Null
    $TranscriptStarted = $true
    Set-Location $ProjectRoot
    $env:PYTHONPATH = $AlgorithmSource

    # 3. Collect public sources and optional authenticated sources
    if ($RequestedSources.Count -gt 0) {
        $CollectionArguments = @(
            $Collector,
            "--db", $AlgorithmDatabase,
            "--report", $CollectionReport,
            "--sources"
        ) + @($RequestedSources)
        if ($Strict) {
            $CollectionArguments += "--strict"
        }
        & $VenvPython @CollectionArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Public-source collection failed with exit code $LASTEXITCODE."
        }
        $CollectionPayload = Get-Content -Raw -LiteralPath $CollectionReport | ConvertFrom-Json
        foreach ($Property in $CollectionPayload.sources.PSObject.Properties) {
            if ($Property.Value.status -eq "complete") {
                $AnySourceCompleted = $true
                $CompletedSources.Add($Property.Name)
            }
        }
    }

    # 4. Collect recent KOICA list data without the unstable detail API
    if ($IncludeKoica) {
        & $VenvPython $KoicaCollector `
            --db $AlgorithmDatabase `
            --from-year $KoicaFromYear `
            --to-year $KoicaToYear `
            --page-size 100 `
            --min-request-interval 5 `
            --list-only
        if ($LASTEXITCODE -ne 0) {
            throw "KOICA list collection failed with exit code $LASTEXITCODE."
        }
        $AnySourceCompleted = $true
        $CompletedSources.Add("KOICA")
    }

    if (-not $AnySourceCompleted) {
        throw "No requested data source completed."
    }

    # 5. Recalculate existing scores and synchronize the FastAPI database
    if (-not $SkipScoring) {
        $AsOf = Get-Date -Format "yyyy-MM-dd"
        & $VenvPython -m opportunity_radar `
            --db $AlgorithmDatabase `
            score `
            --as-of $AsOf
        if ($LASTEXITCODE -ne 0) {
            throw "Score calculation failed with exit code $LASTEXITCODE."
        }

        & $VenvPython -m $BackendInitializer --path $BackendDatabase
        if ($LASTEXITCODE -ne 0) {
            throw "Backend database initialization failed with exit code $LASTEXITCODE."
        }

        & $VenvPython $BackendSync `
            --algorithm-db $AlgorithmDatabase `
            --backend-db $BackendDatabase `
            --as-of $AsOf
        if ($LASTEXITCODE -ne 0) {
            throw "Backend synchronization failed with exit code $LASTEXITCODE."
        }
    }

    $RunStatus = "complete"
}
catch {
    $FailureMessage = $_.Exception.Message
    Write-Error $FailureMessage
}
finally {
    $FinishedAt = (Get-Date).ToUniversalTime()
    $RunReport = [ordered]@{
        status = $RunStatus
        started_at = $StartedAt.ToString("o")
        finished_at = $FinishedAt.ToString("o")
        duration_seconds = [Math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 2)
        requested_sources = @($RequestedSources)
        completed_sources = @($CompletedSources)
        included_koica = [bool]$IncludeKoica
        score_and_sync = -not [bool]$SkipScoring
        collection_report = $CollectionReport
        log = $LogPath
        error = $FailureMessage
    }
    $RunReport |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $AutomationReport -Encoding utf8

    if ($TranscriptStarted) {
        Stop-Transcript | Out-Null
    }
    if ($LockStream) {
        $LockStream.Dispose()
    }
}

if ($RunStatus -ne "complete") {
    exit 1
}

Write-Host "Automatic collection completed." -ForegroundColor Green
Write-Host "Report: $AutomationReport"
