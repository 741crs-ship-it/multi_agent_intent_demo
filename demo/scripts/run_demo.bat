@echo off
chcp 65001 >nul
echo [run_demo] 当前 PATH 里的 python（若排第一的不是 Python312，直接敲 python 可能无声退出）：
where python 2>nul
echo.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" goto RUN
echo [run_demo] 找不到默认 Python312：%PY%
echo [run_demo] 请用记事本打开本 bat，把 PY= 改成你的 python.exe 完整路径
pause
exit /b 1

:RUN
echo [run_demo] 使用解释器：%PY%
"%PY%" -u "%~dp0..\demo_agentuniverse.py" %*
echo [run_demo] 退出码：%ERRORLEVEL%
pause
