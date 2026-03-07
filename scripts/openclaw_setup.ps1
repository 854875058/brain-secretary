param(
    [string]$AgentId = "brain-secretary",
    [string]$Workspace = "",
    [string]$Model = "penguin/claude-sonnet-4-6"
)

$ErrorActionPreference = "Stop"

if (-not $Workspace) {
    # 默认使用仓库根目录（脚本所在目录的上一级）
    $Workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Write-Host "AgentId=$AgentId"
Write-Host "Workspace=$Workspace"
Write-Host "Model=$Model"

try {
    $agentsJson = & openclaw agents list --json 2>$null
} catch {
    Write-Error "无法执行 openclaw。请确认 OpenClaw CLI 已安装并在 PATH 中。"
    throw
}

$agents = @()
try {
    if ($agentsJson) { $agents = $agentsJson | ConvertFrom-Json }
} catch {
    Write-Warning "解析 openclaw agents list --json 失败，将继续尝试创建 Agent。"
}

$exists = $false
if ($agents) {
    foreach ($a in $agents) {
        if ($a.id -eq $AgentId) { $exists = $true; break }
    }
}

if (-not $exists) {
    Write-Host "创建 OpenClaw Agent: $AgentId"
    & openclaw agents add $AgentId --workspace $Workspace --model $Model --non-interactive
} else {
    Write-Host "OpenClaw Agent 已存在: $AgentId"
}

Write-Host "从工作区 IDENTITY.md 同步身份信息（可选但推荐）"
& openclaw agents set-identity --agent $AgentId --workspace $Workspace --from-identity

Write-Host "完成。你现在可以在 QQ Bridge 配置中使用 openclaw.agent_id=$AgentId"

