#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'ops' / 'project-sync.json'
EXAMPLE_CONFIG = ROOT / 'ops' / 'project-sync.example.json'


class SyncError(RuntimeError):
    pass


def run_git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args],
        cwd=str(path),
        text=True,
        capture_output=True,
        check=check,
    )


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SyncError(f'配置不存在: {path}\n可先复制示例: {EXAMPLE_CONFIG}')
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SyncError('配置顶层必须是对象')
    projects = data.get('projects') or []
    if not isinstance(projects, list) or not projects:
        raise SyncError('配置里至少需要一个 projects 项')
    return data


def iter_projects(config: dict[str, Any], selected: list[str] | None) -> list[dict[str, Any]]:
    projects = config.get('projects') or []
    if not selected:
        return [item for item in projects if isinstance(item, dict)]
    selected_set = set(selected)
    found = [item for item in projects if isinstance(item, dict) and str(item.get('name') or '') in selected_set]
    missing = [name for name in selected if name not in {str(item.get('name') or '') for item in found}]
    if missing:
        raise SyncError(f'配置中不存在这些 project: {", ".join(missing)}')
    return found


def ensure_repo(path: Path) -> None:
    if not path.exists():
        raise SyncError(f'项目目录不存在: {path}')
    if not (path / '.git').exists():
        raise SyncError(f'不是 Git 仓库: {path}')


def branch_exists(path: Path, branch: str) -> bool:
    result = run_git(path, 'rev-parse', '--verify', branch, check=False)
    return result.returncode == 0


def ensure_branch(path: Path, remote: str, branch: str) -> None:
    ensure_repo(path)
    run_git(path, 'fetch', remote, '--prune', check=False)
    if branch_exists(path, branch):
        run_git(path, 'checkout', branch)
        return
    remote_branch = f'{remote}/{branch}'
    if run_git(path, 'rev-parse', '--verify', remote_branch, check=False).returncode == 0:
        run_git(path, 'checkout', '-b', branch, '--track', remote_branch)
        return
    current = run_git(path, 'rev-parse', '--abbrev-ref', 'HEAD').stdout.strip() or 'main'
    run_git(path, 'checkout', '-b', branch, current)


def porcelain_status(path: Path) -> dict[str, Any]:
    branch = run_git(path, 'rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    status_lines = run_git(path, 'status', '--porcelain').stdout.splitlines()
    dirty = bool(status_lines)
    untracked = sum(1 for line in status_lines if line.startswith('??'))
    staged = sum(1 for line in status_lines if line[:2].strip() and not line.startswith('??'))
    ahead = behind = 0
    upstream = run_git(path, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}', check=False)
    upstream_name = upstream.stdout.strip() if upstream.returncode == 0 else ''
    if upstream_name:
        counts = run_git(path, 'rev-list', '--left-right', '--count', f'{branch}...{upstream_name}', check=False).stdout.strip().split()
        if len(counts) == 2:
            ahead = int(counts[0])
            behind = int(counts[1])
    return {
        'path': str(path),
        'branch': branch,
        'dirty': dirty,
        'untracked': untracked,
        'staged_or_modified': staged,
        'ahead': ahead,
        'behind': behind,
        'upstream': upstream_name,
    }


def sync_project(item: dict[str, Any], commit_message: str | None, push: bool) -> dict[str, Any]:
    name = str(item.get('name') or '').strip()
    path = Path(str(item.get('path') or '')).expanduser()
    remote = str(item.get('remote') or 'origin').strip() or 'origin'
    branch = str(item.get('branch') or f'sync/{name}').strip()
    pull_rebase = bool(item.get('pull_rebase', True))

    ensure_branch(path, remote, branch)
    run_git(path, 'fetch', remote, '--prune', check=False)

    before = porcelain_status(path)
    committed = False
    if before['dirty']:
        if not commit_message:
            raise SyncError(f'{name} 工作区有未提交改动，请传 --commit "类型: 中文说明" 后再 sync')
        run_git(path, 'add', '-A')
        commit_result = run_git(path, 'commit', '-m', commit_message, check=False)
        if commit_result.returncode == 0:
            committed = True
        elif 'nothing to commit' not in (commit_result.stdout + commit_result.stderr).lower():
            raise SyncError(f'{name} commit 失败: {(commit_result.stderr or commit_result.stdout).strip()}')

    pull_args = ['pull', '--rebase', remote, branch] if pull_rebase else ['pull', remote, branch]
    pull_result = run_git(path, *pull_args, check=False)
    if pull_result.returncode != 0 and 'couldn\'t find remote ref' not in (pull_result.stderr or '').lower():
        raise SyncError(f'{name} pull 失败: {(pull_result.stderr or pull_result.stdout).strip()}')

    pushed = False
    if push:
        push_result = run_git(path, 'push', '-u', remote, branch, check=False)
        if push_result.returncode != 0:
            raise SyncError(f'{name} push 失败: {(push_result.stderr or push_result.stdout).strip()}')
        pushed = True

    after = porcelain_status(path)
    after.update({'name': name, 'remote': remote, 'committed': committed, 'pushed': pushed})
    return after


def prepare_project(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get('name') or '').strip()
    path = Path(str(item.get('path') or '')).expanduser()
    remote = str(item.get('remote') or 'origin').strip() or 'origin'
    branch = str(item.get('branch') or f'sync/{name}').strip()
    ensure_branch(path, remote, branch)
    status = porcelain_status(path)
    status.update({'name': name, 'remote': remote})
    return status


def print_records(records: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    for item in records:
        print(f"- {item.get('name', '(unknown)')} | branch={item.get('branch')} | dirty={item.get('dirty')} | ahead={item.get('ahead')} | behind={item.get('behind')}")
        print(f"  path={item.get('path')}")
        if item.get('upstream'):
            print(f"  upstream={item.get('upstream')}")
        if 'committed' in item:
            print(f"  committed={item.get('committed')} pushed={item.get('pushed')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='项目共享分支同步工具')
    parser.add_argument('action', choices=['status', 'prepare', 'sync'])
    parser.add_argument('--config', default=str(DEFAULT_CONFIG), help='配置文件路径')
    parser.add_argument('--project', action='append', help='只处理指定 project，可重复传入')
    parser.add_argument('--commit', help='sync 时如有改动则自动提交的 commit message')
    parser.add_argument('--no-push', action='store_true', help='sync 时不执行 push')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(Path(args.config))
    projects = iter_projects(config, args.project)
    records: list[dict[str, Any]] = []

    if args.action == 'status':
        for item in projects:
            path = Path(str(item.get('path') or '')).expanduser()
            ensure_repo(path)
            status = porcelain_status(path)
            status.update({'name': item.get('name'), 'remote': item.get('remote', 'origin')})
            records.append(status)
        print_records(records, args.json)
        return 0

    if args.action == 'prepare':
        for item in projects:
            records.append(prepare_project(item))
        print_records(records, args.json)
        return 0

    if args.action == 'sync':
        for item in projects:
            records.append(sync_project(item, args.commit, push=not args.no_push))
        print_records(records, args.json)
        return 0

    raise SyncError(f'unsupported action: {args.action}')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
