@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SERVER_BRIDGE_HOST=%~1"
set "SERVER_SSH_TARGET=%~2"
set "LOCAL_NAPCAT_HOST=%~3"

if "%SERVER_BRIDGE_HOST%"=="" (
  set /p SERVER_BRIDGE_HOST=请输入服务器 Bridge Host（Tailscale IP 或可达主机名）: 
)

if "%SERVER_BRIDGE_HOST%"=="" (
  echo [ERROR] ServerBridgeHost 不能为空。
  pause
  exit /b 1
)

if "%SERVER_SSH_TARGET%"=="" (
  set /p SERVER_SSH_TARGET=可选：输入服务器 SSH 目标（如 root@110.41.170.155），留空则只生成+自检: 
)

if "%LOCAL_NAPCAT_HOST%"=="" (
  set /p LOCAL_NAPCAT_HOST=可选：输入本机 Tailscale IPv4，留空则自动识别: 
)

echo.
echo [INFO] 正在执行一键连接流程（生成配置 -> 自检 -> 可选远程应用）...

if "%LOCAL_NAPCAT_HOST%"=="" (
  powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_connect_remote.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%" -ServerSshTarget "%SERVER_SSH_TARGET%"
) else (
  powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%windows_local_qq_connect_remote.ps1" -ServerBridgeHost "%SERVER_BRIDGE_HOST%" -ServerSshTarget "%SERVER_SSH_TARGET%" -LocalNapCatHost "%LOCAL_NAPCAT_HOST%"
)

set "EXITCODE=%ERRORLEVEL%"
echo.
if %EXITCODE% NEQ 0 (
  echo [ERROR] 一键流程失败，请先看上面的报错信息。
) else (
  echo [OK] 一键流程完成。
)
pause
exit /b %EXITCODE%
