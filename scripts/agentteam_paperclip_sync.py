#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / "qq-bot"
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.agentteam_client import AgentTeamClient, AgentTeamError  # noqa: E402
from bot.agentteam_paperclip import DEFAULT_INTERVAL_SECONDS, DEFAULT_TASK_LIMIT, sync_agentteam_to_paperclip  # noqa: E402
from bot.paperclip_client import PaperclipClient, PaperclipError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把外部 AgentTeam 状态 API 投影到 Paperclip")
    parser.add_argument("action", choices=["once", "watch"])
    parser.add_argument("--task-limit", type=int, default=DEFAULT_TASK_LIMIT, help="最多同步多少个任务 issue")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS, help="watch 模式轮询间隔（秒）")
    parser.add_argument("--dry-run", action="store_true", help="只输出结果，不真正写入 Paperclip")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def _print(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload)


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

    agentteam = AgentTeamClient.from_config({})
    paperclip = PaperclipClient.from_config({})

    if args.action == "once":
        payload = sync_agentteam_to_paperclip(
            agentteam_client=agentteam,
            paperclip_client=paperclip,
            task_limit=args.task_limit,
            dry_run=args.dry_run,
        )
        _print(payload, args.json)
        return 0

    while True:
        payload = sync_agentteam_to_paperclip(
            agentteam_client=agentteam,
            paperclip_client=paperclip,
            task_limit=args.task_limit,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        time.sleep(max(5, int(args.interval)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AgentTeamError, PaperclipError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
