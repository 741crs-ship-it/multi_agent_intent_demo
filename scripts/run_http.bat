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
echo [run_http] Python not found.
echo [run_http] Install Python 3.10+ or run:
echo [run_http]   python -m venv .venv
pause
exit /b 1

:RUN
set "HOST=%~1"
set "PORT=%~2"
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=8000"
echo [run_http] Python: %PY%
echo [run_http] URL: http://%HOST%:%PORT%
"%PY%" -u "%ROOT%\agent_project\http_server.py" --host "%HOST%" --port "%PORT%"
echo [run_http] exit code: %ERRORLEVEL%
pause
