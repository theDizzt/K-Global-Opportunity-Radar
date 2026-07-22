$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$AppPath = Join-Path $ProjectRoot "app.py"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}

Set-Location $ProjectRoot
$ApiProcess = $null
$ApiWasStarted = $false

try {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1 | Out-Null
    }
    catch {
        & $VenvPython -m backend.database.init_db
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        $ApiProcess = Start-Process `
            -FilePath $VenvPython `
            -ArgumentList "-m", "uvicorn", "backend.main:app", "--port", "8000" `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden `
            -PassThru
        $ApiWasStarted = $true

        $ApiReady = $false
        for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1 | Out-Null
                $ApiReady = $true
                break
            }
            catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $ApiReady) {
            throw "Backend API did not become ready on port 8000."
        }
    }

    & $VenvPython -m streamlit run $AppPath
}
finally {
    if ($ApiWasStarted -and $ApiProcess -and -not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id
    }
}
