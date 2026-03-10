param(
    [string]$RepoPath = (Join-Path $PSScriptRoot ".."),
    [int]$IntervalSeconds = 300,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Resolve-GitCommand {
    foreach ($name in @("git.exe", "git")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    throw "Git command not found. Install Git and ensure git is in PATH."
}

function Resolve-RepoPath {
    param([string]$InputPath)

    $candidate = if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $InputPath
    }
    else {
        Join-Path (Get-Location) $InputPath
    }

    if (-not (Test-Path $candidate)) {
        throw "Repository path does not exist: $InputPath"
    }

    return (Resolve-Path $candidate).Path
}

$RepoPath = Resolve-RepoPath -InputPath $RepoPath
$GitCmd = Resolve-GitCommand

if (-not (Test-Path (Join-Path $RepoPath '.git'))) {
    throw "Target directory is not a Git repository: $RepoPath"
}

if ($IntervalSeconds -lt 15) {
    throw "IntervalSeconds must be at least 15 seconds."
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$IgnoreExitCode
    )

    $safeArgs = @('-c', "safe.directory=$RepoPath") + $Arguments
    $output = & $GitCmd @safeArgs 2>&1
    $exitCode = $LASTEXITCODE

    if (-not $IgnoreExitCode -and $exitCode -ne 0) {
        $detail = ($output | Out-String).Trim()
        if (-not $detail) {
            $detail = 'no additional output'
        }
        throw "git $($Arguments -join ' ') failed: $detail"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

function Test-DirtyWorktree {
    $result = Invoke-Git -Arguments @('status', '--porcelain')
    return $result.Output.Count -gt 0
}

Write-Host "Repository auto-pull started."
Write-Host "RepoPath: $RepoPath"
Write-Host "IntervalSeconds: $IntervalSeconds"
Write-Host "Mode: $(if ($Once) { 'pull-once' } else { 'watch' })"
Write-Host ""

while ($true) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] checking repository ..."

    if (Test-DirtyWorktree) {
        Write-Warning "Working tree is dirty; skipping this pull cycle."
        if ($Once) {
            exit 2
        }
    }
    else {
        $pullResult = Invoke-Git -Arguments @('pull', '--ff-only') -IgnoreExitCode
        if ($pullResult.ExitCode -eq 0) {
            foreach ($line in $pullResult.Output) {
                if ($line) {
                    Write-Host $line
                }
            }
        }
        else {
            $detail = ($pullResult.Output | Out-String).Trim()
            if (-not $detail) {
                $detail = 'no additional output'
            }
            Write-Warning "git pull --ff-only returned non-zero: $detail"
        }

        if ($Once) {
            exit $pullResult.ExitCode
        }
    }

    Start-Sleep -Seconds $IntervalSeconds
}
