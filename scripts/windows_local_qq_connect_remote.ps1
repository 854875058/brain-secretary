param(
    [Parameter(Mandatory = $true)]
    [string]$ServerBridgeHost,

    [string]$ServerSshTarget = "",
    [string]$LocalNapCatHost = "",
    [string]$OutputRoot = "",
    [switch]$SkipDoctor,
    [switch]$SkipRemoteApply,
    [switch]$NoOpenOutput
)

$ErrorActionPreference = "Stop"

function Require-File([string]$PathText, [string]$Name) {
    if (-not (Test-Path -LiteralPath $PathText)) {
        throw "$Name not found: $PathText"
    }
}

function Invoke-Step([string]$Title, [scriptblock]$Action) {
    Write-Host ""
    Write-Host "==> $Title"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Title failed with exit code $LASTEXITCODE"
    }
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $env:USERPROFILE "brain-secretary-local-qq"
}

$ScriptRoot = $PSScriptRoot
$ScaffoldScript = Join-Path $ScriptRoot "windows_local_qq_multi.ps1"
$DoctorScript = Join-Path $ScriptRoot "windows_local_qq_doctor.ps1"
$RemoteApplyScript = Join-Path $ScriptRoot "windows_local_qq_remote_apply.ps1"

Require-File -PathText $ScaffoldScript -Name "windows_local_qq_multi.ps1"
Require-File -PathText $DoctorScript -Name "windows_local_qq_doctor.ps1"
Require-File -PathText $RemoteApplyScript -Name "windows_local_qq_remote_apply.ps1"

$scaffoldArgs = @{
    ServerBridgeHost = $ServerBridgeHost
    OutputRoot = $OutputRoot
}
if ($LocalNapCatHost) {
    $scaffoldArgs.LocalNapCatHost = $LocalNapCatHost
}
if (-not $NoOpenOutput) {
    $scaffoldArgs.OpenOutput = $true
}

Invoke-Step -Title "Generate local QQ scaffold" -Action {
    & $ScaffoldScript @scaffoldArgs
}

if (-not $SkipDoctor) {
    $doctorArgs = @{
        ServerBridgeHost = $ServerBridgeHost
        OutputRoot = $OutputRoot
    }
    if ($LocalNapCatHost) {
        $doctorArgs.LocalNapCatHost = $LocalNapCatHost
    }

    Invoke-Step -Title "Run local doctor checks" -Action {
        & $DoctorScript @doctorArgs
    }
}
else {
    Write-Host ""
    Write-Host "[INFO] Skip doctor checks by option: -SkipDoctor"
}

$shouldApplyRemote = (-not $SkipRemoteApply) -and (-not [string]::IsNullOrWhiteSpace($ServerSshTarget))
if ($shouldApplyRemote) {
    $remoteArgs = @{
        ServerSshTarget = $ServerSshTarget
        OutputRoot = $OutputRoot
    }

    Invoke-Step -Title "Upload profile and apply on server" -Action {
        & $RemoteApplyScript @remoteArgs
    }
}
else {
    Write-Host ""
    if ($SkipRemoteApply) {
        Write-Host "[INFO] Skip remote apply by option: -SkipRemoteApply"
    }
    else {
        Write-Host "[INFO] ServerSshTarget is empty, remote apply skipped."
    }
}

Write-Host ""
Write-Host "Done. OutputRoot: $OutputRoot"
Write-Host "ServerBridgeHost: $ServerBridgeHost"
if ($ServerSshTarget) {
    Write-Host "ServerSshTarget: $ServerSshTarget"
}
