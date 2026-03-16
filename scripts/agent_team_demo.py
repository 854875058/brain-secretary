#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / "qq-bot"
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.agent_team import BaseAgentNode, TeamState, build_default_agent_team  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentTeam state graph demo")
    parser.add_argument(
        "--context",
        default="请帮我把这份乱码的 PDF 财务报表转换为 Markdown，并提取关键指标。",
        help="原始需求",
    )
    parser.add_argument("--memory-query", help="知识库检索关键词；默认等于 context")
    parser.add_argument("--mode", choices=["mock", "openclaw"], default="mock", help="运行模式")
    parser.add_argument("--max-review-rounds", type=int, default=1, help="最多允许的复核打回次数")
    parser.add_argument("--json", action="store_true", help="输出完整状态 JSON")
    return parser


async def mock_research(prompt: str, state: TeamState, agent: BaseAgentNode) -> str:
    return (
        "研究结论：\n"
        "1. 这是 PDF 报表转结构化内容任务。\n"
        "2. 输出要稳定，优先 Markdown 或 JSON。\n"
        "3. 私有规则命中时必须优先遵守。"
    )


async def mock_execute(prompt: str, state: TeamState, agent: BaseAgentNode) -> str:
    feedback = str(state.metadata.get("review_feedback") or "").strip()
    if feedback:
        return (
            "{\n"
            '  "summary": "已根据复核反馈修正交付物",\n'
            '  "format": "markdown",\n'
            f'  "feedback_used": {json.dumps(feedback, ensure_ascii=False)}\n'
            "}"
        )
    return (
        "{\n"
        '  "summary": "已完成 PDF 转 Markdown 的结构化抽取",\n'
        '  "format": "markdown",\n'
        '  "key_metrics": ["revenue", "gross_profit", "net_profit"]\n'
        "}"
    )


async def mock_review(prompt: str, state: TeamState, agent: BaseAgentNode) -> str:
    if state.review_rounds == 0:
        return json.dumps(
            {
                "approved": False,
                "feedback": "请补充字段 source_page，便于后续回溯原始页码。",
                "remember": False,
                "memory_note": "",
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "approved": True,
            "feedback": "通过验收，可以交付。",
            "remember": False,
            "memory_note": "",
        },
        ensure_ascii=False,
    )


def main() -> int:
    args = build_parser().parse_args()

    if args.mode == "mock":
        coordinator = build_default_agent_team(
            researcher_callable=mock_research,
            executor_callable=mock_execute,
            reviewer_callable=mock_review,
        )
    else:
        coordinator = build_default_agent_team()

    state = coordinator.run_sync(
        args.context,
        memory_query=args.memory_query,
        max_review_rounds=args.max_review_rounds,
    )

    if args.json:
        print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("=== AgentTeam 执行完成 ===")
        print(f"session_id: {state.session_id}")
        print(f"steps: {len(state.intermediate_steps)}")
        print(f"errors: {state.errors}")
        print(f"final_output:\n{state.final_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
