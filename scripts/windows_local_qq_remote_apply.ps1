param(
    [string]$ServerSshTarget = "",
    [string]$OutputRoot = "",
    [string]$LocalProfilePath = "",
    [string]$RemoteRepoPath = "/root/brain-secretary",
    [string]$RemoteProfileRelativePath = "ops/windows-local-qq-profile.json",
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "找不到命令: $Name，请先安装或启用它。"
    }
    return $cmd
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $env:USERPROFILE "brain-secretary-local-qq"
}

if (-not $LocalProfilePath) {
    $LocalProfilePath = Join-Path $OutputRoot "server-bridge-profile.json"
}

if (-not (Test-Path -LiteralPath $LocalProfilePath)) {
    throw "本地 profile 不存在: $LocalProfilePath"
}

if (-not $ServerSshTarget) {
    $ServerSshTarget = Read-Host "请输入服务器 SSH 目标（例如 root@110.41.170.155）"
}

if (-not $ServerSshTarget) {
    throw "ServerSshTarget 不能为空。"
}

Require-Command ssh | Out-Null
Require-Command scp | Out-Null

$remoteProfilePath = "$RemoteRepoPath/$RemoteProfileRelativePath"
$scpTarget = "${ServerSshTarget}:$remoteProfilePath"

Write-Host "正在上传 profile -> $scpTarget"
& scp $LocalProfilePath $scpTarget
if ($LASTEXITCODE -ne 0) {
    throw "scp 上传失败，exit=$LASTEXITCODE"
}

$remoteCommands = @(
    ('cd "{0}"' -f $RemoteRepoPath),
    ('python3 scripts/qq_bot_multi.py import-profile --profile "{0}" --json' -f $RemoteProfileRelativePath)
)
if (-not $SkipRestart) {
    $remoteCommands += "python3 scripts/qq_bot_multi.py restart --json"
}
$remoteCommands += "python3 scripts/qq_bot_multi.py status --json"
$remoteScript = $remoteCommands -join ' && '

Write-Host "正在服务器应用配置..."
$result = & ssh $ServerSshTarget $remoteScript
if ($LASTEXITCODE -ne 0) {
    throw "服务器执行失败，exit=$LASTEXITCODE"
}

$resultPath = Join-Path $OutputRoot "server-apply-result.txt"
$result | Set-Content -Path $resultPath -Encoding UTF8
Write-Host "服务器应用完成，结果已写入: $resultPath"
Write-Host "远端 profile: $remoteProfilePath"
