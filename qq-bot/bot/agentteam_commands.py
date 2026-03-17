from __future__ import annotations

from typing import Any

from bot.agentteam_client import AgentTeamClient, AgentTeamError

TASK_STATUSES = {"pending", "ready", "in_progress", "completed", "failed"}

AGENTTEAM_HELP = """AgentTeam 指令：
/at-status - 查看 AgentTeam 当前状态
/at-tasks [状态] - 查看任务队列，可选状态 pending|ready|in_progress|completed|failed
/at-task 编号 - 查看任务详情和计划
/at-requests - 查看用户提交需求列表
/at-new 标题|描述|优先级(可选)|验收标准(可选) - 提交新需求
/at-help - 查看本帮助"""


def _short(text: Any, limit: int = 120) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "..."


def _task_line(task: dict[str, Any]) -> str:
    task_id = int(task.get("id", 0) or 0)
    status = str(task.get("status") or "unknown").strip()
    priority = str(task.get("priority") or "unknown").strip()
    title = _short(task.get("title") or "", 50)
    return f"- #{task_id} [{status}/P{priority}] {title}"


def run_agentteam_command(cmd: str, client: AgentTeamClient) -> str:
    text = str(cmd or "").strip()
    if text in {"/at-help", "/agentteam", "/agentteam-help"}:
        return AGENTTEAM_HELP

    if not client.enabled:
        return (
            "AgentTeam Bridge 未启用。\n"
            "请设置 `QQ_BOT_AGENTTEAM_ENABLED=true`，并配置 `QQ_BOT_AGENTTEAM_API_BASE_URL` 指向目标项目的 `/api/agents`。"
        )

    if not client.configured:
        return "AgentTeam Bridge 已启用，但还没配好。至少需要 `QQ_BOT_AGENTTEAM_API_BASE_URL`。"

    if text == "/at-status":
        payload = client.status()
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            raise AgentTeamError("AgentTeam 状态数据缺失")
        brain = data.get("brain") or {}
        code = data.get("code") or {}
        test = data.get("test") or {}
        requests = data.get("requests") or {}
        lines = [
            f"{client.label} 状态",
            f"- running: {data.get('running')}",
            f"- mode: {data.get('mode') or 'unknown'}",
            f"- reason: {_short(data.get('mode_reason') or '', 220)}",
            f"- tasks: total={brain.get('total_tasks', 0)} pending={brain.get('pending_tasks', 0)} ready={brain.get('ready_tasks', 0)} in_progress={brain.get('in_progress_tasks', 0)} completed={brain.get('completed_tasks', 0)}",
            f"- code: current_task={code.get('current_task') or '(无)'} status={code.get('task_status') or '(无)'}",
            f"- test: runs={test.get('total_test_runs', 0)} pass_rate={test.get('pass_rate', 0)}",
            f"- requests: total={requests.get('total', 0)} pending={requests.get('pending', 0)} ready={requests.get('ready', 0)} completed={requests.get('completed', 0)} failed={requests.get('failed', 0)}",
        ]
        return "\n".join(lines)

    if text.startswith("/at-tasks"):
        raw = text[len("/at-tasks"):].strip().lower()
        wanted_status = raw if raw in TASK_STATUSES else ""
        tasks = client.list_tasks()
        if wanted_status:
            tasks = [task for task in tasks if str(task.get("status") or "").strip().lower() == wanted_status]
        if not tasks:
            return "当前没有符合条件的 AgentTeam 任务。"
        lines = [f"{client.label} 任务列表:"]
        for task in tasks[:12]:
            lines.append(_task_line(task))
        return "\n".join(lines)

    if text.startswith("/at-task "):
        raw = text[len("/at-task "):].strip()
        if not raw:
            return "用法: /at-task 编号"
        try:
            task_id = int(raw)
        except Exception:
            return "用法: /at-task 编号"
        task = client.get_task(task_id)
        plan = task.get("plan") or {}
        details = task.get("details") or {}
        lines = [
            f"Task #{task.get('id')}",
            f"- title: {task.get('title') or ''}",
            f"- status: {task.get('status') or ''}",
            f"- priority: {task.get('priority') or ''}",
            f"- assigned_to: {task.get('assigned_to') or '(未分配)'}",
            f"- updated_at: {task.get('updated_at') or ''}",
        ]
        description = _short(task.get("description") or "", 500)
        if description:
            lines.append("描述:")
            lines.append(description)
        if isinstance(plan, dict) and plan:
            lines.append(f"- plan_status: {plan.get('status') or ''}")
            if plan.get("plan"):
                inner = plan.get("plan") or {}
                if isinstance(inner, dict):
                    summary = _short(inner.get("summary") or "", 300)
                    if summary:
                        lines.append(f"- plan_summary: {summary}")
                    target_files = inner.get("target_files") or []
                    if target_files:
                        lines.append("- target_files:")
                        for item in target_files[:6]:
                            lines.append(f"  - {item}")
                    next_actions = inner.get("next_actions") or []
                    if next_actions:
                        lines.append("- next_actions:")
                        for item in next_actions[:6]:
                            lines.append(f"  - {item}")
                    validation_steps = inner.get("validation_steps") or []
                    if validation_steps:
                        lines.append("- validation_steps:")
                        for item in validation_steps[:6]:
                            lines.append(f"  - {item}")
        if isinstance(details, dict) and details:
            result_snippet = _short(details.get("result") or details.get("plan_summary") or "", 300)
            if result_snippet:
                lines.append(f"- detail: {result_snippet}")
        return "\n".join(lines)

    if text == "/at-requests":
        items = client.list_requests()
        if not items:
            return "当前没有 AgentTeam 用户需求。"
        lines = [f"{client.label} 需求列表:"]
        for item in items[:12]:
            lines.append(
                f"- request#{item.get('id')} [{item.get('status') or 'unknown'}/P{item.get('priority') or '?'}] {_short(item.get('title') or '', 50)}"
            )
        return "\n".join(lines)

    if text.startswith("/at-new "):
        payload = text[len("/at-new "):].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            return "用法: /at-new 标题|描述|优先级(可选)|验收标准(可选)"
        title = parts[0]
        description = parts[1]
        priority = 3
        if len(parts) > 2 and parts[2]:
            try:
                priority = int(parts[2])
            except Exception:
                return "优先级必须是 1 到 5 的整数。"
        acceptance = parts[3] if len(parts) > 3 else ""
        item = client.create_request(
            title=title,
            description=description,
            priority=priority,
            acceptance_criteria=acceptance,
        )
        return (
            f"已提交到 {client.label}\n"
            f"- request_id: {item.get('id')}\n"
            f"- status: {item.get('status') or 'pending'}\n"
            f"- title: {item.get('title') or title}"
        )

    if text.startswith("/at-"):
        return AGENTTEAM_HELP

    raise AgentTeamError(f"unsupported command: {text}")
