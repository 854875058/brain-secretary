#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_FILENAME = 'brain-secretary-branch-guard.json'
HOOK_FILENAMES = ['pre-commit', 'pre-push']
ALLOW_ENV = 'BRAIN_SECRETARY_ALLOW_PROTECTED_BRANCH'


class GuardError(RuntimeError):
    pass


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', *args], cwd=str(repo), text=True, capture_output=True, check=check)


def _repo_root(path: str | Path) -> Path:
    repo = Path(path).expanduser().resolve()
    if not repo.exists():
        raise GuardError(f'仓库目录不存在: {repo}')
    git_dir = repo / '.git'
    if not git_dir.exists():
        raise GuardError(f'不是 Git 仓库: {repo}')
    return repo


def _config_path(repo: Path) -> Path:
    return repo / '.git' / CONFIG_FILENAME


def _hook_path(repo: Path, hook_name: str) -> Path:
    return repo / '.git' / 'hooks' / hook_name


def _current_branch(repo: Path) -> str:
    result = _run_git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    return result.stdout.strip()


def _load_config(repo: Path) -> dict[str, Any]:
    path = _config_path(repo)
    if not path.exists():
        return {'protected_branches': ['main']}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise GuardError(f'分支保护配置损坏: {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise GuardError(f'分支保护配置格式错误: {path}')
    branches = payload.get('protected_branches') or ['main']
    payload['protected_branches'] = [str(item).strip() for item in branches if str(item).strip()]
    return payload


def install_guard(repo: Path, protected_branches: list[str]) -> dict[str, Any]:
    branches = [str(item).strip() for item in protected_branches if str(item).strip()]
    if not branches:
        branches = ['main']
    config = {'protected_branches': branches}
    config_path = _config_path(repo)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    script_path = Path(__file__).resolve()
    wrapper = (
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        f'exec /usr/bin/python3 "{script_path}" check --repo "{repo}" --hook "$(basename "$0")"\n'
    )
    for hook_name in HOOK_FILENAMES:
        hook_path = _hook_path(repo, hook_name)
        hook_path.write_text(wrapper, encoding='utf-8')
        hook_path.chmod(0o755)
    return {'repo': str(repo), 'protected_branches': branches, 'config_path': str(config_path)}


def check_guard(repo: Path, hook_name: str | None = None) -> dict[str, Any]:
    config = _load_config(repo)
    branch = _current_branch(repo)
    protected = set(config.get('protected_branches') or [])
    blocked = branch in protected and os.environ.get(ALLOW_ENV, '').strip() not in {'1', 'true', 'yes'}
    payload = {
        'repo': str(repo),
        'branch': branch,
        'protected_branches': sorted(protected),
        'blocked': blocked,
        'hook': hook_name or '',
    }
    if blocked:
        hint = f'当前在受保护分支 `{branch}`，已阻止提交/推送。请切到 work/agent 分支后再继续。'
        payload['message'] = hint
        raise GuardError(json.dumps(payload, ensure_ascii=False))
    payload['message'] = f'当前分支 `{branch}` 可写。'
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Git 受保护分支守卫')
    parser.add_argument('action', choices=['install', 'check'])
    parser.add_argument('--repo', required=True, help='Git 仓库根目录')
    parser.add_argument('--protected', action='append', default=[], help='受保护分支，可重复传入')
    parser.add_argument('--hook', help='当前 hook 名称')
    parser.add_argument('--json', action='store_true')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = _repo_root(args.repo)
    if args.action == 'install':
        payload = install_guard(repo, args.protected)
    else:
        payload = check_guard(repo, hook_name=args.hook)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload.get('message') or json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except GuardError as exc:
        message = str(exc)
        try:
            payload = json.loads(message)
            print(payload.get('message') or message, file=sys.stderr)
        except Exception:
            print(message, file=sys.stderr)
        raise SystemExit(1)
