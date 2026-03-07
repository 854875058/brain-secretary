param(
    [Parameter(Mandatory = $true)]
    [string]$ServerBridgeHost,

    [string]$LocalNapCatHost = "",
    [string]$OutputRoot = "",
    [string]$ServerProfileFileName = "server-bridge-profile.json",
    [switch]$OpenOutput
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

function Ensure-Dir([string]$PathText) {
    if (-not (Test-Path -LiteralPath $PathText)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Write-Utf8File([string]$PathText, [string]$Content) {
    Set-Content -Path $PathText -Value $Content -Encoding UTF8
}

function Write-WindowsBat([string]$PathText, [string[]]$Lines) {
    Write-Utf8File -PathText $PathText -Content (($Lines -join "`r`n") + "`r`n")
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $env:USERPROFILE "brain-secretary-local-qq"
}

if (-not $LocalNapCatHost) {
    $LocalNapCatHost = Get-TailscaleIPv4
}

if (-not $LocalNapCatHost) {
    throw "未能自动识别本机 Tailscale IPv4，请手动传入 -LocalNapCatHost。"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DoctorScriptPath = Join-Path $PSScriptRoot "windows_local_qq_doctor.ps1"

$instances = @(
    [ordered]@{
        slug = "brain"
        role = "大脑号"
        agent_id = "qq-main"
        onebot_port = 3001
        bridge_port = 8011
    },
    [ordered]@{
        slug = "tech"
        role = "技术号"
        agent_id = "brain-secretary-dev"
        onebot_port = 3002
        bridge_port = 8012
    },
    [ordered]@{
        slug = "review"
        role = "方案验收号"
        agent_id = "brain-secretary-review"
        onebot_port = 3003
        bridge_port = 8013
    }
)

Ensure-Dir $OutputRoot
$instancesRoot = Join-Path $OutputRoot "instances"
Ensure-Dir $instancesRoot

$serverProfile = [ordered]@{
    mode = "windows-local-napcat"
    bridge_host = "0.0.0.0"
    napcat_host = $LocalNapCatHost
    instances = @()
}

foreach ($inst in $instances) {
    $instanceDir = Join-Path $instancesRoot $inst.slug
    Ensure-Dir $instanceDir

    $onebotConfig = [ordered]@{
        http = [ordered]@{
            enable = $true
            host = "127.0.0.1"
            port = $inst.onebot_port
            post = @(
                [ordered]@{
                    url = "http://$ServerBridgeHost:$($inst.bridge_port)/qq/message"
                    secret = ""
                }
            )
        }
        ws = [ordered]@{ enable = $false }
        reverseWs = [ordered]@{ enable = $false }
        GroupLocalTime = [ordered]@{
            Record = $false
            RecordList = @()
        }
        debug = $false
        heartInterval = 30000
        messagePostFormat = "array"
        enableLocalFile2Url = $true
        musicSignUrl = ""
        reportSelfMessage = $false
        token = ""
    }

    $bridgeInfo = [ordered]@{
        slug = $inst.slug
        role = $inst.role
        agent_id = $inst.agent_id
        server_bridge_url = "http://$ServerBridgeHost:$($inst.bridge_port)/qq/message"
        local_napcat_api = "http://127.0.0.1:$($inst.onebot_port)"
        local_napcat_tailscale_api = "http://$LocalNapCatHost:$($inst.onebot_port)"
        note = "把 onebot11.json 放进这个 QQ 实例对应的 NapCat 配置目录。"
    }

    $onebotPath = Join-Path $instanceDir "onebot11.json"
    $bridgeInfoPath = Join-Path $instanceDir "bridge-info.json"

    $onebotConfig | ConvertTo-Json -Depth 10 | Set-Content -Path $onebotPath -Encoding UTF8
    $bridgeInfo | ConvertTo-Json -Depth 10 | Set-Content -Path $bridgeInfoPath -Encoding UTF8

    $serverProfile.instances += [ordered]@{
        slug = $inst.slug
        role = $inst.role
        agent_id = $inst.agent_id
        bridge_host = "0.0.0.0"
        napcat_host = $LocalNapCatHost
        bridge_port = $inst.bridge_port
        onebot_port = $inst.onebot_port
    }
}

$serverProfilePath = Join-Path $OutputRoot $ServerProfileFileName
$serverProfile | ConvertTo-Json -Depth 10 | Set-Content -Path $serverProfilePath -Encoding UTF8

$serverApplyPath = Join-Path $OutputRoot "server-apply.txt"
@"
把生成的 server-bridge-profile.json 复制到服务器仓库中，例如：
  /root/brain-secretary/ops/windows-local-qq-profile.json

然后在服务器执行：
  cd /root/brain-secretary
  python3 scripts/qq_bot_multi.py import-profile --profile ops/windows-local-qq-profile.json --json
  python3 scripts/qq_bot_multi.py restart --json
  python3 scripts/qq_bot_multi.py status --json
"@ | Set-Content -Path $serverApplyPath -Encoding UTF8

$doctorBatPath = Join-Path $OutputRoot "run-doctor.bat"
Write-WindowsBat -PathText $doctorBatPath -Lines @(
    '@echo off',
    'setlocal',
    ('powershell -ExecutionPolicy Bypass -File "{0}" -ServerBridgeHost "{1}" -LocalNapCatHost "{2}" -OutputRoot "{3}"' -f $DoctorScriptPath, $ServerBridgeHost, $LocalNapCatHost, $OutputRoot),
    'set "EXITCODE=%ERRORLEVEL%"',
    'echo.',
    'if %EXITCODE% NEQ 0 echo 检查里有告警，先看上面的输出再处理。',
    'pause',
    'exit /b %EXITCODE%'
)

$openOutputBatPath = Join-Path $OutputRoot "open-output.bat"
Write-WindowsBat -PathText $openOutputBatPath -Lines @(
    '@echo off',
    'start "" "%~dp0"'
)

$readmePath = Join-Path $OutputRoot "README.local.md"
@"
# Windows 本地三开 QQ / NapCat 脚手架

生成时间：$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## 你现在手里有什么

- `instances/brain/onebot11.json`
- `instances/tech/onebot11.json`
- `instances/review/onebot11.json`
- `server-bridge-profile.json`
- `server-apply.txt`
- `run-doctor.bat`
- `open-output.bat`

## 最省事的用法

1. 先双击 `open-output.bat` 打开这个目录。
2. 把 3 份 `onebot11.json` 分别塞进 3 个本地 QQ / NapCat 实例。
3. 登录 3 个本地 QQ 号。
4. 配完后双击 `run-doctor.bat` 做本地自检。
5. 把 `server-bridge-profile.json` 交给服务器侧导入。

## 本地要做的事

1. 先确保你的 Windows 和服务器在同一个 Tailscale 网络。
2. 把 3 个 `onebot11.json` 分别放到 3 个本地 QQ / NapCat 实例对应的配置目录。
3. 让 3 个本地 QQ 实例分别登录：
   - brain -> 大脑号
   - tech -> 技术号
   - review -> 方案验收号
4. 确认本机端口 `3001/3002/3003` 都能监听。
5. 把 `server-bridge-profile.json` 交给服务器侧应用。

## 生成参数

- RepoRoot: $RepoRoot
- ServerBridgeHost: $ServerBridgeHost
- LocalNapCatHost: $LocalNapCatHost
- OutputRoot: $OutputRoot

## 每个实例的桥接目标

- brain -> http://$ServerBridgeHost:8011/qq/message
- tech -> http://$ServerBridgeHost:8012/qq/message
- review -> http://$ServerBridgeHost:8013/qq/message

## 建议

- 本地 QQ / NapCat 请优先跑在你常用的 Windows 电脑上，不要再放云服务器扫码。
- 如果本机 Tailscale IP 变化，重新运行本脚本，再把新的 `server-bridge-profile.json` 应用到服务器。
- `run-doctor.bat` 是你后面最好用的排障入口，先看它的输出再看别的。
"@ | Set-Content -Path $readmePath -Encoding UTF8

Write-Host "已生成 Windows 本地三开 QQ 脚手架： $OutputRoot"
Write-Host "本机 NapCat Host: $LocalNapCatHost"
Write-Host "服务器桥接 Host: $ServerBridgeHost"
Write-Host "仓库根目录: $RepoRoot"
Write-Host "下一步先看： $readmePath"

if ($OpenOutput) {
    Start-Process explorer.exe $OutputRoot | Out-Null
}
