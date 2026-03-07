@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SERVER_BRIDGE_HOST=%~1"
set "LOCAL_NAPCAT_HOST=%~2"

if "%SERVER_BRIDGE_HOST%"=="" (
  set /p SERVER_BRIDGE_HOST=可选：输入服务器 Tailscale IP，用于检查 8011/8012/8013 端口；直接回车跳过: 
)

if "%LOCAL_NAPCAT_HOST%"=="" (
  set /p LOCAL_NAPCAT_HOST=可选：手动输入本机 Tailscale IPv4，直接回车则自动识别: 
)

echo.
echo [INFO] 正在执行 Windows 本地 QQ 自检...

if "%SERVER_BRIDGE_HOST%"=="" (
  if "%LOCAL_NAPCAT_HOST%"=="" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_doctor.ps1"
  ) else (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_doctor.ps1" -LocalNapCatHost "%LOCAL_NAPCAT_HOST%"
  )
) else (
  if "%LOCAL_NAPCAT_HOST%"=="" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_doctor.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%"
  ) else (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_doctor.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%" -LocalNapCatHost "%LOCAL_NAPCAT_HOST%"
  )
)

set "EXITCODE=%ERRORLEVEL%"
echo.
if %EXITCODE% NEQ 0 (
  echo [WARN] 自检里有告警，先看上面的输出。
) else (
  echo [OK] 自检通过。
)
pause
exit /b %EXITCODE%
