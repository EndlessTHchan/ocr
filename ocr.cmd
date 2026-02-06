@echo off
setlocal
set ROOT=%~dp0
set PY=%ROOT%\.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Missing venv python at %PY%
  echo Create it with one of:
  echo   py -3.10 -m venv .venv
  echo   python -m venv .venv
  exit /b 1
)
"%PY%" -m ocr_tool.cli %*
endlocal
