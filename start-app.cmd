@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Missing venv. Complete the one-time setup in README.md first.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" "scripts\run.py" app %*
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
