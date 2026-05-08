@echo off
chcp 65001 >nul
set "ROOT=%~dp0.."
echo ========== project venv python ==========
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -c "import sys; print(sys.version); print(sys.executable)"
) else (
  echo [MISS] project venv not found: %ROOT%\.venv\Scripts\python.exe
)
echo.
echo ========== fixed local python ==========
if exist "C:\Dev\Python312\python.exe" (
  "C:\Dev\Python312\python.exe" -c "import sys; print(sys.version); print(sys.executable)"
) else (
  echo [MISS] fixed local python not found: C:\Dev\Python312\python.exe
)
echo.
echo ========== where python ==========
where python
echo.
echo ========== python -c print exe ==========
python -c "import sys; print(sys.version); print(sys.executable)" 2>nul
if errorlevel 1 echo [FAIL] PATH python is not available or not reliable
echo.
pause
