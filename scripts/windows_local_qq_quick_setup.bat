@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SERVER_BRIDGE_HOST=%~1"
set "LOCAL_NAPCAT_HOST=%~2"

if "%SERVER_BRIDGE_HOST%"=="" (
  set /p SERVER_BRIDGE_HOST=请输入服务器 Tailscale IP 或可达主机名: 
)

if "%SERVER_BRIDGE_HOST%"=="" (
  echo [ERROR] ServerBridgeHost 不能为空。
  pause
  exit /b 1
)

if "%LOCAL_NAPCAT_HOST%"=="" (
  set /p LOCAL_NAPCAT_HOST=可选：手动输入本机 Tailscale IPv4，直接回车则自动识别: 
)

echo.
echo [INFO] 正在生成 Windows 本地三开 QQ 配置...

if "%LOCAL_NAPCAT_HOST%"=="" (
  powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_multi.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%" -OpenOutput
) else (
  powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_multi.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%" -LocalNapCatHost "%LOCAL_NAPCAT_HOST%" -OpenOutput
)

set "EXITCODE=%ERRORLEVEL%"
echo.
if %EXITCODE% NEQ 0 (
  echo [ERROR] 生成失败，请先看上面的报错。
  pause
  exit /b %EXITCODE%
)

echo [OK] 已生成配置并打开输出目录。
echo [TIP] 把 3 份 onebot11.json 放进 3 个 NapCat 实例后，再运行 run-doctor.bat 自检。
pause
exit /b 0
