#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / 'qq-bot'
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.openclaw_client import OpenClawClient, OpenClawError  # noqa: E402
from bot.project_registry import load_project_registry  # noqa: E402
from bot.task_db import get_bridge_state_value, init_db, set_bridge_state_value  # noqa: E402

logger = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = ROOT / 'ops' / 'auto-evolve.json'
DEFAULT_SYNC_CONFIG_PATH = ROOT / 'ops' / 'project-sync.json'
STATE_KEY = 'project_auto_evolve_v1'
DEFAULT_AGENT_TIMEOUT_SECONDS = 3600
DEFAULT_SESSION_MODE = 'fresh'
DEFAULT_AUTO_EVOLVE_AGENT_ID = 'auto-evolve-main'
SYNC_PREP_ACTIONS = ['repair-boundaries', 'prepare-agent', 'sync-work', 'sync-agent']
WATCHDOG_BRAIN_AGENT_ID = 'qq-main'


class AutoEvolveError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except Exception:
        return None


def _run_command(cmd: list[str], *, cwd: Path | None = None, check: bool = True, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, capture_output=True, check=check, timeout=timeout)


def _run_json(cmd: list[str], *, cwd: Path | None = None, timeout: int = 1800) -> Any:
    result = _run_command(cmd, cwd=cwd, timeout=timeout)
    output = (result.stdout or '').strip()
    return json.loads(output) if output else None


def _github_repo_spec(repo_url: str) -> str:
    text = str(repo_url or '').strip().rstrip('/')
    marker = 'github.com/'
    if marker not in text:
        raise AutoEvolveError(f'不支持的 GitHub 地址: {repo_url}')
    return text.split(marker, 1)[1]


def _normalize_session_mode(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'fixed', 'reuse', 'sticky'}:
        return 'fixed'
    return DEFAULT_SESSION_MODE


def _resolve_cycle_session_id(project_cfg: dict[str, Any], cycle_started_at: datetime) -> str:
    base = str(project_cfg.get('session_id') or f"auto-evolve:{project_cfg['name']}").strip() or f"auto-evolve:{project_cfg['name']}"
    if _normalize_session_mode(project_cfg.get('session_mode')) == 'fixed':
        return base
    return f"{base}:{cycle_started_at.strftime('%Y%m%dT%H%M%S')}"


def _load_auto_config(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AutoEvolveError(f'自动进化配置不存在: {path}')
    payload = json.loads(path.read_text(encoding='utf-8'))
    projects = payload.get('projects') if isinstance(payload, dict) else None
    if not isinstance(projects, list) or not projects:
        raise AutoEvolveError('自动进化配置里至少需要一个 projects 项')
    normalized: list[dict[str, Any]] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        normalized.append(
            {
                'name': name,
                'enabled': bool(item.get('enabled', True)),
                'registry_project': str(item.get('registry_project') or name).strip() or name,
                'sync_project': str(item.get('sync_project') or name).strip() or name,
                'agent_id': str(item.get('agent_id') or DEFAULT_AUTO_EVOLVE_AGENT_ID).strip() or DEFAULT_AUTO_EVOLVE_AGENT_ID,
                'session_id': str(item.get('session_id') or f'auto-evolve:{name}').strip(),
                'session_mode': _normalize_session_mode(item.get('session_mode')),
                'interval_minutes': max(5, int(item.get('interval_minutes') or 45)),
                'timeout_seconds': max(120, int(item.get('timeout_seconds') or DEFAULT_AGENT_TIMEOUT_SECONDS)),
                'thinking': str(item.get('thinking') or 'low').strip() or 'low',
                'protected_branches': [str(branch).strip() for branch in (item.get('protected_branches') or ['main']) if str(branch).strip()],
                'goal': str(item.get('goal') or '').strip(),
                'validation_hint': str(item.get('validation_hint') or '').strip(),
                'commit_prefix': str(item.get('commit_prefix') or 'chore: 夜间自动进化').strip(),
            }
        )
    if not normalized:
        raise AutoEvolveError('自动进化配置没有有效 project')
    return normalized


def _load_project_sync_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise AutoEvolveError(f'项目双轨配置不存在: {path}')
    payload = json.loads(path.read_text(encoding='utf-8'))
    projects = payload.get('projects') if isinstance(payload, dict) else None
    if not isinstance(projects, list):
        raise AutoEvolveError(f'项目双轨配置格式错误: {path}')
    mapping: dict[str, dict[str, Any]] = {}
    for item in projects:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        mapping[name] = item
    return mapping


def _load_registry_map() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in load_project_registry():
        name = str(item.get('name') or '').strip()
        if name:
            mapping[name] = item
        for alias in item.get('aliases') or []:
            normalized = str(alias).strip()
            if normalized:
                mapping.setdefault(normalized, item)
    return mapping


def _clean_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {'version': 1, 'projects': {}}
    cleaned = dict(raw)
    cleaned.pop('_db_updated_at', None)
    cleaned.setdefault('version', 1)
    cleaned.setdefault('projects', {})
    return cleaned



def _unique_strings(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item or '').strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _powershell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_openclaw_json(args: list[str], *, timeout: int = 180) -> Any:
    if os.name == 'nt':
        command = 'openclaw ' + ' '.join(_powershell_quote(str(item)) for item in args)
        result = subprocess.run(
            [r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe', '-Command', command],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
            timeout=timeout,
        )
    else:
        result = subprocess.run(
            ['openclaw', *[str(item) for item in args]],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
            timeout=timeout,
        )
    output = (result.stdout or '').strip()
    return json.loads(output) if output else None


def _session_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ('sessions', 'items', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _main_session_snapshot(agent_id: str, *, timeout: int = 120) -> dict[str, Any]:
    target_key = f'agent:{agent_id}:main'
    try:
        payload = _run_openclaw_json(['sessions', '--agent', agent_id, '--json'], timeout=timeout)
    except Exception as exc:
        return {
            'agent_id': agent_id,
            'main_key': target_key,
            'present': False,
            'session_count': 0,
            'error': str(exc),
        }
    items = _session_items(payload)
    matched = next((item for item in items if str(item.get('key') or '').strip() == target_key), None)
    return {
        'agent_id': agent_id,
        'main_key': target_key,
        'present': bool(matched),
        'session_count': len(items),
        'key': str((matched or {}).get('key') or '').strip(),
        'session_id': str((matched or {}).get('sessionId') or '').strip(),
        'updated_at': (matched or {}).get('updatedAt') or (matched or {}).get('lastUpdatedAt'),
        'aborted_last_run': bool((matched or {}).get('abortedLastRun')),
        'total_tokens': (matched or {}).get('totalTokens'),
    }


def _session_matches_prefix(session_id: str, prefix: str) -> bool:
    normalized_session = str(session_id or '').strip()
    normalized_prefix = str(prefix or '').strip()
    return bool(normalized_session and normalized_prefix and (normalized_session == normalized_prefix or normalized_session.startswith(f'{normalized_prefix}:')))


def _build_branch_guard_preview(repo_path: Path, protected_branches: list[str]) -> dict[str, Any]:
    branches = [str(item).strip() for item in (protected_branches or ['main']) if str(item).strip()] or ['main']
    return {
        'repo': str(repo_path),
        'protected_branches': branches,
        'config_path': str(repo_path / '.git' / 'brain-secretary-branch-guard.json'),
        'repo_exists': repo_path.exists(),
        'git_exists': (repo_path / '.git').exists(),
        'will_install': True,
    }


def _build_sync_preview(project_name: str, sync_config: Path) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for action in SYNC_PREP_ACTIONS:
        cmd = [
            sys.executable,
            str(ROOT / 'scripts' / 'project_sync.py'),
            action,
            '--config',
            str(sync_config),
            '--project',
            project_name,
            '--json',
        ]
        previews.append({'action': action, 'command': shlex.join(cmd)})
    return previews


def _build_watchdog_report(projects: list[dict[str, Any]]) -> dict[str, Any]:
    enabled_projects = [item for item in projects if item.get('enabled', True)]
    auto_agent_ids = _unique_strings([item.get('agent_id') for item in enabled_projects])
    session_prefixes = _unique_strings([item.get('session_id') for item in enabled_projects])
    qq_main_snapshot = _main_session_snapshot(WATCHDOG_BRAIN_AGENT_ID)
    auto_snapshots = [_main_session_snapshot(agent_id) for agent_id in auto_agent_ids]
    violations: list[dict[str, Any]] = []

    for item in enabled_projects:
        if str(item.get('agent_id') or '').strip() == WATCHDOG_BRAIN_AGENT_ID:
            violations.append(
                {
                    'type': 'config_drift',
                    'project': item.get('name'),
                    'message': '自动进化项目仍绑定到 qq-main，会污染 QQ 主会话。',
                }
            )

    if qq_main_snapshot.get('error'):
        violations.append(
            {
                'type': 'watchdog_probe_failed',
                'agent_id': WATCHDOG_BRAIN_AGENT_ID,
                'message': str(qq_main_snapshot['error']),
            }
        )
    else:
        qq_main_session_id = str(qq_main_snapshot.get('session_id') or '').strip()
        if any(_session_matches_prefix(qq_main_session_id, prefix) for prefix in session_prefixes):
            violations.append(
                {
                    'type': 'session_pollution',
                    'agent_id': WATCHDOG_BRAIN_AGENT_ID,
                    'session_id': qq_main_session_id,
                    'message': '检测到 qq-main 主会话被自动进化 session 前缀占用，已触发熔断。',
                }
            )

    for snapshot in auto_snapshots:
        if snapshot.get('error'):
            violations.append(
                {
                    'type': 'watchdog_probe_failed',
                    'agent_id': snapshot.get('agent_id'),
                    'message': str(snapshot['error']),
                }
            )

    status = 'ok' if not violations else 'tripped'
    return {
        'checked_at': _now_iso(),
        'status': status,
        'circuit_breaker_open': status != 'ok',
        'brain_agent_id': WATCHDOG_BRAIN_AGENT_ID,
        'expected_auto_evolve_agents': auto_agent_ids,
        'expected_session_prefixes': session_prefixes,
        'qq_main': qq_main_snapshot,
        'auto_evolve_agents': auto_snapshots,
        'violations': violations,
        'message': 'watchdog ok' if status == 'ok' else 'watchdog tripped: detected session pollution or config drift',
    }


def _merge_watchdog_state(state: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    watchdog_state = dict(state.get('watchdog') or {})
    watchdog_state['last_checked_at'] = report.get('checked_at')
    watchdog_state['last_status'] = report.get('status')
    watchdog_state['circuit_breaker_open'] = bool(report.get('circuit_breaker_open'))
    watchdog_state['last_report'] = report
    if report.get('status') == 'ok':
        watchdog_state['last_ok_at'] = report.get('checked_at')
    else:
        watchdog_state['last_tripped_at'] = report.get('checked_at')
    state['watchdog'] = watchdog_state
    return state


def _ensure_project_checkout(sync_item: dict[str, Any], registry_item: dict[str, Any]) -> Path:
    repo_path = Path(str(sync_item.get('path') or '')).expanduser()
    if (repo_path / '.git').exists():
        return repo_path
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    repo_url = str(registry_item.get('repo_url') or '').strip()
    if not repo_url:
        raise AutoEvolveError(f"{sync_item.get('name')} 缺少 repo_url，无法自动克隆")
    gh_spec = _github_repo_spec(repo_url)
    logger.info('项目不存在，开始克隆: %s -> %s', gh_spec, repo_path)
    try:
        _run_command(['gh', 'repo', 'clone', gh_spec, str(repo_path)], timeout=3600)
    except Exception:
        _run_command(['git', 'clone', repo_url, str(repo_path)], timeout=3600)
    return repo_path


def _install_branch_guard(repo_path: Path, protected_branches: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / 'scripts' / 'git_branch_guard.py'), 'install', '--repo', str(repo_path), '--json']
    for branch in protected_branches:
        cmd.extend(['--protected', branch])
    return _run_json(cmd, timeout=300) or {}


def _project_sync(action: str, project_name: str, sync_config: Path, extra_args: list[str] | None = None, timeout: int = 3600) -> Any:
    cmd = [sys.executable, str(ROOT / 'scripts' / 'project_sync.py'), action, '--config', str(sync_config), '--project', project_name, '--json']
    if extra_args:
        cmd.extend(extra_args)
    return _run_json(cmd, timeout=timeout)


def _build_cycle_prompt(project_cfg: dict[str, Any], sync_item: dict[str, Any], registry_item: dict[str, Any], previous_state: dict[str, Any] | None = None) -> str:
    repo_path = str(sync_item.get('path') or '').strip()
    project_name = str(registry_item.get('name') or project_cfg['name']).strip()
    repo_url = str(registry_item.get('repo_url') or '').strip()
    work_branch = str(sync_item.get('work_branch') or '').strip()
    agent_branch = str(sync_item.get('agent_branch') or '').strip()
    stable_branch = str(sync_item.get('stable_branch') or 'main').strip() or 'main'
    goal = str(project_cfg.get('goal') or '').strip() or '持续寻找高价值、低风险、可验证的小步改进。'
    validation_hint = str(project_cfg.get('validation_hint') or '').strip()
    prior_summary = str((previous_state or {}).get('last_summary') or '').strip()
    prior_outcome = str((previous_state or {}).get('last_outcome') or '').strip()
    prior_commit = str((previous_state or {}).get('last_commit') or '').strip()

    lines = [
        '这是一次【24 小时自动进化守护周期】。',
        '你现在不是等用户下命令，而是在无人值守模式下，主动为项目寻找可落地的小步改进。',
        '',
        f'项目: {project_name}',
        f'仓库: {repo_url}',
        f'本地仓库路径: {repo_path}',
        f'稳定分支(禁止提交/推送): {stable_branch}',
        f'白天工作分支: {work_branch}',
        f'夜间 agent 分支: {agent_branch}',
        '',
        '硬约束:',
        f'- 绝对不要向 `{stable_branch}` 提交、合并或推送；所有实际改动只允许落在 `{agent_branch}`。',
        '- 遇到缺依赖、缺测试工具、仓库未克隆、默认分支未确认、缺 `rg` 等可恢复阻塞时，先自己补环境、换工具、继续推进，不要把这些先甩给用户。',
        '- 这轮必须按“大脑 -> 技术号 -> 验收号 -> 若有问题再打回技术号”的闭环推进，至少完成一轮真实复核。',
        '- 如果验收指出问题、测试失败或实现不完整，大脑要自动带着 blocker 再派技术号修，不要把返工交给用户。',
        '- 只有在确实缺账号授权、验证码、业务取舍或用户专属偏好时，才允许停止并对外报阻塞。',
        '',
        '本轮目标:',
        f'- {goal}',
        '- 主动自己找活：优先处理明确 bug、测试失败、工程稳定性问题、依赖/脚本问题、低风险文档/配置改进。',
        '- 优先选择 1 个高价值、低风险、可验证的改动；不要一轮铺太大。',
        '- 如果这轮已经完成实现，但补依赖 / 跑 pytest / 前端 build 会明显拖长时长，优先拆成“实现回合”和“验证回合”，不要为了等全量验证把整轮跑到超时。',
    ]
    if validation_hint:
        lines.extend(['', '验证要求:', f'- {validation_hint}'])
    if prior_summary or prior_outcome or prior_commit:
        lines.extend([
            '',
            '上一轮上下文:',
            f'- 上轮结论: {prior_outcome or "(无)"}',
            f'- 上轮摘要: {prior_summary or "(无)"}',
            f'- 上轮 commit: {prior_commit or "(无)"}',
            '- 这轮如果还有未解决项，优先接着推进，不要从头乱找。',
        ])
    lines.extend([
        '',
        '最终输出要求（中文）:',
        '1. 先写本轮找到的活和最终结论。',
        '2. 写清技术号做了什么、验收号发现了什么、是否发生返工。',
        '3. 写清改动文件、验证动作、剩余风险。',
        '4. 如果有实际提交，写 commit hash、当前分支、push 结果。',
        '5. 如果这轮没有安全改动可提交，也要给出下一轮优先项，别空转。',
    ])
    return '\n'.join(lines).strip()


def _extract_commit_hash(reply_text: str) -> str | None:
    for token in str(reply_text or '').split():
        cleaned = token.strip('`[]()<>.,;:')
        if len(cleaned) >= 7 and len(cleaned) <= 40 and all(char in '0123456789abcdef' for char in cleaned.lower()):
            return cleaned
    return None


async def run_project_cycle(
    project_cfg: dict[str, Any],
    *,
    sync_config: Path,
    dry_run: bool = False,
    watchdog_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sync_map = _load_project_sync_map(sync_config)
    sync_item = sync_map.get(project_cfg['sync_project'])
    if not sync_item:
        raise AutoEvolveError(f"项目双轨配置里找不到 {project_cfg['sync_project']}")
    registry_map = _load_registry_map()
    registry_item = registry_map.get(project_cfg['registry_project'])
    if not registry_item:
        raise AutoEvolveError(f"项目注册表里找不到 {project_cfg['registry_project']}")

    repo_path = Path(str(sync_item.get('path') or '')).expanduser()
    cycle_started_at = datetime.now().astimezone()
    effective_session_id = _resolve_cycle_session_id(project_cfg, cycle_started_at)
    result: dict[str, Any] = {
        'project': project_cfg['name'],
        'repo_path': str(repo_path),
        'agent_id': project_cfg['agent_id'],
        'session_id': effective_session_id,
        'session_id_base': project_cfg['session_id'],
        'session_mode': project_cfg.get('session_mode') or DEFAULT_SESSION_MODE,
        'dry_run': dry_run,
        'started_at': cycle_started_at.isoformat(),
    }
    if watchdog_report is not None:
        result['watchdog'] = watchdog_report

    if dry_run:
        result['guard'] = _build_branch_guard_preview(repo_path, project_cfg.get('protected_branches') or ['main'])
        result['sync_preview'] = _build_sync_preview(project_cfg['sync_project'], sync_config)
        result['repo_exists'] = repo_path.exists()
        result['git_exists'] = (repo_path / '.git').exists()
        result['prompt_preview'] = _build_cycle_prompt(project_cfg, sync_item, registry_item, previous_state={})
        result['status'] = 'dry_run'
        return result

    if watchdog_report and watchdog_report.get('status') != 'ok':
        result['status'] = 'blocked'
        result['error'] = 'watchdog_tripped'
        result['error_detail'] = '检测到 qq-main 主会话污染或自动进化配置漂移，已拒绝执行自动进化周期。'
        result['finished_at'] = _now_iso()
        return result

    repo_path = _ensure_project_checkout(sync_item, registry_item)
    guard_info = _install_branch_guard(repo_path, project_cfg.get('protected_branches') or ['main'])
    repair_record = _project_sync('repair-boundaries', project_cfg['sync_project'], sync_config, timeout=3600)
    prepare_record = _project_sync('prepare-agent', project_cfg['sync_project'], sync_config, timeout=3600)
    _project_sync('sync-work', project_cfg['sync_project'], sync_config, timeout=3600)
    _project_sync('sync-agent', project_cfg['sync_project'], sync_config, timeout=3600)

    await init_db()
    state = _clean_state(await get_bridge_state_value(STATE_KEY))
    project_state = dict((state.get('projects') or {}).get(project_cfg['name']) or {})
    prompt = _build_cycle_prompt(project_cfg, sync_item, registry_item, previous_state=project_state)

    result['guard'] = guard_info
    result['repair'] = repair_record
    result['prepared'] = prepare_record

    client = OpenClawClient(
        agent_id=project_cfg['agent_id'],
        thinking=project_cfg.get('thinking') or 'low',
        timeout_seconds=int(project_cfg.get('timeout_seconds') or DEFAULT_AGENT_TIMEOUT_SECONDS),
    )
    try:
        turn = await client.agent_turn_result(effective_session_id, prompt)
        reply_text = str(turn.text or '').strip()
        auto_sync_record = _project_sync(
            'sync-agent',
            project_cfg['sync_project'],
            sync_config,
            extra_args=['--commit', f"{project_cfg.get('commit_prefix') or 'chore: 夜间自动进化'} {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            timeout=3600,
        )
        project_state.update(
            {
                'last_started_at': result['started_at'],
                'last_finished_at': _now_iso(),
                'last_summary': reply_text[:4000],
                'last_outcome': reply_text.splitlines()[0].strip() if reply_text else '（无）',
                'last_commit': _extract_commit_hash(reply_text) or '',
                'last_status': 'ok',
                'last_error': '',
                'last_session_id': effective_session_id,
            }
        )
        state.setdefault('projects', {})[project_cfg['name']] = project_state
        await set_bridge_state_value(STATE_KEY, state)
        result['reply_text'] = reply_text
        result['auto_sync'] = auto_sync_record
        result['finished_at'] = project_state['last_finished_at']
        result['status'] = 'ok'
    except OpenClawError as exc:
        project_state.update(
            {
                'last_started_at': result['started_at'],
                'last_finished_at': _now_iso(),
                'last_status': 'error',
                'last_error': str(exc),
                'last_session_id': effective_session_id,
            }
        )
        state.setdefault('projects', {})[project_cfg['name']] = project_state
        await set_bridge_state_value(STATE_KEY, state)
        result['status'] = 'error'
        result['error'] = str(exc)
        result['finished_at'] = project_state['last_finished_at']
    return result


async def status_payload(config_path: Path) -> dict[str, Any]:
    await init_db()
    projects = _load_auto_config(config_path)
    state = _clean_state(await get_bridge_state_value(STATE_KEY))
    watchdog = _build_watchdog_report(projects)
    return {
        'config_path': str(config_path),
        'projects': projects,
        'watchdog': watchdog,
        'state': state,
    }


def watchdog_payload(config_path: Path) -> dict[str, Any]:
    return _build_watchdog_report(_load_auto_config(config_path))


async def watch_projects(config_path: Path, sync_config: Path, poll_seconds: int, dry_run: bool = False) -> None:
    if not dry_run:
        await init_db()
    while True:
        projects = [item for item in _load_auto_config(config_path) if item.get('enabled', True)]
        watchdog = _build_watchdog_report(projects)
        if dry_run:
            project_state_map: dict[str, Any] = {}
        else:
            state = _clean_state(await get_bridge_state_value(STATE_KEY))
            _merge_watchdog_state(state, watchdog)
            await set_bridge_state_value(STATE_KEY, state)
            project_state_map = state.setdefault('projects', {})
        if watchdog.get('status') != 'ok':
            logger.error('自动进化看门狗触发，暂停本轮执行: %s', json.dumps(watchdog, ensure_ascii=False)[:4000])
            await asyncio.sleep(max(30, int(poll_seconds)))
            continue
        for project_cfg in projects:
            project_state = dict(project_state_map.get(project_cfg['name']) or {})
            last_finished = _parse_iso(project_state.get('last_finished_at'))
            interval = timedelta(minutes=int(project_cfg.get('interval_minutes') or 45))
            if last_finished is not None and datetime.now().astimezone() - last_finished < interval:
                continue
            try:
                payload = await run_project_cycle(project_cfg, sync_config=sync_config, dry_run=dry_run, watchdog_report=watchdog)
                logger.info('自动进化周期完成: %s', json.dumps(payload, ensure_ascii=False)[:4000])
            except Exception as exc:
                logger.exception('自动进化周期失败: project=%s err=%s', project_cfg['name'], exc)
        await asyncio.sleep(max(30, int(poll_seconds)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='项目 24 小时自动进化守护脚本')
    parser.add_argument('action', choices=['status', 'watchdog', 'once', 'watch'])
    parser.add_argument('--config', default=str(DEFAULT_CONFIG_PATH), help='自动进化配置路径')
    parser.add_argument('--sync-config', default=str(DEFAULT_SYNC_CONFIG_PATH), help='项目双轨配置路径')
    parser.add_argument('--project', action='append', help='只运行指定项目')
    parser.add_argument('--poll-seconds', type=int, default=120, help='watch 模式轮询间隔')
    parser.add_argument('--dry-run', action='store_true', help='只预演，不真正调用自动进化 agent')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    return parser


def _filter_projects(config_path: Path, selected: list[str] | None) -> list[dict[str, Any]]:
    projects = _load_auto_config(config_path)
    if not selected:
        return projects
    selected_set = {str(item).strip() for item in selected if str(item).strip()}
    return [item for item in projects if item['name'] in selected_set]


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    config_path = Path(args.config).expanduser()
    sync_config = Path(args.sync_config).expanduser()

    if args.action == 'status':
        payload = asyncio.run(status_payload(config_path))
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.action == 'watchdog':
        payload = watchdog_payload(config_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get('status') == 'ok' else 2

    if args.action == 'once':
        projects = [item for item in _filter_projects(config_path, args.project) if item.get('enabled', True)]
        watchdog = _build_watchdog_report([item for item in _load_auto_config(config_path) if item.get('enabled', True)])
        payloads = [
            asyncio.run(run_project_cycle(project_cfg, sync_config=sync_config, dry_run=args.dry_run, watchdog_report=watchdog))
            for project_cfg in projects
        ]
        if args.json:
            print(json.dumps(payloads, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payloads, ensure_ascii=False, indent=2))
        return 0 if args.dry_run or watchdog.get('status') == 'ok' else 2

    selected = {str(item).strip() for item in (args.project or []) if str(item).strip()}
    if selected:
        original_loader = _load_auto_config

        def _filtered_loader(path: Path) -> list[dict[str, Any]]:
            return [item for item in original_loader(path) if item['name'] in selected]

        globals()['_load_auto_config'] = _filtered_loader
    asyncio.run(watch_projects(config_path, sync_config, args.poll_seconds, dry_run=args.dry_run))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
