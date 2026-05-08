@echo off
chcp 65001 >nul
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
if exist "%PY%" goto RUN

set "PY=C:\Dev\Python312\python.exe"
if exist "%PY%" goto RUN

where python >nul 2>nul
if errorlevel 1 goto MISS
set "PY=python"
goto RUN

:MISS
echo [run_test] Python not found.
echo [run_test] Install Python 3.10+ or run:
echo [run_test]   python -m venv .venv
echo [run_test]   .venv\Scripts\python.exe -m pip install --upgrade pip
pause
exit /b 1

:RUN
echo [run_test] Python: %PY%
"%PY%" -u "%ROOT%\agent_project\test_cases.py" %*
echo [run_test] exit code: %ERRORLEVEL%
pause
