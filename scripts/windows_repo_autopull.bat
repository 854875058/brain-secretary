@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "INTERVAL=%~1"

if "%INTERVAL%"=="" set "INTERVAL=300"

echo [INFO] 即将开始自动拉取当前仓库，轮询间隔 %INTERVAL% 秒。
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_repo_autopull.ps1" -IntervalSeconds %INTERVAL%
set "EXITCODE=%ERRORLEVEL%"
echo.
if %EXITCODE% NEQ 0 echo [WARN] 自动拉取退出，返回码 %EXITCODE%。
pause
exit /b %EXITCODE%
