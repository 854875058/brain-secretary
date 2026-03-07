from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS_MANAGER = ROOT / 'scripts' / 'ops_manager.py'

PATROL_KEYWORDS = [
    '巡检', '自诊断', '健康检查', '健康报告', '服务状态', '排查一下', '检查服务', '检查一下', '帮我看下状态',
    '看下服务', '看下端口', '查看状态', '运维巡检',
]


def looks_like_ops_patrol_request(message: str) -> bool:
    text = str(message or '').strip().lower()
    if not text:
        return False
    if text.startswith('/patrol') or text.startswith('/diag'):
        return True
    return any(keyword in text for keyword in PATROL_KEYWORDS)


def _python_cmd() -> list[str]:
    return [sys.executable or ('py' if os.name == 'nt' else 'python3')]


def _run_ops(*args: str, timeout: int = 45) -> str:
    cmd = _python_cmd() + [str(OPS_MANAGER), *args]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, check=False)
    output = (result.stdout or '').strip()
    if result.returncode != 0:
        error = (result.stderr or output or f'ops_manager exit={result.returncode}').strip()
        raise RuntimeError(error)
    return output


def _trim(text: str, limit: int = 1800) -> str:
    raw = str(text or '').strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + '\n…'


async def build_patrol_report(detail: str | None = None) -> str:
    detail_text = str(detail or '').strip().lower()
    status_all = _run_ops('status', 'all', timeout=60)
    ports_all = _run_ops('ports', 'all', timeout=30)

    extra_blocks: list[str] = []
    if any(keyword in detail_text for keyword in ('日志', 'log', 'bridge', 'qq-bot', '报错', '错误', '失败', '异常')):
        try:
            extra_blocks.append('【Bridge 最近日志】\n' + _run_ops('logs', 'bridge', '-n', '40', timeout=30))
        except Exception as exc:
            extra_blocks.append(f'【Bridge 最近日志】\n获取失败: {exc}')

    if any(keyword in detail_text for keyword in ('nginx', '公网', '反代', 'public')):
        try:
            extra_blocks.append('【Public Proxy】\n' + _run_ops('status', 'public_proxy', timeout=20))
        except Exception as exc:
            extra_blocks.append(f'【Public Proxy】\n获取失败: {exc}')

    report = [
        '运维巡检结果',
        '【服务状态】',
        status_all,
        '',
        '【端口状态】',
        ports_all,
    ]
    if extra_blocks:
        report.extend(['', *extra_blocks])

    final = '\n'.join(part for part in report if part is not None).strip()
    return _trim(final, limit=3500)
