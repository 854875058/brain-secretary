from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / "qq-bot"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


commands = load_module("agentteam_commands_test", ROOT / "qq-bot" / "bot" / "agentteam_commands.py")


class StubAgentTeamClient:
    def __init__(self) -> None:
        self.enabled = True
        self.configured = True
        self.label = "MDL AgentTeam"

    def status(self):
        return {
            "success": True,
            "message": "ok",
            "data": {
                "running": True,
                "mode": "planning_only",
                "mode_reason": "CodeAgent/TestAgent 仍是占位实现。",
                "brain": {
                    "total_tasks": 12,
                    "pending_tasks": 2,
                    "ready_tasks": 5,
                    "in_progress_tasks": 1,
                    "completed_tasks": 4,
                },
                "code": {"current_task": "统一分页策略", "task_status": "in_progress"},
                "test": {"total_test_runs": 8, "pass_rate": 93.33},
                "requests": {"total": 3, "pending": 1, "ready": 1, "completed": 1, "failed": 0},
            },
        }

    def list_tasks(self):
        return [
            {"id": 1, "title": "统一分页策略", "status": "ready", "priority": 4},
            {"id": 2, "title": "清理遗留 Vue 页面", "status": "pending", "priority": 5},
        ]

    def get_task(self, task_id: int):
        return {
            "id": task_id,
            "title": "统一分页策略",
            "status": "ready",
            "priority": 4,
            "assigned_to": None,
            "updated_at": "2026-03-17T10:00:00+08:00",
            "description": "让任务治理页和工作台列表使用相同分页口径",
            "plan": {
                "status": "ready",
                "plan": {
                    "summary": "收敛前后端分页参数和回包结构。",
                    "target_files": ["frontend/src/pages/TaskGovernancePage.jsx"],
                    "next_actions": ["统一 page/page_size 参数"],
                    "validation_steps": ["npm run build"],
                },
            },
            "details": {},
        }

    def list_requests(self):
        return [
            {"id": 5, "title": "统一工作台分页策略", "status": "pending", "priority": 4},
        ]

    def create_request(self, *, title: str, description: str, priority: int = 3, acceptance_criteria: str = ""):
        return {
            "id": 9,
            "title": title,
            "description": description,
            "priority": priority,
            "acceptance_criteria": acceptance_criteria,
            "status": "pending",
        }


class AgentTeamCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = StubAgentTeamClient()

    def test_status_command_renders_mode_and_counts(self) -> None:
        text = commands.run_agentteam_command("/at-status", self.client)
        self.assertIn("MDL AgentTeam 状态", text)
        self.assertIn("mode: planning_only", text)
        self.assertIn("tasks: total=12", text)

    def test_task_detail_renders_plan(self) -> None:
        text = commands.run_agentteam_command("/at-task 1", self.client)
        self.assertIn("Task #1", text)
        self.assertIn("plan_summary: 收敛前后端分页参数和回包结构。", text)
        self.assertIn("target_files:", text)

    def test_create_request_command(self) -> None:
        text = commands.run_agentteam_command(
            "/at-new 统一分页策略|让任务治理页和工作台分页一致|4|前端构建通过",
            self.client,
        )
        self.assertIn("已提交到 MDL AgentTeam", text)
        self.assertIn("request_id: 9", text)


if __name__ == "__main__":
    unittest.main()
