from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.task_db import get_bridge_state_value, set_bridge_state_value
from bot.runtime_paths import PROJECT_ROOT

logger = logging.getLogger(__name__)
MANIFEST_PATH = PROJECT_ROOT / 'ops' / 'deployment_manifest.json'
STATE_KEY = 'watchdog_last_snapshot'


def _load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def _platform_name() -> str:
    return 'windows' if os.name == 'nt' else 'linux'


def _normalize_host(host: str) -> str:
    value = str(host or '').strip() or '127.0.0.1'
    if value in {'0.0.0.0', '::', '*'}:
        return '127.0.0.1'
    return value


def _check_port(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((_normalize_host(host), int(port)), timeout=timeout):
            return True
    except OSError:
        return False


async def _check_napcat(qq_sender) -> dict[str, Any]:
    try:
        payload = await qq_sender.call_action('get_login_info', {}, timeout=8)
        ok = str(payload.get('status') or '').lower() == 'ok'
        data = payload.get('data') if isinstance(payload, dict) else None
        nickname = ''
        if isinstance(data, dict):
            nickname = str(data.get('nickname') or data.get('user_name') or '').strip()
        detail = f"NapCat API={qq_sender.base_url}" + (f" nickname={nickname}" if nickname else '')
        return {'name': 'napcat_api', 'ok': ok, 'detail': detail, 'critical': True}
    except Exception as exc:
        return {'name': 'napcat_api', 'ok': False, 'detail': f'NapCat API 不可达: {exc}', 'critical': True}


async def collect_watchdog_snapshot(qq_sender) -> dict[str, Any]:
    manifest = _load_manifest()
    platform = _platform_name()
    platform_cfg = manifest['platforms'][platform]
    components = list(dict.fromkeys(platform_cfg.get('groups', {}).get('backend', []) + platform_cfg.get('groups', {}).get('frontend', [])))

    items: list[dict[str, Any]] = []
    for component in components:
        common = manifest['components'].get(component, {})
        platform_meta = platform_cfg.get('components', {}).get(component, {})
        label = str(common.get('label') or component)
        for port_item in platform_meta.get('ports', []) or []:
            host = str(port_item.get('host') or '127.0.0.1')
            port = int(port_item.get('port'))
            port_name = str(port_item.get('name') or 'port')
            ok = _check_port(host, port)
            critical = component in set(platform_cfg.get('groups', {}).get('backend', []))
            items.append({
                'name': f'{component}:{port_name}',
                'ok': ok,
                'detail': f'{label} {_normalize_host(host)}:{port}',
                'critical': critical,
            })

    items.append(await _check_napcat(qq_sender))
    unhealthy = [item for item in items if item.get('critical') and not item.get('ok')]
    return {
        'checked_at': datetime.now().astimezone().isoformat(),
        'platform': platform,
        'healthy': not unhealthy,
        'items': items,
    }


def _snapshot_key(item: dict[str, Any]) -> str:
    return str(item.get('name') or '').strip()


async def build_watchdog_report(qq_sender) -> str:
    snapshot = await collect_watchdog_snapshot(qq_sender)
    lines = [
        'Watchdog 状态',
        f"时间: {snapshot['checked_at']}",
        f"总体: {'正常' if snapshot['healthy'] else '异常'}",
    ]
    for item in snapshot.get('items', []):
        flag = 'OK' if item.get('ok') else 'FAIL'
        lines.append(f"- {flag} {item.get('name')}: {item.get('detail')}")
    return '\n'.join(lines)


async def run_watchdog_pass(qq_sender, target_qq: int | None) -> dict[str, Any]:
    snapshot = await collect_watchdog_snapshot(qq_sender)
    previous = await get_bridge_state_value(STATE_KEY)
    await set_bridge_state_value(STATE_KEY, snapshot, updated_at=snapshot['checked_at'])

    if not isinstance(previous, dict):
        return snapshot

    previous_items = { _snapshot_key(item): item for item in previous.get('items', []) if isinstance(item, dict) }
    current_items = { _snapshot_key(item): item for item in snapshot.get('items', []) if isinstance(item, dict) }

    changed_failures: list[str] = []
    recovered_items: list[str] = []
    for key, current in current_items.items():
        old = previous_items.get(key) or {}
        if old.get('ok', True) and not current.get('ok', True):
            changed_failures.append(f"- {key}: {current.get('detail')}")
        elif not old.get('ok', True) and current.get('ok', True):
            recovered_items.append(f"- {key}: {current.get('detail')}")

    if changed_failures and target_qq:
        message = '⚠️ Watchdog 告警\n' + '\n'.join(changed_failures) + '\n\n请优先排查对应服务/端口。'
        await qq_sender.send_private_msg(int(target_qq), message)
        logger.warning('Watchdog 发现新的异常: %s', '; '.join(changed_failures))
    elif recovered_items and target_qq:
        message = '✅ Watchdog 恢复\n' + '\n'.join(recovered_items)
        await qq_sender.send_private_msg(int(target_qq), message)
        logger.info('Watchdog 检测到恢复项: %s', '; '.join(recovered_items))

    return snapshot
