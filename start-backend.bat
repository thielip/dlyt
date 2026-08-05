@echo off
REM Backend-only helper. Prefer start.bat to launch the full stack.
echo [info] Prefer start.bat for one-click full stack.
echo [info] Starting backend only...
cd /d "%~dp0backend"

where py >nul 2>&1
if errorlevel 1 (
  set PY=python
) else (
  set PY=py -3
)

if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
)
call ".venv\Scripts\activate.bat"
pip install -q -r requirements.txt
if not exist ".env" copy ".env.example" ".env" >nul
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --proxy-headers
