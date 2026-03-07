@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PROJECT=%~1"
set "INTERVAL=%~2"

if "%PROJECT%"=="" (
  set /p PROJECT=请输入 project 名称（对应 ops/project-sync.json 里的 name）: 
)

if "%PROJECT%"=="" (
  echo [ERROR] Project 不能为空。
  pause
  exit /b 1
)

if "%INTERVAL%"=="" set "INTERVAL=120"

echo [INFO] 即将开始自动同步 %PROJECT%，轮询间隔 %INTERVAL% 秒。
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_project_autosync.ps1" -Project "%PROJECT%" -IntervalSeconds %INTERVAL%
set "EXITCODE=%ERRORLEVEL%"
echo.
if %EXITCODE% NEQ 0 echo [WARN] 自动同步退出，返回码 %EXITCODE%。
pause
exit /b %EXITCODE%
