#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / 'qq-bot'
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.paperclip_projection import DEFAULT_BOOTSTRAP_HOURS, DEFAULT_LIMIT, sync_projection_once, watch_projection  # noqa: E402
from bot.runtime_paths import OPENCLAW_TRANSCRIPT_DIR  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Paperclip 自动投影守护脚本（把 qq-main 子 agent 协同映射到 Paperclip）')
    parser.add_argument('action', choices=['once', 'watch'])
    parser.add_argument('--transcript-dir', default=str(OPENCLAW_TRANSCRIPT_DIR), help='qq-main transcript 目录')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT, help='最多扫描多少条协同记录')
    parser.add_argument('--bootstrap-hours', type=int, default=DEFAULT_BOOTSTRAP_HOURS, help='首次启动时最多回补最近多少小时的协同记录')
    parser.add_argument('--interval', type=int, default=15, help='watch 模式轮询间隔（秒）')
    parser.add_argument('--dry-run', action='store_true', help='只打印结果，不真正写入 Paperclip / 状态库')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出一次同步结果')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    transcript_dir = args.transcript_dir
    if args.action == 'once':
        payload = asyncio.run(
            sync_projection_once(
                transcript_dir=transcript_dir,
                limit=args.limit,
                bootstrap_hours=args.bootstrap_hours,
                dry_run=args.dry_run,
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload)
        return 0
    asyncio.run(
        watch_projection(
            transcript_dir=transcript_dir,
            limit=args.limit,
            bootstrap_hours=args.bootstrap_hours,
            interval_seconds=args.interval,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
