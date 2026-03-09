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

from bot.project_registry import (  # noqa: E402
    REGISTRY_PATH,
    build_project_registry_context,
    load_project_registry,
    render_registry_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='项目注册表工具')
    parser.add_argument('action', choices=['list', 'context', 'sync-workspace'])
    parser.add_argument('--text', help='用于匹配项目的文本')
    parser.add_argument('--workspace', default='/root/.openclaw/workspace', help='OpenClaw workspace 路径')
    parser.add_argument('--json', action='store_true')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.action == 'list':
        payload = load_project_registry(REGISTRY_PATH)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_registry_markdown(REGISTRY_PATH).strip())
        return 0

    if args.action == 'context':
        if not args.text:
            raise SystemExit('context 需要 --text')
        print(build_project_registry_context(args.text, path=REGISTRY_PATH))
        return 0

    if args.action == 'sync-workspace':
        workspace_root = Path(args.workspace).expanduser()
        target = workspace_root / 'memory' / 'project-registry.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_registry_markdown(REGISTRY_PATH), encoding='utf-8')
        if args.json:
            print(json.dumps({'workspace': str(workspace_root), 'target': str(target)}, ensure_ascii=False, indent=2))
        else:
            print(f'已同步到: {target}')
        return 0

    raise SystemExit(f'unsupported action: {args.action}')


if __name__ == '__main__':
    raise SystemExit(main())
