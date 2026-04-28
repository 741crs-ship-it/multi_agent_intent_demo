@echo off
chcp 65001 >nul
echo ========== where python ==========
where python
echo.
echo ========== python -c print exe ==========
python -c "import sys; print(sys.executable)" 2>nul
if errorlevel 1 echo [FAIL] 这里的 python 无法执行 -c，说明 PATH 里的 python 不可靠
echo.
echo ========== Python312 直接路径 ==========
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" (
  "%PY%" -c "import sys; print(sys.executable)"
) else (
  echo [MISS] 未找到: %PY%
)
echo.
pause
