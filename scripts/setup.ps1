# 0. 필요하면 사용할 Python 실행 파일을 외부 인자로 입력
param(
    [string]$PythonExecutable = ""
)

# 1. 오류 처리 방식과 프로젝트 설치 경로 설정
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

Write-Host "[1/3] Checking Python" -ForegroundColor Cyan

# 2. 기존 가상환경이 없으면 사용 가능한 Python을 찾아 새로 생성
if (-not (Test-Path -LiteralPath $VenvPython)) {
    # 2.1. 시스템 Python을 우선 확인하고 Codex 번들 Python을 대체 경로로 사용
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

    # 2.2. 사용할 Python이 없으면 설치 또는 실행 경로 입력 안내
    if (-not $PythonExecutable -or -not (Test-Path -LiteralPath $PythonExecutable)) {
        throw "Python was not found. Install Python 3.12+ or provide python.exe with -PythonExecutable."
    }

    Write-Host "[2/3] Creating .venv" -ForegroundColor Cyan
    & $PythonExecutable -m venv (Join-Path $ProjectRoot ".venv")
}
else {
    Write-Host "[2/3] Reusing existing .venv" -ForegroundColor DarkGray
}

# 3. requirements에 정의된 프로젝트 의존성 설치
Write-Host "[3/3] Installing packages" -ForegroundColor Cyan
& $VenvPython -m pip install --disable-pip-version-check --quiet -r $Requirements

Write-Host ""
# 4. 환경 구축 완료 후 주요 실행 명령 안내
Write-Host "Streamlit environment is ready." -ForegroundColor Green
Write-Host "Run: .\scripts\run.ps1"
Write-Host "API: .\scripts\run_api.ps1"
