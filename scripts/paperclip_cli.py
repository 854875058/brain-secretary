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

from bot.paperclip_client import PaperclipClient, PaperclipError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Paperclip CLI（供 OpenClaw / QQ / 运维脚本调用）')
    parser.add_argument('action', choices=['status', 'companies', 'agents', 'issues', 'issue', 'create', 'wake', 'run'])
    parser.add_argument('--issue-id', help='issue id / identifier')
    parser.add_argument('--title', help='issue 标题')
    parser.add_argument('--description', help='issue 描述')
    parser.add_argument('--agent', help='agent id / name / title / shortname')
    parser.add_argument('--status', help='issues 过滤状态')
    parser.add_argument('--query', help='issues 搜索关键词')
    parser.add_argument('--reason', help='wake 理由')
    parser.add_argument('--json', action='store_true')
    return parser


def _print(payload, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload)


def main() -> int:
    args = build_parser().parse_args()
    client = PaperclipClient.from_config({})

    if args.action == 'status':
        payload = {
            'summary': client.summary(),
            'health': client.health() if client.configured else None,
        }
        _print(payload, args.json)
        return 0

    if args.action == 'companies':
        _print(client.list_companies(), args.json)
        return 0

    if args.action == 'agents':
        _print(client.list_agents(), args.json)
        return 0

    if args.action == 'issues':
        _print(client.list_issues(status=args.status, q=args.query), args.json)
        return 0

    if args.action == 'issue':
        if not args.issue_id:
            raise SystemExit('issue 需要 --issue-id')
        _print(client.get_issue(args.issue_id), args.json)
        return 0

    if args.action == 'create':
        if not args.title:
            raise SystemExit('create 需要 --title')
        assignee_id = None
        if args.agent:
            assignee = client.resolve_agent_ref(args.agent)
            assignee_id = str(assignee.get('id') or '').strip() or None
        payload = client.create_issue(title=args.title, description=args.description, assignee_agent_id=assignee_id)
        _print(payload, args.json)
        return 0

    if args.action == 'wake':
        if not args.agent:
            raise SystemExit('wake 需要 --agent')
        assignee = client.resolve_agent_ref(args.agent)
        assignee_id = str(assignee.get('id') or '').strip()
        payload = client.wake_agent(assignee_id, reason=args.reason) or {}
        _print(payload, args.json)
        return 0

    if args.action == 'run':
        if not args.agent or not args.title:
            raise SystemExit('run 需要 --agent 和 --title')
        assignee = client.resolve_agent_ref(args.agent)
        assignee_id = str(assignee.get('id') or '').strip()
        issue = client.create_issue(
            title=args.title,
            description=args.description,
            assignee_agent_id=assignee_id,
            status='todo',
        )
        payload = {'issue': issue, 'wake': {'status': 'queued_via_issue_assignment'}}
        _print(payload, args.json)
        return 0

    raise SystemExit(f'unsupported action: {args.action}')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except PaperclipError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
