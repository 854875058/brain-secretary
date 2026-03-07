from __future__ import annotations

import os
import subprocess
import logging
from bot.workspace import update_agent_status, get_all_agent_status

logger = logging.getLogger(__name__)


def _scan_windows_processes() -> list[dict]:
    result = subprocess.run(
        ["wmic", "process", "where", "name='claude.exe' or name='node.exe' or name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip() and 'CommandLine' not in line]
    processes = []
    for line in lines:
        low = line.lower()
        if 'claude' not in low and 'openclaw' not in low and 'qq-bot' not in low:
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        cmd, pid = parts[0].strip(), parts[1].strip()
        try:
            processes.append({'cmd': cmd[:200], 'pid': int(pid)})
        except ValueError:
            continue
    return processes


def _scan_linux_processes() -> list[dict]:
    result = subprocess.run(['ps', '-eo', 'pid=,args='], capture_output=True, text=True, timeout=10, check=False)
    processes = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid_text, cmd = parts
        low = cmd.lower()
        if 'openclaw' not in low and 'qq-bot' not in low and 'claude' not in low:
            continue
        try:
            processes.append({'cmd': cmd[:240], 'pid': int(pid_text)})
        except ValueError:
            continue
    return processes


async def scan_agent_processes() -> list:
    """扫描当前运行的 Claude/OpenClaw 相关进程（粗略）"""
    try:
        if os.name == 'nt':
            return _scan_windows_processes()
        return _scan_linux_processes()
    except Exception as e:
        logger.error(f"扫描 Agent 进程失败: {e}")
        return []


async def refresh_agent_status():
    """刷新所有 Agent 状态"""
    processes = await scan_agent_processes()

    for proc in processes:
        agent_id = f"claude-{proc['pid']}"
        project = ''
        cmd = proc['cmd']
        low = cmd.lower()
        if '/qq-bot/' in low or '\\qq-bot\\' in low:
            project = 'qq-bot'
        elif '/brain-secretary/' in low or '\\brain-secretary\\' in low:
            project = 'brain-secretary'
        elif '/agent-hub/' in low or '\\agent-hub\\' in low:
            project = 'agent-hub'

        await update_agent_status(
            agent_id=agent_id,
            project=project,
            status='running',
            current_task=cmd[:100],
            pid=proc['pid'],
        )

    return processes


async def get_status_report() -> str:
    """生成状态报告"""
    processes = await scan_agent_processes()
    agents = await get_all_agent_status()

    report = '🤖 Agent 状态报告\n'
    report += '━━━━━━━━━━━━━━━\n'
    report += f'运行中的 Claude/OpenClaw 进程: {len(processes)}\n'
    report += f'最近心跳 Agent 记录: {len(agents)}\n\n'

    if processes:
        for i, proc in enumerate(processes[:10], 1):
            report += f"#{i} PID:{proc['pid']}\n  {proc['cmd'][:120]}\n\n"
    else:
        report += '未检测到 Claude/OpenClaw 相关进程\n'

    return report.strip()
