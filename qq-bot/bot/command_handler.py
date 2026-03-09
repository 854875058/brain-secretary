from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
import logging

from bot.ops_patrol import build_patrol_report

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / 'qq-bot' / 'logs' / 'bot.log'

ALLOWED_COMMANDS = {
    '/help': '显示可用指令',
    '@项目名 指令': '派发任务给 Agent',
    '/projects': '查看所有项目',
    '/tasks': '查看最近任务',
    '/task 编号': '查看任务详情',
    '/agents': '查看运行中的 Agent 进程',
    '/report': '获取完整进度汇报',
    '/note 标题|内容|标签': '添加知识库笔记',
    '/notes': '查看知识库列表',
    '/search 关键词': '搜索知识库',
    '/read 编号': '查看知识库详情',
    '/broadcast 消息': '发布公告',
    '/status': '查看服务状态',
    '/disk': '查看磁盘使用',
    '/patrol': '执行运维巡检',
    '/logs': '查看最近桥接日志',
    '/memories': '查看最近固化记忆',
    '/memory-search 关键词': '搜索桥接层记忆',
    '/watchdog': '查看闭环告警状态',
    '/pc-status': '查看 Paperclip 连通性与配置',
    '/pc-agents': '查看 Paperclip agent 列表',
    '/pc-issues': '查看 Paperclip 最近 issues',
    '/pc-issue': '查看 Paperclip issue 详情',
    '/pc-new': '创建 Paperclip issue',
    '/pc-run': '创建并唤醒 Paperclip 任务',
    '/pc-wake': '手动唤醒 Paperclip agent',
    '/pc-help': '查看 Paperclip 指令帮助',
}


def _trim(text: str, limit: int = 2000) -> str:
    raw = str(text or '').strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + '\n…'


def _disk_report() -> str:
    target = ROOT
    usage = shutil.disk_usage(target)
    total = usage.total / (1024 ** 3)
    used = usage.used / (1024 ** 3)
    free = usage.free / (1024 ** 3)
    return f'磁盘状态\n路径: {target}\n总量: {total:.2f} GB\n已用: {used:.2f} GB\n剩余: {free:.2f} GB'


async def execute_command(cmd: str) -> str:
    logger.info(f'执行指令: {cmd}')

    if cmd == '/help':
        help_text = '可用指令：\n'
        for command, desc in ALLOWED_COMMANDS.items():
            help_text += f'{command} - {desc}\n'
        return help_text.strip()

    if cmd == '/status':
        return await build_patrol_report('/status')

    if cmd == '/patrol':
        return await build_patrol_report('/patrol')

    if cmd == '/disk':
        return _disk_report()

    if cmd == '/logs':
        if not LOG_FILE.exists():
            return f'日志文件不存在: {LOG_FILE}'
        try:
            content = LOG_FILE.read_text(encoding='utf-8', errors='replace')
        except Exception as exc:
            logger.error(f'读取日志失败: {exc}')
            return f'读取日志失败: {exc}'
        return _trim(content[-2500:])

    return '未知指令。发送 /help 查看可用指令'
