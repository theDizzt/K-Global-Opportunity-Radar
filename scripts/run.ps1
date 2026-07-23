# 0. 오류 발생 시 즉시 중단하고 애플리케이션 실행 경로 설정
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$AppPath = Join-Path $ProjectRoot "app.py"

# 1. 프로젝트 가상환경 존재 여부 확인
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw ".venv was not found. Run .\scripts\setup.ps1 first."
}

# 2. 기존 API 프로세스 확인을 위한 실행 상태 준비
Set-Location $ProjectRoot
$ApiProcess = $null
$ApiWasStarted = $false

# 3. API가 없으면 새로 실행한 뒤 Streamlit 시작
try {
    # 3.1. 기존 API 상태 확인
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1 | Out-Null
    }
    catch {
        # 3.2. 데이터베이스 초기화 후 숨김 창에서 FastAPI 실행
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

        # 3.3. API 상태 확인을 반복하여 준비 완료까지 대기
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

    # 3.4. 준비된 API와 연결할 Streamlit 화면 실행
    & $VenvPython -m streamlit run $AppPath
}
finally {
    # 4. 이 스크립트가 실행한 API 프로세스만 종료
    if ($ApiWasStarted -and $ApiProcess -and -not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id
    }
}
