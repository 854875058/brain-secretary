from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.agentteam_client import AgentTeamClient, AgentTeamError
from bot.paperclip_client import PaperclipClient, PaperclipError
from bot.runtime_paths import DATA_DIR, ensure_runtime_dirs

logger = logging.getLogger(__name__)

DEFAULT_TASK_LIMIT = 20
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_STATE_PATH = DATA_DIR / "agentteam-paperclip-state.json"

TASK_STATUS_TO_ISSUE_STATUS = {
    "pending": "backlog",
    "ready": "todo",
    "in_progress": "in_progress",
    "completed": "done",
    "failed": "blocked",
}

TASK_STATUS_SORT_ORDER = {
    "in_progress": 0,
    "ready": 1,
    "pending": 2,
    "failed": 3,
    "completed": 4,
}


@dataclass(slots=True)
class AgentTeamPaperclipStats:
    created_parent: int = 0
    updated_parent: int = 0
    created_children: int = 0
    updated_children: int = 0
    closed_children: int = 0
    skipped: int = 0
    scanned_tasks: int = 0
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _str_env(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip()


def _trim(text: str | None, limit: int = 240) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)].rstrip() + "…"


def _state_key(label: str, api_base_url: str) -> str:
    payload = f"{label}|{api_base_url}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:20]


def _payload_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _clean_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"version": 1, "teams": {}}
    cleaned = dict(raw)
    cleaned.setdefault("version", 1)
    cleaned.setdefault("teams", {})
    return cleaned


def load_sync_state(path: Path | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    state_path = Path(path or DEFAULT_STATE_PATH)
    if not state_path.exists():
        return {"version": 1, "teams": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "teams": {}}
    return _clean_state(payload)


def save_sync_state(state: dict[str, Any], path: Path | None = None) -> None:
    ensure_runtime_dirs()
    state_path = Path(path or DEFAULT_STATE_PATH)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _task_priority(task: dict[str, Any]) -> int:
    try:
        return int(task.get("priority") or 0)
    except Exception:
        return 0


def _task_status(task: dict[str, Any]) -> str:
    return str(task.get("status") or "pending").strip().lower()


def _sort_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tasks,
        key=lambda task: (
            TASK_STATUS_SORT_ORDER.get(_task_status(task), 99),
            -_task_priority(task),
            str(task.get("updated_at") or ""),
        ),
    )


def _issue_status_from_task(task: dict[str, Any]) -> str:
    return TASK_STATUS_TO_ISSUE_STATUS.get(_task_status(task), "todo")


def _issue_status_from_overview(status_payload: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    data = status_payload.get("data") if isinstance(status_payload, dict) else {}
    if isinstance(data, dict) and data.get("running"):
        if any(_task_status(task) == "in_progress" for task in tasks):
            return "in_progress"
        if any(_task_status(task) in {"ready", "pending"} for task in tasks):
            return "todo"
        if tasks and all(_task_status(task) == "completed" for task in tasks):
            return "done"
    if any(_task_status(task) == "failed" for task in tasks):
        return "blocked"
    if tasks:
        return "todo"
    return "backlog"


def _render_parent_payload(client: AgentTeamClient, status_payload: dict[str, Any], tasks: list[dict[str, Any]], requests: list[dict[str, Any]]) -> dict[str, Any]:
    data = status_payload.get("data") if isinstance(status_payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    brain = data.get("brain") or {}
    code = data.get("code") or {}
    test = data.get("test") or {}
    request_stats = data.get("requests") or {}

    lines = [
        f"# {client.label} 状态看板",
        "",
        f"- api_base_url: `{client.api_base_url}`",
        f"- running: `{data.get('running')}`",
        f"- mode: `{data.get('mode') or 'unknown'}`",
        f"- mode_reason: {_trim(data.get('mode_reason') or '', 300)}",
        f"- synced_at: `{_now_iso()}`",
        "",
        "## 任务统计",
        "",
        f"- total: {brain.get('total_tasks', 0)}",
        f"- pending: {brain.get('pending_tasks', 0)}",
        f"- ready: {brain.get('ready_tasks', 0)}",
        f"- in_progress: {brain.get('in_progress_tasks', 0)}",
        f"- completed: {brain.get('completed_tasks', 0)}",
        "",
        "## 当前执行态",
        "",
        f"- code.current_task: {_trim(code.get('current_task') or '(无)', 200)}",
        f"- code.task_status: `{code.get('task_status') or '(无)'}`",
        f"- test.total_test_runs: {test.get('total_test_runs', 0)}",
        f"- test.pass_rate: {test.get('pass_rate', 0)}",
        "",
        "## 用户需求统计",
        "",
        f"- requests.total: {request_stats.get('total', len(requests))}",
        f"- requests.pending: {request_stats.get('pending', 0)}",
        f"- requests.ready: {request_stats.get('ready', 0)}",
        f"- requests.completed: {request_stats.get('completed', 0)}",
        f"- requests.failed: {request_stats.get('failed', 0)}",
    ]

    if requests:
        lines.extend(["", "## 最近需求", ""])
        for item in requests[:8]:
            lines.append(
                f"- request#{item.get('id')} [{item.get('status') or 'unknown'}/P{item.get('priority') or '?'}] {_trim(item.get('title') or '', 80)}"
            )

    if tasks:
        lines.extend(["", "## 活跃任务", ""])
        for task in _sort_tasks(tasks)[:10]:
            lines.append(
                f"- task#{task.get('id')} [{task.get('status') or 'unknown'}/P{task.get('priority') or '?'}] {_trim(task.get('title') or '', 80)}"
            )

    return {
        "title": f"{client.label} 状态看板",
        "description": "\n".join(lines).strip() + "\n",
        "status": _issue_status_from_overview(status_payload, tasks),
        "priority": "medium",
    }


def _render_task_payload(client: AgentTeamClient, task: dict[str, Any], parent_issue_id: str) -> dict[str, Any]:
    plan = task.get("plan") or {}
    details = task.get("details") or {}
    inner_plan = plan.get("plan") if isinstance(plan, dict) else {}
    if not isinstance(inner_plan, dict):
        inner_plan = {}

    lines = [
        f"# {client.label} 任务投影",
        "",
        f"- task_id: `{task.get('id')}`",
        f"- status: `{task.get('status') or ''}`",
        f"- priority: `{task.get('priority') or ''}`",
        f"- assigned_to: `{task.get('assigned_to') or '(未分配)'}`",
        f"- updated_at: `{task.get('updated_at') or ''}`",
        f"- synced_at: `{_now_iso()}`",
        "",
        "## 描述",
        "",
        _trim(task.get("description") or "", 1200),
    ]

    summary = _trim(inner_plan.get("summary") or "", 800)
    if summary:
        lines.extend(["", "## 计划摘要", "", summary])

    target_files = inner_plan.get("target_files") or []
    if target_files:
        lines.extend(["", "## 目标文件", ""])
        for item in target_files[:10]:
            lines.append(f"- {item}")

    next_actions = inner_plan.get("next_actions") or []
    if next_actions:
        lines.extend(["", "## 下一步动作", ""])
        for item in next_actions[:10]:
            lines.append(f"- {item}")

    validation_steps = inner_plan.get("validation_steps") or []
    if validation_steps:
        lines.extend(["", "## 验证步骤", ""])
        for item in validation_steps[:10]:
            lines.append(f"- {item}")

    blockers = inner_plan.get("blockers") or []
    if blockers:
        lines.extend(["", "## 阻塞项", ""])
        for item in blockers[:10]:
            lines.append(f"- {item}")

    result_hint = _trim(details.get("result") or details.get("plan_summary") or "", 800)
    if result_hint:
        lines.extend(["", "## 结果摘录", "", result_hint])

    return {
        "title": f"{client.label} | Task #{task.get('id')} | {_trim(task.get('title') or '', 64)}",
        "description": "\n".join(lines).strip() + "\n",
        "status": _issue_status_from_task(task),
        "priority": "high" if _task_priority(task) >= 4 else "medium",
        "parent_id": parent_issue_id,
    }


def sync_agentteam_to_paperclip(
    *,
    agentteam_client: AgentTeamClient,
    paperclip_client: PaperclipClient,
    state_path: Path | None = None,
    task_limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not agentteam_client.configured:
        raise AgentTeamError("AgentTeam 未启用或未配置 api_base_url")
    if not paperclip_client.configured:
        raise PaperclipError("Paperclip 未启用或未配置 api_base_url")

    ensure_runtime_dirs()
    stats = AgentTeamPaperclipStats(dry_run=dry_run)
    state = load_sync_state(state_path)
    team_key = _state_key(agentteam_client.label, agentteam_client.api_base_url)
    team_state = state.setdefault("teams", {}).setdefault(team_key, {"parent": {}, "tasks": {}})
    parent_state = team_state.setdefault("parent", {})
    task_state = team_state.setdefault("tasks", {})

    limit = max(1, int(task_limit if task_limit is not None else _int_env("QQ_BOT_AGENTTEAM_PAPERCLIP_TASK_LIMIT", DEFAULT_TASK_LIMIT)))
    status_payload = agentteam_client.status()
    tasks = _sort_tasks(agentteam_client.list_tasks())[:limit]
    requests = agentteam_client.list_requests()
    stats.scanned_tasks = len(tasks)

    parent_payload = _render_parent_payload(agentteam_client, status_payload, tasks, requests)
    parent_digest = _payload_digest(parent_payload)
    parent_issue_id = str(parent_state.get("issue_id") or "").strip()

    if not parent_issue_id:
        if dry_run:
            parent_issue_id = f"dry-parent-{team_key}"
        else:
            created_parent = paperclip_client.create_issue(
                title=parent_payload["title"],
                description=parent_payload["description"],
                status=parent_payload["status"],
                priority=parent_payload["priority"],
                use_default_assignee=False,
            )
            parent_issue_id = str(created_parent.get("id") or "").strip()
        parent_state.update({"issue_id": parent_issue_id, "digest": parent_digest, "updated_at": _now_iso()})
        stats.created_parent += 1
    elif parent_state.get("digest") != parent_digest:
        if not dry_run:
            paperclip_client.update_issue(
                parent_issue_id,
                title=parent_payload["title"],
                description=parent_payload["description"],
                status=parent_payload["status"],
                priority=parent_payload["priority"],
            )
        parent_state.update({"issue_id": parent_issue_id, "digest": parent_digest, "updated_at": _now_iso()})
        stats.updated_parent += 1
    else:
        stats.skipped += 1

    visible_task_ids: set[str] = set()
    for task in tasks:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        visible_task_ids.add(task_id)
        payload = _render_task_payload(agentteam_client, task, parent_issue_id)
        digest = _payload_digest(payload)
        entry = task_state.get(task_id) or {}
        issue_id = str(entry.get("issue_id") or "").strip()

        if not issue_id:
            if dry_run:
                issue_id = f"dry-task-{task_id}"
            else:
                created_issue = paperclip_client.create_issue(
                    title=payload["title"],
                    description=payload["description"],
                    status=payload["status"],
                    priority=payload["priority"],
                    parent_id=parent_issue_id,
                    use_default_assignee=False,
                )
                issue_id = str(created_issue.get("id") or "").strip()
            task_state[task_id] = {
                "issue_id": issue_id,
                "digest": digest,
                "status": payload["status"],
                "updated_at": _now_iso(),
            }
            stats.created_children += 1
        elif entry.get("digest") != digest:
            if not dry_run:
                paperclip_client.update_issue(
                    issue_id,
                    title=payload["title"],
                    description=payload["description"],
                    status=payload["status"],
                    priority=payload["priority"],
                    parent_id=parent_issue_id,
                )
            task_state[task_id] = {
                "issue_id": issue_id,
                "digest": digest,
                "status": payload["status"],
                "updated_at": _now_iso(),
            }
            stats.updated_children += 1
        else:
            stats.skipped += 1

    missing_task_ids = [task_id for task_id in list(task_state.keys()) if task_id not in visible_task_ids]
    for task_id in missing_task_ids:
        entry = task_state.get(task_id) or {}
        issue_id = str(entry.get("issue_id") or "").strip()
        if issue_id and not dry_run:
            paperclip_client.update_issue(
                issue_id,
                status="cancelled",
                comment="AgentTeam 任务队列中已不再包含该任务，自动标记为已移出同步范围。",
            )
        task_state.pop(task_id, None)
        stats.closed_children += 1

    if not dry_run:
        save_sync_state(state, state_path)

    return {
        "stats": stats.to_dict(),
        "parent_issue_id": parent_issue_id,
        "task_count": len(tasks),
        "request_count": len(requests),
        "state_path": str(Path(state_path or DEFAULT_STATE_PATH)),
    }
