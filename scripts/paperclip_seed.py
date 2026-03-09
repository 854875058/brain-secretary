#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / 'qq-bot'
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))

from bot.paperclip_client import PaperclipClient, PaperclipError  # noqa: E402

OPENCLAW_CONFIG = Path.home() / '.openclaw' / 'openclaw.json'
DEFAULT_LOCAL_ENV_FILE = ROOT / 'ops' / 'paperclip.local.env'
DEFAULT_COMPANY_NAME = 'Brain Secretary'
DEFAULT_COMPANY_DESCRIPTION = 'QQ + OpenClaw + Paperclip 协同控制面'
DEFAULT_API_BASE_URL = 'http://127.0.0.1:3110'
DEFAULT_PUBLIC_URL = 'http://110.41.170.155:3100'
DEFAULT_OPENCLAW_WS_URL = 'ws://127.0.0.1:18789'
DEFAULT_TIMEOUT_SEC = 900
DEFAULT_WAIT_TIMEOUT_MS = 900000

AGENT_DEFS = [
    {
        'name': 'qq-main',
        'title': 'QQ 总协调大脑',
        'role': 'ceo',
        'openclaw_agent_id': 'qq-main',
        'icon': 'brain',
        'capabilities': 'QQ 总入口、任务拆解、协调多 agent、统一回执',
        'permissions': {'canCreateAgents': True},
    },
    {
        'name': 'brain-secretary-dev',
        'title': '工程实施',
        'role': 'engineer',
        'openclaw_agent_id': 'brain-secretary-dev',
        'icon': 'code',
        'capabilities': '代码修改、脚本实现、测试与工程落地',
    },
    {
        'name': 'brain-secretary-review',
        'title': '方案与验收',
        'role': 'qa',
        'openclaw_agent_id': 'brain-secretary-review',
        'icon': 'shield',
        'capabilities': '方案复核、验收、回归检查、风险提示',
    },
]


def load_openclaw_gateway_token(path: Path) -> str:
    if not path.exists():
        raise PaperclipError(f'OpenClaw 配置不存在: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    token = str(((data.get('gateway') or {}).get('auth') or {}).get('token') or '').strip()
    if not token:
        raise PaperclipError(f'OpenClaw gateway token 缺失: {path}')
    return token


def wait_for_health(client: PaperclipClient, timeout_seconds: int) -> None:
    deadline = time.time() + max(3, timeout_seconds)
    last_error = 'unknown'
    while time.time() < deadline:
        try:
            health = client.health()
            if health:
                return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise PaperclipError(f'等待 Paperclip 健康检查超时: {last_error}')


def ensure_company(client: PaperclipClient, name: str, description: str) -> dict[str, Any]:
    existing = client.find_company_by_name(name)
    if existing:
        return existing
    return client.create_company(name=name, description=description)


def ensure_agent(
    client: PaperclipClient,
    *,
    definition: dict[str, Any],
    openclaw_ws_url: str,
    gateway_token: str,
    paperclip_public_url: str,
    reports_to: str | None,
) -> dict[str, Any]:
    existing = client.find_agent_by_name(definition['name'])
    payload: dict[str, Any] = {
        'name': definition['name'],
        'title': definition['title'],
        'role': definition['role'],
        'icon': definition['icon'],
        'reportsTo': reports_to,
        'capabilities': definition['capabilities'],
        'adapterType': 'openclaw_gateway',
        'adapterConfig': {
            'url': openclaw_ws_url,
            'headers': {'x-openclaw-token': gateway_token},
            'agentId': definition['openclaw_agent_id'],
            'timeoutSec': DEFAULT_TIMEOUT_SEC,
            'waitTimeoutMs': DEFAULT_WAIT_TIMEOUT_MS,
            'paperclipApiUrl': paperclip_public_url,
            'sessionKeyStrategy': 'fixed',
            'sessionKey': f"agent:{definition['openclaw_agent_id']}:paperclip",
            'role': 'operator',
            'scopes': ['operator.admin'],
        },
        'permissions': definition.get('permissions') or {},
    }
    if existing:
        patch: dict[str, Any] = {
            'title': payload['title'],
            'role': payload['role'],
            'icon': payload['icon'],
            'reportsTo': payload['reportsTo'],
            'capabilities': payload['capabilities'],
            'adapterConfig': payload['adapterConfig'],
        }
        return client.update_agent(str(existing.get('id') or '').strip(), patch)
    return client.create_agent(payload)


def write_local_env(path: Path, values: dict[str, str], *, remove_keys: set[str] | None = None) -> None:
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            raw = line.strip()
            if not raw or raw.startswith('#') or '=' not in raw:
                continue
            key, value = raw.split('=', 1)
            existing[key.strip()] = value.strip()
    existing.update({key: value for key, value in values.items() if str(value or '').strip() != ''})
    for key in remove_keys or set():
        existing.pop(key, None)
    lines = [f'{key}={existing[key]}' for key in sorted(existing)]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='初始化 Paperclip company / agents / 本地联动 env')
    parser.add_argument('--company-name', default=DEFAULT_COMPANY_NAME)
    parser.add_argument('--company-description', default=DEFAULT_COMPANY_DESCRIPTION)
    parser.add_argument('--api-base-url', default=os.environ.get('QQ_BOT_PAPERCLIP_API_BASE_URL', DEFAULT_API_BASE_URL))
    parser.add_argument('--public-url', default=DEFAULT_PUBLIC_URL)
    parser.add_argument('--openclaw-ws-url', default=DEFAULT_OPENCLAW_WS_URL)
    parser.add_argument('--openclaw-config', default=str(OPENCLAW_CONFIG))
    parser.add_argument('--env-file', default=str(DEFAULT_LOCAL_ENV_FILE))
    parser.add_argument('--agent-key-name', default='qq-bridge')
    parser.add_argument('--auth-mode', choices=['local_trusted', 'agent_key'], default='local_trusted')
    parser.add_argument('--wait-timeout', type=int, default=60)
    parser.add_argument('--json', action='store_true')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    os.environ['QQ_BOT_PAPERCLIP_ENABLED'] = 'true'
    os.environ['QQ_BOT_PAPERCLIP_API_BASE_URL'] = args.api_base_url
    if args.auth_mode == 'local_trusted':
        client = PaperclipClient(
            enabled=True,
            api_base_url=args.api_base_url.rstrip('/'),
            timeout_seconds=30,
        )
    else:
        client = PaperclipClient.from_config({})
    wait_for_health(client, args.wait_timeout)
    gateway_token = load_openclaw_gateway_token(Path(args.openclaw_config))
    company = ensure_company(client, args.company_name, args.company_description)
    client.company_id = str(company.get('id') or '').strip()

    created_agents: list[dict[str, Any]] = []
    ceo_agent = ensure_agent(
        client,
        definition=AGENT_DEFS[0],
        openclaw_ws_url=args.openclaw_ws_url,
        gateway_token=gateway_token,
        paperclip_public_url=args.public_url,
        reports_to=None,
    )
    created_agents.append(ceo_agent)
    ceo_id = str(ceo_agent.get('id') or '').strip()
    if ceo_id:
        client.update_agent_permissions(ceo_id, can_create_agents=True)

    for definition in AGENT_DEFS[1:]:
        created_agents.append(
            ensure_agent(
                client,
                definition=definition,
                openclaw_ws_url=args.openclaw_ws_url,
                gateway_token=gateway_token,
                paperclip_public_url=args.public_url,
                reports_to=ceo_id or None,
            )
        )

    key_payload = client.create_agent_key(ceo_id, name=args.agent_key_name) if ceo_id else {}
    token = str(key_payload.get('token') or key_payload.get('key') or key_payload.get('value') or '').strip()

    env_values = {
        'QQ_BOT_PAPERCLIP_ENABLED': 'true',
        'QQ_BOT_PAPERCLIP_API_BASE_URL': args.api_base_url,
        'QQ_BOT_PAPERCLIP_COMPANY_ID': client.company_id,
        'QQ_BOT_PAPERCLIP_DEFAULT_ASSIGNEE_AGENT_ID': ceo_id,
    }
    remove_keys: set[str] = set()
    if args.auth_mode == 'agent_key' and token:
        env_values['QQ_BOT_PAPERCLIP_API_KEY'] = token
    else:
        remove_keys.add('QQ_BOT_PAPERCLIP_API_KEY')
    write_local_env(Path(args.env_file), env_values, remove_keys=remove_keys)

    payload = {
        'company': company,
        'agents': created_agents,
        'agent_key': key_payload,
        'local_env_file': str(Path(args.env_file)),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Paperclip 初始化完成: company={company.get('name')} ({company.get('id')})")
        print(f"- local env: {args.env_file}")
        for agent in created_agents:
            print(f"- agent: {agent.get('name')} | id={agent.get('id')} | role={agent.get('role')}")
        if token:
            print(f"- qq-main agent key generated: {args.agent_key_name}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except PaperclipError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
