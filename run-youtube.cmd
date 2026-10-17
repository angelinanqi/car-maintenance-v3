@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Missing venv. Complete the one-time setup in README.md first.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" "scripts\run.py" youtube %*
set "result=%errorlevel%"
echo.
echo YouTube ingestion finished with exit code %result%.
pause
exit /b %result%
