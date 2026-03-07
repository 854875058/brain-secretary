param(
    [string]$ServerBridgeHost = "",
    [string]$LocalNapCatHost = "",
    [string]$OutputRoot = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Get-TailscaleIPv4 {
    try {
        $cmd = Get-Command tailscale -ErrorAction Stop
        $ips = & $cmd.Source ip -4 2>$null
        foreach ($item in $ips) {
            $text = [string]$item
            if ($text -match '^\d+\.\d+\.\d+\.\d+$') {
                return $text
            }
        }
    } catch {
    }
    return ""
}

function Test-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutMs = 2000) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Add-Check([string]$Name, [bool]$Ok, [string]$Detail) {
    $script:Checks += [pscustomobject]@{
        name = $Name
        ok = $Ok
        detail = $Detail
    }
}

$Checks = @()

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $env:USERPROFILE "brain-secretary-local-qq"
}

if (-not $LocalNapCatHost) {
    $LocalNapCatHost = Get-TailscaleIPv4
}

Add-Check -Name "output_root" -Ok (Test-Path -LiteralPath $OutputRoot) -Detail "输出目录: $OutputRoot"
Add-Check -Name "tailscale_ip" -Ok (-not [string]::IsNullOrWhiteSpace($LocalNapCatHost)) -Detail $(if ($LocalNapCatHost) { "本机 Tailscale IPv4: $LocalNapCatHost" } else { "未检测到本机 Tailscale IPv4" })

$requiredFiles = @(
    "instances\\brain\\onebot11.json",
    "instances\\tech\\onebot11.json",
    "instances\\review\\onebot11.json",
    "server-bridge-profile.json",
    "README.local.md",
    "run-doctor.bat",
    "open-output.bat"
)

foreach ($relative in $requiredFiles) {
    $fullPath = Join-Path $OutputRoot $relative
    $exists = Test-Path -LiteralPath $fullPath
    Add-Check -Name "file:$relative" -Ok $exists -Detail $(if ($exists) { "存在: $fullPath" } else { "缺失: $fullPath" })
}

$profilePath = Join-Path $OutputRoot "server-bridge-profile.json"
if (Test-Path -LiteralPath $profilePath) {
    try {
        $profile = Get-Content -LiteralPath $profilePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $profileHost = [string]$profile.napcat_host
        $match = (-not $LocalNapCatHost) -or ($profileHost -eq $LocalNapCatHost)
        Add-Check -Name "profile:napcat_host" -Ok $match -Detail "profile.napcat_host=$profileHost"
    } catch {
        Add-Check -Name "profile:parse" -Ok $false -Detail "解析 server-bridge-profile.json 失败: $($_.Exception.Message)"
    }
}

foreach ($port in @(3001, 3002, 3003)) {
    $ok = Test-TcpPort -HostName "127.0.0.1" -Port $port
    Add-Check -Name "local_port:$port" -Ok $ok -Detail $(if ($ok) { "127.0.0.1:$port 可连通" } else { "127.0.0.1:$port 未监听，先确认对应 NapCat 实例是否启动" })
}

if ($ServerBridgeHost) {
    foreach ($port in @(8011, 8012, 8013)) {
        $ok = Test-TcpPort -HostName $ServerBridgeHost -Port $port
        Add-Check -Name "server_bridge:$port" -Ok $ok -Detail $(if ($ok) { "$ServerBridgeHost:$port 可连通" } else { "$ServerBridgeHost:$port 不通，先检查服务器桥接是否已 import-profile 并 restart" })
    }
} else {
    Add-Check -Name "server_bridge_host" -Ok $true -Detail "未提供 ServerBridgeHost，已跳过服务器 8011/8012/8013 连通性检查"
}

$failed = @($Checks | Where-Object { -not $_.ok }).Count
$summary = [ordered]@{
    output_root = $OutputRoot
    local_napcat_host = $LocalNapCatHost
    server_bridge_host = $ServerBridgeHost
    total = $Checks.Count
    failed = $failed
    passed = $Checks.Count - $failed
    checks = $Checks
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 10
    if ($failed -gt 0) {
        exit 1
    }
    exit 0
}

Write-Host "Windows 本地 QQ / NapCat 自检"
Write-Host "OutputRoot: $OutputRoot"
if ($LocalNapCatHost) {
    Write-Host "LocalNapCatHost: $LocalNapCatHost"
}
if ($ServerBridgeHost) {
    Write-Host "ServerBridgeHost: $ServerBridgeHost"
}
Write-Host ""

foreach ($check in $Checks) {
    $tag = if ($check.ok) { "[OK]  " } else { "[WARN]" }
    Write-Host "$tag $($check.name) - $($check.detail)"
}

Write-Host ""
if ($failed -gt 0) {
    Write-Host "共有 $failed 项告警，先按上面的提示处理。"
    exit 1
}

Write-Host "全部检查通过，可以继续把 profile 导入服务器。"
exit 0
