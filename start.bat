@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ========================================
echo   dlyt - starting backend + frontend
echo ========================================
echo.

REM ---- Backend (new window) ----
where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
  )
  set "PY=python"
) else (
  set "PY=py -3"
)

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js is not installed or not in PATH.
  pause
  exit /b 1
)

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo [backend] Creating virtualenv...
  pushd "%ROOT%backend"
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create venv.
    popd
    pause
    exit /b 1
  )
  popd
)

if not exist "%ROOT%backend\.env" (
  copy "%ROOT%backend\.env.example" "%ROOT%backend\.env" >nul
)

if not exist "%ROOT%frontend\node_modules\" (
  echo [frontend] Installing npm dependencies...
  pushd "%ROOT%frontend"
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
  )
  popd
)

if not exist "%ROOT%frontend\.env.local" (
  echo NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000> "%ROOT%frontend\.env.local"
  echo [frontend] Created .env.local pointing at local API.
)

echo [backend] Opening API window on http://127.0.0.1:8000
start "dlyt-backend" cmd /k "cd /d "%ROOT%backend" && call .venv\Scripts\activate.bat && python -m pip install -q -r requirements.txt && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --proxy-headers"

echo [frontend] Waiting for API to boot...
timeout /t 3 /nobreak >nul

echo [frontend] Starting UI on http://localhost:3000
echo Press Ctrl+C here to stop the frontend. Close the "dlyt-backend" window to stop the API.
echo.
pushd "%ROOT%frontend"
call npm run dev
popd

endlocal
