param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$Config = "ops/project-sync.json",
    [int]$IntervalSeconds = 120,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    foreach ($name in @("py", "python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            if ($name -eq "py") {
                return @($cmd.Source, "-3")
            }
            return @($cmd.Source)
        }
    }
    throw "未找到 Python 命令，请先安装 py / python / python3。"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptPath = Join-Path $PSScriptRoot "project_sync.py"
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $RepoRoot $Config }
$PythonCmd = Resolve-PythonCommand

if ($IntervalSeconds -lt 15) {
    throw "IntervalSeconds 不建议小于 15 秒。"
}

Write-Host "Windows 项目自动同步已启动"
Write-Host "Project: $Project"
Write-Host "Config: $ConfigPath"
Write-Host "IntervalSeconds: $IntervalSeconds"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Mode: update-work"
Write-Host ""

while ($true) {
    $args = @($ScriptPath, "update-work", "--config", $ConfigPath, "--project", $Project)

    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] checking $Project ..."
    if ($PythonCmd.Count -gt 1) {
        $extraPythonArgs = @($PythonCmd[1..($PythonCmd.Count - 1)])
        & $PythonCmd[0] @extraPythonArgs @args
    }
    else {
        & $PythonCmd[0] @args
    }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Warning "project_sync.py 返回非 0：$exitCode。可能是本地有未提交改动，或当前分支不对。"
    }

    if ($Once) {
        exit $exitCode
    }

    Start-Sleep -Seconds $IntervalSeconds
}
