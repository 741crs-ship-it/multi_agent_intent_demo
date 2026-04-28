@echo off
chcp 65001 >nul
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" goto RUN
echo [run_test] 找不到默认 Python312：%PY%
echo [run_test] 请修改 run_test.bat 里的 PY 路径后重试
pause
exit /b 1

:RUN
echo [run_test] 使用解释器：%PY%
"%PY%" -u "%~dp0..\test_demo.py" %*
echo [run_test] 退出码：%ERRORLEVEL%
pause
