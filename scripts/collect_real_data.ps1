# 0. 오류 발생 시 즉시 중단하고 프로젝트 실행 경로 설정
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AlgorithmRoot = Join-Path $ProjectRoot "data_algorithm"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Collector = Join-Path $AlgorithmRoot "scripts\collect_public_sources.py"

# 1. 프로젝트 가상환경 존재 여부 확인
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}

# 2. 데이터·알고리즘 패키지를 Python 모듈 검색 경로에 추가
$env:PYTHONPATH = Join-Path $AlgorithmRoot "src"

# 3. 전달받은 옵션으로 실제 공공데이터 통합 수집기 실행
Set-Location $ProjectRoot
& $VenvPython $Collector @args
exit $LASTEXITCODE
