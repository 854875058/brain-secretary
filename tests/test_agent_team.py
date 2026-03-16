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


agent_team = load_module("agent_team_test", ROOT / "qq-bot" / "bot" / "agent_team.py")


class StubKnowledgeBase:
    def __init__(self) -> None:
        self.notes: list[str] = []

    def render_context(self, query: str, *, limit: int = 6) -> str:
        return f"[stub-kb] {query} -> 规则：输出必须严格 JSON。"

    def remember(self, note: str, *, kind: str = "remember", source: str = "agentteam"):
        self.notes.append(note)
        return {"note": note, "kind": kind, "source": source}


class AgentTeamCoordinatorTests(unittest.TestCase):
    def test_default_flow_runs_to_done_and_writes_memory(self) -> None:
        kb = StubKnowledgeBase()

        async def research(prompt: str, state, agent) -> str:
            return "研究：必须输出 JSON，并补充 source_page。"

        async def execute(prompt: str, state, agent) -> str:
            return '{"summary":"ok","source_page":[1,2]}'

        async def review(prompt: str, state, agent) -> str:
            return '{"approved": true, "feedback": "通过", "remember": true, "memory_note": "同类任务默认补 source_page。"}'

        coordinator = agent_team.build_default_agent_team(
            knowledge_base=kb,
            researcher_callable=research,
            executor_callable=execute,
            reviewer_callable=review,
            researcher_agent_id="",
            executor_agent_id="",
            reviewer_agent_id="",
        )

        state = coordinator.run_sync("请处理 PDF 报表")

        self.assertEqual(state.current_status, "done")
        self.assertEqual(len(state.intermediate_steps), 3)
        self.assertEqual(state.final_output, '{"summary":"ok","source_page":[1,2]}')
        self.assertIn("同类任务默认补 source_page。", kb.notes)

    def test_review_can_route_back_to_execution_once(self) -> None:
        kb = StubKnowledgeBase()
        review_calls = {"count": 0}

        async def research(prompt: str, state, agent) -> str:
            return "研究：先产出草稿，再根据复核反馈修正。"

        async def execute(prompt: str, state, agent) -> str:
            feedback = str(state.metadata.get("review_feedback") or "").strip()
            if feedback:
                return '{"summary":"patched","source_page":[3]}'
            return '{"summary":"draft"}'

        async def review(prompt: str, state, agent) -> str:
            review_calls["count"] += 1
            if review_calls["count"] == 1:
                return '{"approved": false, "feedback": "缺少 source_page", "remember": false, "memory_note": ""}'
            return '{"approved": true, "feedback": "通过", "remember": false, "memory_note": ""}'

        coordinator = agent_team.build_default_agent_team(
            knowledge_base=kb,
            researcher_callable=research,
            executor_callable=execute,
            reviewer_callable=review,
            researcher_agent_id="",
            executor_agent_id="",
            reviewer_agent_id="",
        )

        state = coordinator.run_sync("请处理 PDF 报表", max_review_rounds=1)

        self.assertEqual(state.current_status, "done")
        self.assertEqual(review_calls["count"], 2)
        self.assertEqual(state.review_rounds, 1)
        self.assertEqual(state.final_output, '{"summary":"patched","source_page":[3]}')
        self.assertIn("缺少 source_page", str(state.metadata.get("review_feedback") or ""))


if __name__ == "__main__":
    unittest.main()
