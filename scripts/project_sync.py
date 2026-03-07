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


def git_ok(path: Path, *args: str) -> bool:
    return run_git(path, *args, check=False).returncode == 0


def git_stdout(path: Path, *args: str) -> str:
    return run_git(path, *args).stdout.strip()


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
    found = [item for item in projects if isinstance(item, dict) and str(item.get('name') or '').strip() in selected_set]
    missing = [name for name in selected if name not in {str(item.get('name') or '').strip() for item in found}]
    if missing:
        raise SyncError(f'配置中不存在这些 project: {", ".join(missing)}')
    return found


def ensure_repo(path: Path) -> None:
    if not path.exists():
        raise SyncError(f'项目目录不存在: {path}')
    if not (path / '.git').exists():
        raise SyncError(f'不是 Git 仓库: {path}')


def current_branch(path: Path) -> str:
    return git_stdout(path, 'rev-parse', '--abbrev-ref', 'HEAD') or '(detached)'


def branch_exists(path: Path, branch: str) -> bool:
    return git_ok(path, 'show-ref', '--verify', '--quiet', f'refs/heads/{branch}')


def remote_branch_exists(path: Path, remote: str, branch: str) -> bool:
    return git_ok(path, 'show-ref', '--verify', '--quiet', f'refs/remotes/{remote}/{branch}')


def ref_exists(path: Path, ref: str) -> bool:
    return git_ok(path, 'rev-parse', '--verify', ref)


def fetch_remote(path: Path, remote: str) -> None:
    result = run_git(path, 'fetch', remote, '--prune', check=False)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or '').strip()
        raise SyncError(f'fetch 失败: {error}')


def working_tree_status(path: Path) -> dict[str, Any]:
    lines = run_git(path, 'status', '--porcelain').stdout.splitlines()
    return {
        'dirty': bool(lines),
        'untracked': sum(1 for line in lines if line.startswith('??')),
        'staged_or_modified': sum(1 for line in lines if line[:2].strip() and not line.startswith('??')),
    }


def ensure_switchable(path: Path, target_branch: str, *, allow_dirty_on_target: bool = False, project_name: str = '') -> None:
    status = working_tree_status(path)
    if not status['dirty']:
        return
    current = current_branch(path)
    if allow_dirty_on_target and current == target_branch:
        return
    label = project_name or str(path)
    raise SyncError(f'{label} 当前工作区有未提交改动，无法切换到 {target_branch}；请先提交、暂存或清理改动')


def resolve_project(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get('name') or '').strip()
    if not name:
        raise SyncError('project.name 不能为空')
    path = Path(str(item.get('path') or '')).expanduser()
    remote = str(item.get('remote') or 'origin').strip() or 'origin'
    stable_branch = str(item.get('stable_branch') or 'main').strip() or 'main'
    work_branch = str(item.get('work_branch') or item.get('branch') or f'work/{name}').strip()
    agent_branch = str(item.get('agent_branch') or f'agent/{name}').strip()
    pull_rebase = bool(item.get('pull_rebase', True))
    mode = 'single' if ('agent_branch' not in item and 'work_branch' not in item and 'branch' in item) else 'dual'
    return {
        'name': name,
        'path': path,
        'remote': remote,
        'stable_branch': stable_branch,
        'work_branch': work_branch,
        'agent_branch': agent_branch,
        'pull_rebase': pull_rebase,
        'mode': mode,
    }


def resolve_existing_ref(path: Path, remote: str, branch: str | None, fallback: list[str] | None = None) -> str | None:
    candidates: list[str] = []
    if branch:
        candidates.extend([branch, f'{remote}/{branch}'])
    for item in fallback or []:
        if item:
            candidates.append(item)
    for ref in candidates:
        if ref_exists(path, ref):
            return ref
    return None


def checkout_or_create_branch(path: Path, remote: str, branch: str, start_ref: str | None = None) -> None:
    if branch_exists(path, branch):
        result = run_git(path, 'checkout', branch, check=False)
        if result.returncode != 0:
            raise SyncError(f'切换到分支 {branch} 失败: {(result.stderr or result.stdout).strip()}')
        return

    if remote_branch_exists(path, remote, branch):
        result = run_git(path, 'checkout', '-b', branch, '--track', f'{remote}/{branch}', check=False)
        if result.returncode != 0:
            raise SyncError(f'创建并跟踪分支 {branch} 失败: {(result.stderr or result.stdout).strip()}')
        return

    base = start_ref or 'HEAD'
    if not ref_exists(path, base):
        raise SyncError(f'创建分支 {branch} 时找不到基线 ref: {base}')
    result = run_git(path, 'checkout', '-b', branch, base, check=False)
    if result.returncode != 0:
        raise SyncError(f'创建分支 {branch} 失败: {(result.stderr or result.stdout).strip()}')


def pull_branch(path: Path, remote: str, branch: str, pull_rebase: bool) -> bool:
    if not remote_branch_exists(path, remote, branch):
        return False
    args = ['pull']
    if pull_rebase:
        args.append('--rebase')
    args.extend([remote, branch])
    result = run_git(path, *args, check=False)
    if result.returncode != 0:
        raise SyncError(f'拉取分支 {branch} 失败: {(result.stderr or result.stdout).strip()}')
    return True


def push_branch(path: Path, remote: str, branch: str) -> bool:
    result = run_git(path, 'push', '-u', remote, branch, check=False)
    if result.returncode != 0:
        raise SyncError(f'推送分支 {branch} 失败: {(result.stderr or result.stdout).strip()}')
    return True


def commit_current_branch(path: Path, project_name: str, commit_message: str | None) -> bool:
    status = working_tree_status(path)
    if not status['dirty']:
        return False
    if not commit_message:
        raise SyncError(f'{project_name} 当前分支有未提交改动，请传 --commit "类型: 中文说明" 后再 sync')
    run_git(path, 'add', '-A')
    result = run_git(path, 'commit', '-m', commit_message, check=False)
    if result.returncode == 0:
        return True
    combined = (result.stdout + result.stderr).lower()
    if 'nothing to commit' in combined:
        return False
    raise SyncError(f'{project_name} commit 失败: {(result.stderr or result.stdout).strip()}')


def divergence(path: Path, left_ref: str | None, right_ref: str | None) -> dict[str, Any] | None:
    if not left_ref or not right_ref:
        return None
    if not ref_exists(path, left_ref) or not ref_exists(path, right_ref):
        return None
    result = run_git(path, 'rev-list', '--left-right', '--count', f'{left_ref}...{right_ref}', check=False)
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None
    return {
        'left_ref': left_ref,
        'right_ref': right_ref,
        'left_only': int(parts[0]),
        'right_only': int(parts[1]),
    }


def branch_remote_status(path: Path, remote: str, branch: str) -> dict[str, Any]:
    local_exists = branch_exists(path, branch)
    remote_exists = remote_branch_exists(path, remote, branch)
    local_ref = branch if local_exists else None
    remote_ref = f'{remote}/{branch}' if remote_exists else None
    relation = divergence(path, local_ref, remote_ref) if local_exists and remote_exists else None
    return {
        'branch': branch,
        'local_exists': local_exists,
        'remote_exists': remote_exists,
        'local_ref': local_ref,
        'remote_ref': remote_ref,
        'ahead': relation['left_only'] if relation else 0,
        'behind': relation['right_only'] if relation else 0,
        'current': current_branch(path) == branch,
    }


def work_base_ref(project: dict[str, Any]) -> str:
    path = project['path']
    remote = project['remote']
    stable = project['stable_branch']
    ref = resolve_existing_ref(path, remote, stable, fallback=['HEAD'])
    if ref is None:
        raise SyncError(f"{project['name']} 找不到稳定基线分支: {stable}")
    return ref


def agent_base_ref(project: dict[str, Any]) -> str:
    path = project['path']
    remote = project['remote']
    ref = resolve_existing_ref(path, remote, project['work_branch'], fallback=[work_base_ref(project)])
    if ref is None:
        raise SyncError(f"{project['name']} 找不到工作分支基线: {project['work_branch']}")
    return ref


def prepare_work(project: dict[str, Any]) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    ensure_switchable(path, project['work_branch'], project_name=project['name'])
    fetch_remote(path, project['remote'])
    checkout_or_create_branch(path, project['remote'], project['work_branch'], start_ref=work_base_ref(project))
    pull_branch(path, project['remote'], project['work_branch'], project['pull_rebase'])
    return build_project_status(project, refresh=False)


def update_work(project: dict[str, Any]) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    ensure_switchable(path, project['work_branch'], allow_dirty_on_target=True, project_name=project['name'])
    fetch_remote(path, project['remote'])
    checkout_or_create_branch(path, project['remote'], project['work_branch'], start_ref=work_base_ref(project))
    status = working_tree_status(path)
    skipped = False
    reason = ''
    if status['dirty']:
        skipped = True
        reason = 'worktree_dirty'
    else:
        pull_branch(path, project['remote'], project['work_branch'], project['pull_rebase'])
    record = build_project_status(project, refresh=False)
    record['skipped'] = skipped
    record['skip_reason'] = reason
    return record


def sync_work(project: dict[str, Any], commit_message: str | None, push: bool) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    ensure_switchable(path, project['work_branch'], allow_dirty_on_target=True, project_name=project['name'])
    fetch_remote(path, project['remote'])
    checkout_or_create_branch(path, project['remote'], project['work_branch'], start_ref=work_base_ref(project))
    committed = commit_current_branch(path, project['name'], commit_message)
    pull_branch(path, project['remote'], project['work_branch'], project['pull_rebase'])
    pushed = push_branch(path, project['remote'], project['work_branch']) if push else False
    record = build_project_status(project, refresh=False)
    record['committed'] = committed
    record['pushed'] = pushed
    return record


def merge_into_current(path: Path, source_ref: str, *, message: str | None = None, no_ff: bool = False) -> bool:
    relation = divergence(path, source_ref, 'HEAD')
    if relation is None or relation['left_only'] <= 0:
        return False
    args = ['merge']
    if no_ff:
        args.append('--no-ff')
    if message:
        args.extend(['-m', message])
    else:
        args.append('--no-edit')
    args.append(source_ref)
    result = run_git(path, *args, check=False)
    if result.returncode == 0:
        return True
    run_git(path, 'merge', '--abort', check=False)
    raise SyncError(f'合并 {source_ref} 到当前分支失败: {(result.stderr or result.stdout).strip()}')


def prepare_agent(project: dict[str, Any]) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    prepare_work(project)
    ensure_switchable(path, project['agent_branch'], project_name=project['name'])
    fetch_remote(path, project['remote'])
    checkout_or_create_branch(path, project['remote'], project['agent_branch'], start_ref=agent_base_ref(project))
    if working_tree_status(path)['dirty']:
        raise SyncError(f"{project['name']} agent 分支存在未提交改动，先清理后再 prepare-agent")
    pull_branch(path, project['remote'], project['agent_branch'], project['pull_rebase'])
    merged = merge_into_current(path, project['work_branch'])
    record = build_project_status(project, refresh=False)
    record['merged_work_into_agent'] = merged
    return record


def sync_agent(project: dict[str, Any], commit_message: str | None, push: bool) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    ensure_switchable(path, project['agent_branch'], allow_dirty_on_target=True, project_name=project['name'])
    fetch_remote(path, project['remote'])
    checkout_or_create_branch(path, project['remote'], project['agent_branch'], start_ref=agent_base_ref(project))
    committed = commit_current_branch(path, project['name'], commit_message)
    pull_branch(path, project['remote'], project['agent_branch'], project['pull_rebase'])
    pushed = push_branch(path, project['remote'], project['agent_branch']) if push else False
    record = build_project_status(project, refresh=False)
    record['committed'] = committed
    record['pushed'] = pushed
    return record


def review_agent(project: dict[str, Any]) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    fetch_remote(path, project['remote'])
    work_ref = resolve_existing_ref(path, project['remote'], project['work_branch'])
    agent_ref = resolve_existing_ref(path, project['remote'], project['agent_branch'])
    if work_ref is None:
        raise SyncError(f"{project['name']} 找不到工作分支: {project['work_branch']}")
    if agent_ref is None:
        raise SyncError(f"{project['name']} 找不到 agent 分支: {project['agent_branch']}")

    relation = divergence(path, agent_ref, work_ref)
    diff_stat = run_git(path, 'diff', '--stat', f'{work_ref}..{agent_ref}', check=False).stdout.strip()
    agent_commits = run_git(path, 'log', '--oneline', '--max-count', '12', f'{work_ref}..{agent_ref}', check=False).stdout.strip().splitlines()
    work_commits = run_git(path, 'log', '--oneline', '--max-count', '12', f'{agent_ref}..{work_ref}', check=False).stdout.strip().splitlines()
    record = build_project_status(project, refresh=False)
    record.update({
        'review': {
            'work_ref': work_ref,
            'agent_ref': agent_ref,
            'agent_only_commits': agent_commits,
            'work_only_commits': work_commits,
            'diff_stat': diff_stat,
            'agent_vs_work': relation,
        }
    })
    return record


def promote_agent(project: dict[str, Any], push: bool, commit_message: str | None) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    ensure_switchable(path, project['work_branch'], project_name=project['name'])
    fetch_remote(path, project['remote'])
    agent_ref = resolve_existing_ref(path, project['remote'], project['agent_branch'])
    if agent_ref is None:
        raise SyncError(f"{project['name']} 找不到 agent 分支: {project['agent_branch']}")
    checkout_or_create_branch(path, project['remote'], project['work_branch'], start_ref=work_base_ref(project))
    if working_tree_status(path)['dirty']:
        raise SyncError(f"{project['name']} work 分支存在未提交改动，先清理后再 promote-agent")
    pull_branch(path, project['remote'], project['work_branch'], project['pull_rebase'])
    merge_message = commit_message or f"merge: 合并 {project['agent_branch']} 到 {project['work_branch']}"
    merged = merge_into_current(path, agent_ref, message=merge_message, no_ff=True)
    pushed = push_branch(path, project['remote'], project['work_branch']) if push and merged else False
    record = build_project_status(project, refresh=False)
    record['merged_agent_into_work'] = merged
    record['pushed'] = pushed
    return record


def build_project_status(project: dict[str, Any], *, refresh: bool = True) -> dict[str, Any]:
    path = project['path']
    ensure_repo(path)
    if refresh:
        fetch_remote(path, project['remote'])

    current = current_branch(path)
    tree = working_tree_status(path)
    work = branch_remote_status(path, project['remote'], project['work_branch'])
    agent = branch_remote_status(path, project['remote'], project['agent_branch'])
    stable_ref = resolve_existing_ref(path, project['remote'], project['stable_branch'])
    work_ref = resolve_existing_ref(path, project['remote'], project['work_branch'])
    agent_ref = resolve_existing_ref(path, project['remote'], project['agent_branch'])
    return {
        'name': project['name'],
        'mode': project['mode'],
        'path': str(path),
        'remote': project['remote'],
        'stable_branch': project['stable_branch'],
        'work_branch': project['work_branch'],
        'agent_branch': project['agent_branch'],
        'current_branch': current,
        'dirty': tree['dirty'],
        'untracked': tree['untracked'],
        'staged_or_modified': tree['staged_or_modified'],
        'work': work,
        'agent': agent,
        'work_vs_stable': divergence(path, work_ref, stable_ref),
        'agent_vs_work': divergence(path, agent_ref, work_ref),
    }


def print_records(records: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return

    for item in records:
        print(f"- {item['name']} | current={item['current_branch']} | dirty={item['dirty']}")
        print(f"  path={item['path']}")
        print(f"  stable={item['stable_branch']} | work={item['work_branch']} | agent={item['agent_branch']}")
        work = item.get('work') or {}
        agent = item.get('agent') or {}
        print(
            f"  work: local={work.get('local_exists')} remote={work.get('remote_exists')} ahead={work.get('ahead')} behind={work.get('behind')}"
        )
        print(
            f"  agent: local={agent.get('local_exists')} remote={agent.get('remote_exists')} ahead={agent.get('ahead')} behind={agent.get('behind')}"
        )
        work_vs_stable = item.get('work_vs_stable')
        if work_vs_stable:
            print(
                f"  work_vs_stable: work_only={work_vs_stable['left_only']} stable_only={work_vs_stable['right_only']}"
            )
        agent_vs_work = item.get('agent_vs_work')
        if agent_vs_work:
            print(
                f"  agent_vs_work: agent_only={agent_vs_work['left_only']} work_only={agent_vs_work['right_only']}"
            )
        if 'committed' in item:
            print(f"  committed={item.get('committed')} pushed={item.get('pushed')}")
        if 'skipped' in item:
            print(f"  skipped={item.get('skipped')} reason={item.get('skip_reason') or ''}")
        if 'merged_work_into_agent' in item:
            print(f"  merged_work_into_agent={item.get('merged_work_into_agent')}")
        if 'merged_agent_into_work' in item:
            print(f"  merged_agent_into_work={item.get('merged_agent_into_work')} pushed={item.get('pushed')}")
        review = item.get('review')
        if isinstance(review, dict):
            print('  agent_only_commits:')
            for line in review.get('agent_only_commits') or []:
                print(f'    {line}')
            print('  work_only_commits:')
            for line in review.get('work_only_commits') or []:
                print(f'    {line}')
            diff_stat = str(review.get('diff_stat') or '').strip()
            if diff_stat:
                print('  diff_stat:')
                for line in diff_stat.splitlines():
                    print(f'    {line}')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='项目双轨分支同步工具')
    parser.add_argument(
        'action',
        choices=['status', 'prepare', 'sync', 'update-work', 'prepare-work', 'sync-work', 'prepare-agent', 'sync-agent', 'review-agent', 'promote-agent'],
    )
    parser.add_argument('--config', default=str(DEFAULT_CONFIG), help='配置文件路径')
    parser.add_argument('--project', action='append', help='只处理指定 project，可重复传入')
    parser.add_argument('--commit', help='sync-* 提交说明，或 promote-agent 时的 merge commit message')
    parser.add_argument('--no-push', action='store_true', help='sync-* 时不执行 push')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(Path(args.config))
    raw_projects = iter_projects(config, args.project)
    projects = [resolve_project(item) for item in raw_projects]
    records: list[dict[str, Any]] = []
    action = args.action
    if action == 'prepare':
        action = 'prepare-work'
    elif action == 'sync':
        action = 'sync-work'

    if action == 'status':
        records = [build_project_status(project) for project in projects]
    elif action == 'prepare-work':
        records = [prepare_work(project) for project in projects]
    elif action == 'update-work':
        records = [update_work(project) for project in projects]
    elif action == 'sync-work':
        records = [sync_work(project, args.commit, push=not args.no_push) for project in projects]
    elif action == 'prepare-agent':
        records = [prepare_agent(project) for project in projects]
    elif action == 'sync-agent':
        records = [sync_agent(project, args.commit, push=not args.no_push) for project in projects]
    elif action == 'review-agent':
        records = [review_agent(project) for project in projects]
    elif action == 'promote-agent':
        records = [promote_agent(project, push=not args.no_push, commit_message=args.commit) for project in projects]
    else:
        raise SyncError(f'unsupported action: {action}')

    print_records(records, args.json)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
