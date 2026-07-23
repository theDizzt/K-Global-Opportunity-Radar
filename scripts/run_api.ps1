# 0. 오류 발생 시 즉시 중단하고 실행 경로 설정
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# 1. 프로젝트 가상환경 존재 여부 확인
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}

# 2. SQLite 초기화 후 FastAPI 개발 서버 실행
Set-Location $ProjectRoot
& $VenvPython -m backend.database.init_db
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $VenvPython -m uvicorn backend.main:app --reload --port 8000
