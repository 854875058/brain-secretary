#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / 'qq-bot'
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.memory_center import build_memory_context, remember_text, render_recent_entries, render_search_results, search_entries  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Bridge 记忆中心工具')
    parser.add_argument('action', choices=['add', 'list', 'search', 'context'])
    parser.add_argument('--text', help='新增记忆文本 / context 查询文本')
    parser.add_argument('--keyword', help='搜索关键词')
    parser.add_argument('--kind', default='remember', help='记忆类型')
    parser.add_argument('--source', default='manual', help='记忆来源')
    parser.add_argument('--user-qq', type=int, default=None)
    parser.add_argument('--group-id', type=int, default=None)
    parser.add_argument('--chat-type', default='private')
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--json', action='store_true')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.action == 'add':
        if not args.text:
            raise SystemExit('add 需要 --text')
        payload = remember_text(
            args.text,
            kind=args.kind,
            source=args.source,
            user_qq=args.user_qq,
            group_id=args.group_id,
            chat_type=args.chat_type,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"已写入记忆: {payload.get('summary')}")
            print(f"- daily: {payload.get('daily_path')}")
            print(f"- topic: {payload.get('topic_path')}")
        return 0

    if args.action == 'list':
        print(render_recent_entries(limit=args.limit))
        return 0

    if args.action == 'search':
        keyword = args.keyword or args.text
        if not keyword:
            raise SystemExit('search 需要 --keyword 或 --text')
        if args.json:
            print(json.dumps(search_entries(keyword, limit=args.limit), ensure_ascii=False, indent=2))
        else:
            print(render_search_results(keyword, limit=args.limit))
        return 0

    if args.action == 'context':
        if not args.text:
            raise SystemExit('context 需要 --text')
        print(build_memory_context(args.text, limit=args.limit))
        return 0

    raise SystemExit(f'unsupported action: {args.action}')


if __name__ == '__main__':
    raise SystemExit(main())
