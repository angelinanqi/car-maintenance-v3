@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ocr\Scripts\python.exe" (
  echo Create .venv-ocr and install requirements-ocr.txt first. See README.md.
  exit /b 1
)
".venv-ocr\Scripts\python.exe" scripts\run.py ocr %*
exit /b %errorlevel%
