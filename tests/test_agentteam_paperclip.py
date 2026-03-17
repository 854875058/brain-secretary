from __future__ import annotations

import importlib.util
import json
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


sync_mod = load_module("agentteam_paperclip_test", ROOT / "qq-bot" / "bot" / "agentteam_paperclip.py")


class StubAgentTeamClient:
    def __init__(self) -> None:
        self.label = "MDL AgentTeam"
        self.api_base_url = "http://127.0.0.1:8090/api/agents"
        self.configured = True

    def status(self):
        return {
            "data": {
                "running": True,
                "mode": "planning_only",
                "mode_reason": "CodeAgent/TestAgent 仍是占位实现。",
                "brain": {
                    "total_tasks": 3,
                    "pending_tasks": 1,
                    "ready_tasks": 1,
                    "in_progress_tasks": 1,
                    "completed_tasks": 0,
                },
                "code": {"current_task": "统一分页策略", "task_status": "in_progress"},
                "test": {"total_test_runs": 8, "pass_rate": 93.33},
                "requests": {"total": 2, "pending": 1, "ready": 1, "completed": 0, "failed": 0},
            }
        }

    def list_tasks(self):
        return [
            {
                "id": 1,
                "title": "统一分页策略",
                "status": "in_progress",
                "priority": 4,
                "updated_at": "2026-03-17T12:00:00+08:00",
                "description": "让任务治理页和工作台列表使用相同分页口径",
                "plan": {"plan": {"summary": "统一前后端分页参数", "target_files": ["frontend/src/pages/A.jsx"]}},
                "details": {},
            },
            {
                "id": 2,
                "title": "清理遗留 Vue 页面",
                "status": "ready",
                "priority": 5,
                "updated_at": "2026-03-17T11:00:00+08:00",
                "description": "移除不再使用的旧 Vue 页面",
                "plan": {"plan": {"summary": "删除旧入口", "next_actions": ["删除 App.vue"]}},
                "details": {},
            },
        ]

    def list_requests(self):
        return [{"id": 3, "title": "统一工作台分页策略", "status": "pending", "priority": 4}]


class StubPaperclipClient:
    def __init__(self) -> None:
        self.configured = True
        self.created: list[dict] = []
        self.updated: list[dict] = []

    def create_issue(self, **payload):
        issue_id = f"issue-{len(self.created) + 1}"
        self.created.append({"id": issue_id, **payload})
        return {"id": issue_id, **payload}

    def update_issue(self, issue_id: str, **payload):
        self.updated.append({"id": issue_id, **payload})
        return {"id": issue_id, **payload}


class AgentTeamPaperclipSyncTests(unittest.TestCase):
    def _state_path(self, name: str) -> Path:
        path = ROOT / "tests" / name
        if path.exists():
            path.unlink()
        self.addCleanup(lambda: path.exists() and path.unlink())
        return path

    def test_sync_creates_parent_and_children(self) -> None:
        client = StubAgentTeamClient()
        paperclip = StubPaperclipClient()
        state_path = self._state_path("_tmp_agentteam_paperclip_state_1.json")
        payload = sync_mod.sync_agentteam_to_paperclip(
            agentteam_client=client,
            paperclip_client=paperclip,
            state_path=state_path,
        )

        self.assertEqual(payload["stats"]["created_parent"], 1)
        self.assertEqual(payload["stats"]["created_children"], 2)
        self.assertEqual(len(paperclip.created), 3)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["teams"])

    def test_second_sync_updates_changed_task(self) -> None:
        client = StubAgentTeamClient()
        paperclip = StubPaperclipClient()
        state_path = self._state_path("_tmp_agentteam_paperclip_state_2.json")
        sync_mod.sync_agentteam_to_paperclip(
            agentteam_client=client,
            paperclip_client=paperclip,
            state_path=state_path,
        )

        original_list_tasks = client.list_tasks

        def changed_tasks():
            items = original_list_tasks()
            items[0]["status"] = "completed"
            return items

        client.list_tasks = changed_tasks
        payload = sync_mod.sync_agentteam_to_paperclip(
            agentteam_client=client,
            paperclip_client=paperclip,
            state_path=state_path,
        )

        self.assertGreaterEqual(payload["stats"]["updated_children"], 1)
        self.assertTrue(paperclip.updated)


if __name__ == "__main__":
    unittest.main()
