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
    }
    catch {
    }
    return ""
}

function Ensure-Dir([string]$PathText) {
    if (-not (Test-Path -LiteralPath $PathText)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Write-Utf8File([string]$PathText, [string]$Content) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($PathText, $Content, $utf8NoBom)
}

function Write-JsonFile([string]$PathText, $Value, [int]$Depth = 10) {
    Write-Utf8File -PathText $PathText -Content (($Value | ConvertTo-Json -Depth $Depth) + "`n")
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
    throw "Failed to detect local Tailscale IPv4. Please pass -LocalNapCatHost explicitly."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DoctorScriptPath = Join-Path $PSScriptRoot "windows_local_qq_doctor.ps1"
$RemoteApplyScriptPath = Join-Path $PSScriptRoot "windows_local_qq_remote_apply.ps1"

$instances = @(
    [ordered]@{
        slug = "brain"
        role = "brain"
        agent_id = "qq-main"
        onebot_port = 3001
        bridge_port = 8011
    },
    [ordered]@{
        slug = "tech"
        role = "tech"
        agent_id = "brain-secretary-dev"
        onebot_port = 3002
        bridge_port = 8012
    },
    [ordered]@{
        slug = "review"
        role = "review"
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
                    url = "http://${ServerBridgeHost}:$($inst.bridge_port)/qq/message"
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
        server_bridge_url = "http://${ServerBridgeHost}:$($inst.bridge_port)/qq/message"
        local_napcat_api = "http://127.0.0.1:$($inst.onebot_port)"
        local_napcat_tailscale_api = "http://${LocalNapCatHost}:$($inst.onebot_port)"
        note = "Put this onebot11.json into the corresponding local NapCat instance config directory."
    }

    $onebotPath = Join-Path $instanceDir "onebot11.json"
    $bridgeInfoPath = Join-Path $instanceDir "bridge-info.json"

    Write-JsonFile -PathText $onebotPath -Value $onebotConfig
    Write-JsonFile -PathText $bridgeInfoPath -Value $bridgeInfo

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
Write-JsonFile -PathText $serverProfilePath -Value $serverProfile

$serverApplyPath = Join-Path $OutputRoot "server-apply.txt"
@"
Copy generated server-bridge-profile.json to server repo, for example:
  /root/brain-secretary/ops/windows-local-qq-profile.json

Then run on server:
  cd /root/brain-secretary
  python3 scripts/qq_bot_multi.py import-profile --profile ops/windows-local-qq-profile.json --json
  python3 scripts/qq_bot_multi.py restart --json
  python3 scripts/qq_bot_multi.py status --json
"@ | ForEach-Object { Write-Utf8File -PathText $serverApplyPath -Content $_ }

$doctorBatPath = Join-Path $OutputRoot "run-doctor.bat"
Write-WindowsBat -PathText $doctorBatPath -Lines @(
    '@echo off',
    'setlocal',
    ('powershell -ExecutionPolicy Bypass -File "{0}" -ServerBridgeHost "{1}" -LocalNapCatHost "{2}" -OutputRoot "{3}"' -f $DoctorScriptPath, $ServerBridgeHost, $LocalNapCatHost, $OutputRoot),
    'set "EXITCODE=%ERRORLEVEL%"',
    'echo.',
    'if %EXITCODE% NEQ 0 echo Doctor checks reported warnings. Review output above first.',
    'pause',
    'exit /b %EXITCODE%'
)

$openOutputBatPath = Join-Path $OutputRoot "open-output.bat"
Write-WindowsBat -PathText $openOutputBatPath -Lines @(
    '@echo off',
    'start "" "%~dp0"'
)

$remoteApplyBatPath = Join-Path $OutputRoot "apply-remote.bat"
Write-WindowsBat -PathText $remoteApplyBatPath -Lines @(
    '@echo off',
    'setlocal',
    ('powershell -ExecutionPolicy Bypass -File "{0}" -OutputRoot "{1}" -LocalProfilePath "{2}"' -f $RemoteApplyScriptPath, $OutputRoot, $serverProfilePath),
    'set "EXITCODE=%ERRORLEVEL%"',
    'echo.',
    'if %EXITCODE% NEQ 0 echo Remote apply failed. Review output above.',
    'pause',
    'exit /b %EXITCODE%'
)

$readmePath = Join-Path $OutputRoot "README.local.md"
@"
# Windows Local QQ/NapCat Scaffold

Generated at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Files

- `instances/brain/onebot11.json`
- `instances/tech/onebot11.json`
- `instances/review/onebot11.json`
- `server-bridge-profile.json`
- `server-apply.txt`
- `run-doctor.bat`
- `open-output.bat`
- `apply-remote.bat`

## Quick steps

1. Open this folder via `open-output.bat`.
2. Put the three `onebot11.json` files into three local NapCat instances.
3. Log in the three local QQ accounts.
4. Run `run-doctor.bat` for local checks.
5. If SSH to server is available, run `apply-remote.bat`.

## Parameters

- RepoRoot: $RepoRoot
- ServerBridgeHost: $ServerBridgeHost
- LocalNapCatHost: $LocalNapCatHost
- OutputRoot: $OutputRoot

## Bridge targets

- brain -> http://$ServerBridgeHost:8011/qq/message
- tech -> http://$ServerBridgeHost:8012/qq/message
- review -> http://$ServerBridgeHost:8013/qq/message
"@ | ForEach-Object { Write-Utf8File -PathText $readmePath -Content $_ }

Write-Host "Generated Windows local QQ scaffold: $OutputRoot"
Write-Host "Local NapCat Host: $LocalNapCatHost"
Write-Host "Server Bridge Host: $ServerBridgeHost"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Readme: $readmePath"

if ($OpenOutput) {
    Start-Process explorer.exe $OutputRoot | Out-Null
}
