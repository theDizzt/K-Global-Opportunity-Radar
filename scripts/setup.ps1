param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

Write-Host "[1/3] Checking Python" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $VenvPython)) {
    if (-not $PythonExecutable) {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue

        if ($PythonCommand) {
            $PythonExecutable = $PythonCommand.Source
        }
        else {
            $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

            if (Test-Path -LiteralPath $BundledPython) {
                $PythonExecutable = $BundledPython
            }
        }
    }

    if (-not $PythonExecutable -or -not (Test-Path -LiteralPath $PythonExecutable)) {
        throw "Python was not found. Install Python 3.12+ or provide python.exe with -PythonExecutable."
    }

    Write-Host "[2/3] Creating .venv" -ForegroundColor Cyan
    & $PythonExecutable -m venv (Join-Path $ProjectRoot ".venv")
}
else {
    Write-Host "[2/3] Reusing existing .venv" -ForegroundColor DarkGray
}

Write-Host "[3/3] Installing packages" -ForegroundColor Cyan
& $VenvPython -m pip install --disable-pip-version-check --quiet -r $Requirements

Write-Host ""
Write-Host "Streamlit environment is ready." -ForegroundColor Green
Write-Host "Run: .\scripts\run.ps1"
