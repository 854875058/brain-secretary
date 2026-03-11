#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_AGENT_ID = 'auto-evolve-main'
DEFAULT_BRAIN_AGENT_ID = 'qq-main'
DEFAULT_CHILD_AGENTS = ['brain-secretary-dev', 'brain-secretary-review']
DEFAULT_OPENCLAW_CONFIG = Path(os.environ.get('OPENCLAW_CONFIG_PATH') or (Path.home() / '.openclaw' / 'openclaw.json'))
DEFAULT_WORKSPACE = str(Path.home() / '.openclaw' / 'workspace')


class ReconcileError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ReconcileError(f'OpenClaw 配置不存在: {path}')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ReconcileError(f'OpenClaw 配置格式错误: {path}')
    return payload


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + '\n'


def _find_agent(agent_list: list[dict[str, Any]], agent_id: str) -> dict[str, Any] | None:
    for item in agent_list:
        if isinstance(item, dict) and str(item.get('id') or '').strip() == agent_id:
            return item
    return None


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item or '').strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _deep_copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _ensure_agent_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    agents = config.setdefault('agents', {})
    if not isinstance(agents, dict):
        raise ReconcileError('OpenClaw 配置里的 agents 不是对象')
    agent_list = agents.setdefault('list', [])
    if not isinstance(agent_list, list):
        raise ReconcileError('OpenClaw 配置里的 agents.list 不是数组')
    return agent_list


def _state_dir_for(config_path: Path) -> Path:
    override = str(os.environ.get('OPENCLAW_STATE_DIR') or '').strip()
    return Path(override).expanduser() if override else config_path.parent


def _validate_config(config_path: Path) -> None:
    env = os.environ.copy()
    env['OPENCLAW_CONFIG_PATH'] = str(config_path)
    env.setdefault('OPENCLAW_STATE_DIR', str(_state_dir_for(config_path)))
    if os.name == 'nt':
        cmd = [
            r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe',
            '-Command',
            'openclaw config validate',
        ]
    else:
        cmd = ['openclaw', 'config', 'validate']
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise ReconcileError((result.stderr or result.stdout or 'openclaw config validate failed').strip())


def reconcile_config(
    config: dict[str, Any],
    *,
    config_path: Path,
    agent_id: str,
    brain_agent_id: str,
    child_agents: list[str],
    workspace: str | None,
) -> dict[str, Any]:
    agent_list = _ensure_agent_list(config)
    brain_agent = _find_agent(agent_list, brain_agent_id)
    if not brain_agent:
        raise ReconcileError(f'未找到脑控 agent: {brain_agent_id}')

    defaults = config.setdefault('agents', {}).setdefault('defaults', {})
    if not isinstance(defaults, dict):
        raise ReconcileError('agents.defaults 不是对象')

    resolved_workspace = str(
        workspace
        or brain_agent.get('workspace')
        or defaults.get('workspace')
        or DEFAULT_WORKSPACE
    ).strip()
    if not resolved_workspace:
        raise ReconcileError('无法确定 auto-evolve workspace')

    brain_subagents = brain_agent.get('subagents') if isinstance(brain_agent.get('subagents'), dict) else {}
    allow_agents = _unique(list(brain_subagents.get('allowAgents') or []) + list(child_agents))
    if not allow_agents:
        raise ReconcileError('无法确定 auto-evolve 可调用的子 agent 列表')

    model_cfg = {}
    if isinstance(brain_agent.get('model'), dict) and brain_agent.get('model'):
        model_cfg = _deep_copy_json(brain_agent['model'])
    elif isinstance(defaults.get('model'), dict) and defaults.get('model'):
        model_cfg = _deep_copy_json(defaults['model'])

    target_agent = _find_agent(agent_list, agent_id)
    created = False
    if not target_agent:
        target_agent = {'id': agent_id}
        agent_list.append(target_agent)
        created = True

    state_dir = _state_dir_for(config_path)
    agent_dir = state_dir / 'agents' / agent_id / 'agent'
    agent_dir.parent.mkdir(parents=True, exist_ok=True)

    target_agent['id'] = agent_id
    target_agent['name'] = agent_id
    target_agent['workspace'] = resolved_workspace
    target_agent['agentDir'] = str(agent_dir)
    target_agent['subagents'] = {'allowAgents': allow_agents}
    if model_cfg:
        target_agent['model'] = model_cfg

    tools = config.setdefault('tools', {})
    if not isinstance(tools, dict):
        raise ReconcileError('tools 不是对象')
    agent_to_agent = tools.setdefault('agentToAgent', {})
    if not isinstance(agent_to_agent, dict):
        raise ReconcileError('tools.agentToAgent 不是对象')
    agent_to_agent['enabled'] = True
    existing_allow = agent_to_agent.get('allow') if isinstance(agent_to_agent.get('allow'), list) else []
    agent_to_agent['allow'] = _unique([*existing_allow, brain_agent_id, agent_id, *allow_agents])

    return {
        'created': created,
        'agent_id': agent_id,
        'brain_agent_id': brain_agent_id,
        'workspace': resolved_workspace,
        'agent_dir': str(agent_dir),
        'allowed_subagents': allow_agents,
        'agent_to_agent_allow': list(agent_to_agent['allow']),
        'transcript_dir': str(state_dir / 'agents' / agent_id / 'sessions'),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='收敛 OpenClaw auto-evolve 内部 agent 配置')
    parser.add_argument('--openclaw-config', default=str(DEFAULT_OPENCLAW_CONFIG), help='OpenClaw 配置文件路径')
    parser.add_argument('--agent-id', default=DEFAULT_AGENT_ID, help='自动进化内部 agent id')
    parser.add_argument('--brain-agent-id', default=DEFAULT_BRAIN_AGENT_ID, help='QQ 主入口 brain agent id')
    parser.add_argument('--child-agent', action='append', dest='child_agents', help='允许 auto-evolve 调用的子 agent，可重复')
    parser.add_argument('--workspace', default='', help='自动进化内部 agent 的 workspace；默认继承 qq-main')
    parser.add_argument('--dry-run', action='store_true', help='只预览，不写回配置')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.openclaw_config).expanduser()
    config = _load_json(config_path)
    original_text = _dump_json(config)
    summary = reconcile_config(
        config,
        config_path=config_path,
        agent_id=str(args.agent_id or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID,
        brain_agent_id=str(args.brain_agent_id or DEFAULT_BRAIN_AGENT_ID).strip() or DEFAULT_BRAIN_AGENT_ID,
        child_agents=_unique(list(args.child_agents or DEFAULT_CHILD_AGENTS)),
        workspace=str(args.workspace or '').strip() or None,
    )
    updated_text = _dump_json(config)
    changed = updated_text != original_text
    backup_path = ''
    if changed and not args.dry_run:
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        backup_path = str(config_path.with_name(f'{config_path.name}.bak.{timestamp}'))
        shutil.copyfile(config_path, backup_path)
        try:
            config_path.write_text(updated_text, encoding='utf-8', newline='\n')
            _validate_config(config_path)
        except Exception:
            if backup_path and Path(backup_path).exists():
                config_path.write_text(Path(backup_path).read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
            raise
    payload = {
        'changed': changed,
        'dry_run': bool(args.dry_run),
        'config_path': str(config_path),
        'backup_path': backup_path or None,
        **summary,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        status = 'updated' if changed and not args.dry_run else 'ok'
        print(f"[{status}] auto-evolve agent={payload['agent_id']} workspace={payload['workspace']}")
        print(f"- allowAgents: {', '.join(payload['allowed_subagents'])}")
        print(f"- agentToAgent.allow: {', '.join(payload['agent_to_agent_allow'])}")
        if payload['backup_path']:
            print(f"- backup: {payload['backup_path']}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ReconcileError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
