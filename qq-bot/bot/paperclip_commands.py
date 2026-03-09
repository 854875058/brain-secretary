from __future__ import annotations

from typing import Any

from bot.paperclip_client import PaperclipClient, PaperclipError

ISSUE_STATUSES = {"backlog", "todo", "in_progress", "blocked", "review", "done", "cancelled"}

PAPERCLIP_HELP = """Paperclip 指令：
/pc-status - 查看 Paperclip 连通性与配置摘要
/pc-agents - 查看 Paperclip agent 列表
/pc-issues [状态或关键词] - 查看最近 issues
/pc-issue 编号或ID - 查看 issue 详情
/pc-new 标题|描述|agent(可选) - 创建 issue
/pc-run agent|标题|描述 - 创建 issue 并立即唤醒对应 agent
/pc-wake agent [原因] - 手动唤醒 agent
/pc-help - 查看本帮助"""


def _short(text: Any, limit: int = 140) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "…"


def _agent_label(agent: dict[str, Any]) -> str:
    name = str(agent.get("name") or "unknown").strip()
    title = str(agent.get("title") or "").strip()
    role = str(agent.get("role") or "").strip()
    agent_id = str(agent.get("id") or "").strip()
    pieces = [name]
    if title:
        pieces.append(title)
    if role:
        pieces.append(role)
    if agent_id:
        pieces.append(agent_id[:8])
    return " | ".join(piece for piece in pieces if piece)


def _issue_identifier(issue: dict[str, Any]) -> str:
    return str(issue.get("identifier") or issue.get("id") or "?").strip() or "?"


def _issue_line(issue: dict[str, Any]) -> str:
    identifier = _issue_identifier(issue)
    status = str(issue.get("status") or "unknown").strip()
    priority = str(issue.get("priority") or "unknown").strip()
    title = _short(issue.get("title") or "", 60)
    assignee = str(issue.get("assigneeAgentId") or "").strip()
    assignee_hint = f" -> {assignee[:8]}" if assignee else ""
    return f"- {identifier} [{status}/{priority}] {title}{assignee_hint}"


def _resolve_agent_id(client: PaperclipClient, ref: str | None) -> tuple[str | None, str | None]:
    raw = str(ref or "").strip()
    if not raw:
        default_id = str(client.default_assignee_agent_id or "").strip() or None
        return default_id, None
    agent = client.resolve_agent_ref(raw)
    agent_id = str(agent.get("id") or "").strip()
    if not agent_id:
        raise PaperclipError(f"Paperclip agent 缺少 id: {raw}")
    return agent_id, _agent_label(agent)


def run_paperclip_command(cmd: str, client: PaperclipClient) -> str:
    text = str(cmd or "").strip()
    if text in {"/pc-help", "/paperclip", "/paperclip-help"}:
        return PAPERCLIP_HELP

    if not client.enabled:
        return (
            "Paperclip 未启用。\n"
            "请设置环境变量 `QQ_BOT_PAPERCLIP_ENABLED=true`，并至少配置 `QQ_BOT_PAPERCLIP_API_BASE_URL`。"
        )

    if text == "/pc-status":
        health = client.health() if client.configured else None
        summary = client.summary()
        lines = [
            "Paperclip 状态",
            f"- enabled: {summary['enabled']}",
            f"- configured: {summary['configured']}",
            f"- api_base_url: {summary['api_base_url'] or '(未配置)'}",
            f"- company_id: {summary['company_id'] or '(未配置)'}",
            f"- auth_mode: {summary['auth_mode']}",
            f"- default_assignee_agent_id: {summary['default_assignee_agent_id'] or '(未配置)'}",
            f"- timeout_seconds: {summary['timeout_seconds']}",
            f"- health: {_short(health, 300)}",
        ]
        return "\n".join(lines)

    if not client.configured:
        return "Paperclip 已启用，但还没配好。至少需要 `QQ_BOT_PAPERCLIP_API_BASE_URL`。"

    if text == "/pc-agents":
        agents = client.list_agents()
        if not agents:
            return "Paperclip 当前没有 agent，或当前账号无权查看。"
        lines = ["Paperclip agents:"]
        for agent in agents[:12]:
            lines.append(f"- {_agent_label(agent)}")
        return "\n".join(lines)

    if text.startswith("/pc-issues"):
        raw = text[len("/pc-issues"):].strip()
        status = raw if raw in ISSUE_STATUSES else None
        query = None if status else (raw or None)
        issues = client.list_issues(status=status, q=query)
        if not issues:
            return "未找到符合条件的 Paperclip issues。"
        lines = ["Paperclip issues:"]
        for issue in issues[:10]:
            lines.append(_issue_line(issue))
        return "\n".join(lines)

    if text.startswith("/pc-issue "):
        issue_ref = text[len("/pc-issue "):].strip()
        if not issue_ref:
            return "用法: /pc-issue 编号或ID"
        issue = client.get_issue(issue_ref)
        lines = [
            f"Issue: {_issue_identifier(issue)}",
            f"- title: {issue.get('title') or ''}",
            f"- status: {issue.get('status') or ''}",
            f"- priority: {issue.get('priority') or ''}",
            f"- assigneeAgentId: {issue.get('assigneeAgentId') or '(未分配)'}",
            f"- projectId: {issue.get('projectId') or '(无)'}",
            f"- goalId: {issue.get('goalId') or '(无)'}",
            f"- createdAt: {issue.get('createdAt') or ''}",
        ]
        description = _short(issue.get("description") or "", 800)
        if description:
            lines.append("描述:")
            lines.append(description)
        return "\n".join(lines)

    if text.startswith("/pc-new "):
        payload = text[len("/pc-new "):].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            return "用法: /pc-new 标题|描述|agent(可选)"
        title, description = parts[0], parts[1]
        assignee_ref = parts[2] if len(parts) > 2 else None
        assignee_id, assignee_label = _resolve_agent_id(client, assignee_ref)
        issue = client.create_issue(title=title, description=description, assignee_agent_id=assignee_id)
        return (
            f"已创建 Paperclip issue: {_issue_identifier(issue)}\n"
            f"- title: {issue.get('title') or title}\n"
            f"- assignee: {assignee_label or assignee_id or '(未分配)'}"
        )

    if text.startswith("/pc-wake "):
        payload = text[len("/pc-wake "):].strip()
        if not payload:
            return "用法: /pc-wake agent [原因]"
        agent_ref, _, reason = payload.partition(" ")
        agent = client.resolve_agent_ref(agent_ref)
        agent_id = str(agent.get("id") or "").strip()
        result = client.wake_agent(agent_id, reason=reason.strip() or f"QQ 指令唤醒 {agent_ref}") or {}
        return f"已唤醒 Paperclip agent: {_agent_label(agent)}\n- result: {_short(result, 300)}"

    if text.startswith("/pc-run "):
        payload = text[len("/pc-run "):].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 3 or not parts[0] or not parts[1] or not parts[2]:
            return "用法: /pc-run agent|标题|描述"
        agent_ref, title, description = parts[0], parts[1], parts[2]
        agent = client.resolve_agent_ref(agent_ref)
        agent_id = str(agent.get("id") or "").strip()
        issue = client.create_issue(title=title, description=description, assignee_agent_id=agent_id)
        wake = client.wake_agent(
            agent_id,
            reason=f"QQ run: {_issue_identifier(issue)} {title}",
            payload={"issueId": issue.get("id"), "issueIdentifier": issue.get("identifier")},
        ) or {}
        return f"已创建并唤醒: {_issue_identifier(issue)}\n- agent: {_agent_label(agent)}\n- wake: {_short(wake, 300)}"

    if text.startswith("/pc-"):
        return PAPERCLIP_HELP

    raise PaperclipError(f"unsupported command: {text}")
