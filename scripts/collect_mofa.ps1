# 0. 오류 발생 시 즉시 중단하고 프로젝트·Python 경로 설정
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# 1. 프로젝트 가상환경 존재 여부 확인
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}

# 2. 전달받은 국가·데이터셋·건수 옵션으로 외교부 수집기 실행
Set-Location $ProjectRoot
& $VenvPython -m backend.collectors.run @args
