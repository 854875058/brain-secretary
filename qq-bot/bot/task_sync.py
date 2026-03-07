from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.chat_history import load_agent_collaboration_records, load_chat_records
from bot.task_db import (
    CAPABILITY_CHECKLIST_ITEMS,
    get_bridge_route_state,
    get_bridge_state_value,
    get_checklist_items,
    seed_capability_checklist,
    set_bridge_state_value,
    update_checklist_item,
)

logger = logging.getLogger(__name__)

TASK_SYNC_CURSOR_KEY = 'task_sync_cursor'
ROUTE_INDEX_LIMIT = 1200
MAX_NOTE_LENGTH = 3600
MAX_VALIDATION_LENGTH = 3200
SPACE_RE = re.compile(r'\s+')

MATCH_RULES: dict[str, list[str]] = {
    'cap_send_image': ['发图片', '发图', 'send_image', '图片文件', '图片直链'],
    'cap_send_file': ['发文件', 'send_file', '文件发送', '文件消息'],
    'cap_send_voice': ['发语音', '语音消息', 'record 消息', 'record消息', 'send_voice', 'voice'],
    'cap_send_video': ['发视频', '视频消息', 'qq-video', 'send_video', 'video'],
    'cap_read_multimodal': ['读图', '读文件', '读语音', '读视频', '多模态', 'multimodal'],
    'cap_ops_patrol': ['运维巡检', '巡检', 'ops_manager', '健康报告', '状态检查', '端口', '反代', '日志'],
    'cap_subagent_coordination': ['子 agent 协调', '子agent协调', '异步回推', '完成一件', '派单', '多 agent', 'multi-agent', 'subagent', '任务清单'],
    'cap_message_diag_enhancement': ['网页转 markdown', 'markdown', '故障自诊断', '部署变更同步', 'qq 消息增强', '统一媒体', '引用回复', '长文自动折叠', '内容落地'],
}

LABEL_MATCH_OVERRIDES: dict[str, list[str]] = {
    'qq-video-send-capability': ['cap_send_video'],
    'evolve-media-and-ops-reference': ['cap_message_diag_enhancement'],
    'evolve-media-and-ops-main': ['cap_read_multimodal', 'cap_ops_patrol', 'cap_subagent_coordination', 'cap_message_diag_enhancement'],
}

DONE_VERIFY_KEYWORDS = [
    '已验证', '验证通过', '真实发送测试通过', '真实 qq 端到端验证', '端到端验证通过', '实发测试', '真实 qq 实发',
]
PENDING_VERIFY_KEYWORDS = [
    '待 qq 端到端验证', '待端到端验证', '还差真实 qq 端到端验证', '待验证', '最小可用落地', '已实现待验证',
]
COORDINATION_DONE_KEYWORDS = ['异步回推', '任务清单', '筛选', '完成一件', '回推已发送']

LOCAL_COORDINATION_VALIDATION = '已完成异步完成回推、任务清单、公网页面筛选与防历史回放修复，并已做桥接服务/接口验证。'
LOCAL_COORDINATION_NOTE = '本地维护动作：已落地异步完成回推、任务清单、任务筛选、子 Agent 协作筛选，并修复桥接重启后历史完成消息回放。'
LOCAL_MESSAGE_NOTE = '本地维护动作：聊天记录页已补任务清单、日期筛选、任务筛选、子 Agent 协作筛选与右侧固定大脑主回复。'
IGNORE_LABEL_KEYWORDS = ['readme-check', 'readme-summary']


def _should_ignore_record(record: dict[str, Any]) -> bool:
    label = _normalize_text(record.get('task_label'))
    return any(_normalize_text(keyword) in label for keyword in IGNORE_LABEL_KEYWORDS)


def _normalize_text(text: str | None) -> str:
    return SPACE_RE.sub('', str(text or '').strip().lower())


def _parse_event_time(value: str | None) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d %H:%M:%S,%f')
    except Exception:
        return None


def _parse_group_id_from_session_label(session_label: str | None) -> int | None:
    text = str(session_label or '').strip()
    if '-group-' not in text:
        return None
    try:
        return int(text.rsplit('-', 1)[-1])
    except Exception:
        return None


def _shorten(text: str | None, limit: int = 240) -> str:
    raw = SPACE_RE.sub(' ', str(text or '').strip())
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip(' …') + '…'


def _merge_text(existing: str | None, new_text: str | None, *, limit: int) -> str | None:
    fresh = str(new_text or '').strip()
    current = str(existing or '').strip()
    if not fresh:
        return current or None
    if fresh in current:
        return current or fresh
    merged = fresh if not current else f'{fresh}\n\n{current}'
    if len(merged) > limit:
        merged = merged[:limit].rstrip() + '…'
    return merged


def _build_route_index(log_path: Path, transcript_dir: Path) -> dict[str, dict[str, Any]]:
    route_index: dict[str, dict[str, Any]] = {}
    for chat_type in ('private', 'group'):
        try:
            records = load_chat_records(log_path, transcript_dir, None, chat_type=chat_type, limit=ROUTE_INDEX_LIMIT)
        except Exception as exc:
            logger.warning('构建 transcript route index 失败: chat=%s err=%s', chat_type, exc)
            continue
        for record in records:
            session_id = str(record.transcript_session_id or '').strip()
            if not session_id or session_id in route_index:
                continue
            route_index[session_id] = {
                'user_qq': int(record.user_id) if record.user_id is not None else None,
                'chat_type': record.chat_type,
                'group_id': _parse_group_id_from_session_label(record.session_label),
                'session_label': record.session_label,
            }
    return route_index


def _build_event_text(record: dict[str, Any]) -> str:
    parts = [
        record.get('task_label'),
        record.get('task_text'),
        record.get('brain_note'),
        record.get('completion_result'),
        record.get('child_final_reply'),
        record.get('child_error'),
    ]
    return '\n'.join(str(part or '') for part in parts if str(part or '').strip())


def _match_item_keys(record: dict[str, Any]) -> list[str]:
    label = _normalize_text(record.get('task_label'))
    for label_key, item_keys in LABEL_MATCH_OVERRIDES.items():
        if _normalize_text(label_key) and _normalize_text(label_key) in label:
            return list(item_keys)

    haystack = _normalize_text(_build_event_text(record))
    if not haystack:
        return []

    matches: list[str] = []
    for item in CAPABILITY_CHECKLIST_ITEMS:
        base_key = str(item.get('item_key') or '').strip()
        title = _normalize_text(item.get('title'))
        keywords = [_normalize_text(keyword) for keyword in MATCH_RULES.get(base_key, [])]
        if title and title in haystack:
            matches.append(base_key)
            continue
        if any(keyword and keyword in haystack for keyword in keywords):
            matches.append(base_key)
    return matches


def _build_note(record: dict[str, Any], matched_titles: list[str]) -> str:
    status = str(record.get('completion_status') or record.get('spawn_status') or 'unknown').strip()
    summary = _shorten(record.get('child_final_reply') or record.get('completion_result') or record.get('task_text'), 260)
    header = ' · '.join(part for part in [
        str(record.get('event_time') or '').strip(),
        str(record.get('agent_id') or 'unknown-agent').strip(),
        status,
        '/'.join(matched_titles) if matched_titles else '',
    ] if part)
    note = header
    if summary:
        note = f'{note}\n{summary}'
    child_error = _shorten(record.get('child_error'), 180)
    if child_error:
        note = f'{note}\n异常：{child_error}'
    return note.strip()


def _build_validation(record: dict[str, Any]) -> str | None:
    status = str(record.get('completion_status') or '').strip().lower()
    if 'completed successfully' not in status:
        return None
    summary = _shorten(record.get('child_final_reply') or record.get('completion_result'), 360)
    if not summary:
        return None
    return ' · '.join(part for part in [
        str(record.get('event_time') or '').strip(),
        str(record.get('agent_id') or 'unknown-agent').strip(),
        summary,
    ] if part)


def _infer_status(base_key: str, current_status: str, record: dict[str, Any], match_count: int) -> str | None:
    status = str(record.get('completion_status') or '').strip().lower()
    evidence = _normalize_text(_build_event_text(record))
    if not status:
        return None

    if 'failed' in status:
        if current_status not in {'done', 'completed'} and match_count == 1:
            return 'failed'
        return None

    if 'timed out' in status:
        if current_status in {'pending', 'in_progress'} and match_count == 1:
            return 'blocked'
        return None

    if 'completed successfully' not in status:
        return None

    if any(_normalize_text(keyword) in evidence for keyword in DONE_VERIFY_KEYWORDS):
        return 'done'

    if base_key == 'cap_subagent_coordination' and any(_normalize_text(keyword) in evidence for keyword in COORDINATION_DONE_KEYWORDS):
        return 'done'

    if any(_normalize_text(keyword) in evidence for keyword in PENDING_VERIFY_KEYWORDS):
        return 'implemented_pending_verify'

    if match_count != 1:
        return None

    if base_key in {'cap_send_file', 'cap_send_voice', 'cap_send_video'}:
        return 'implemented_pending_verify'

    if current_status in {'pending', 'blocked', 'failed'}:
        return 'in_progress'

    return None


async def _get_sync_cursor_time() -> datetime | None:
    value = await get_bridge_state_value(TASK_SYNC_CURSOR_KEY)
    if isinstance(value, dict):
        raw = value.get('latest_timestamp') or value.get('updated_at') or value.get('_db_updated_at')
    else:
        raw = value
    raw_text = str(raw or '').strip()
    if not raw_text:
        return None
    try:
        parsed = datetime.fromisoformat(raw_text.replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is not None:
        try:
            return parsed.astimezone().replace(tzinfo=None)
        except Exception:
            return parsed.replace(tzinfo=None)
    return parsed


async def _set_sync_cursor_time(cursor_dt: datetime):
    await set_bridge_state_value(
        TASK_SYNC_CURSOR_KEY,
        {
            'latest_timestamp': cursor_dt.isoformat(),
            'updated_at': datetime.now().astimezone().isoformat(),
        },
    )


async def sync_local_checklist_milestones(default_user_qq: int | None) -> int:
    if default_user_qq is None:
        return 0
    updates = 0
    coordination_key = f'{int(default_user_qq)}:cap_subagent_coordination'
    message_key = f'{int(default_user_qq)}:cap_message_diag_enhancement'

    await seed_capability_checklist(int(default_user_qq), chat_type='private', group_id=None)

    coordination_item_list = await get_checklist_items(int(default_user_qq), 'private', None)
    coordination_item = next((item for item in coordination_item_list if item.get('item_key') == coordination_key), None)
    if coordination_item is not None:
        notes = _merge_text(coordination_item.get('notes'), LOCAL_COORDINATION_NOTE, limit=MAX_NOTE_LENGTH)
        validation = _merge_text(coordination_item.get('validation'), LOCAL_COORDINATION_VALIDATION, limit=MAX_VALIDATION_LENGTH)
        needs_update = any([
            str(coordination_item.get('status') or '') != 'done',
            str(coordination_item.get('notes') or '') != str(notes or ''),
            str(coordination_item.get('validation') or '') != str(validation or ''),
            str(coordination_item.get('assigned_agent') or '') != 'qq-main',
            str(coordination_item.get('owner_agent') or '') != 'qq-main',
            str(coordination_item.get('source') or '') != 'local_maintenance',
        ])
        if needs_update:
            await update_checklist_item(
                coordination_key,
                status='done',
                notes=notes,
                validation=validation,
                assigned_agent='qq-main',
                owner_agent='qq-main',
                source='local_maintenance',
            )
            updates += 1

    message_item = next((item for item in coordination_item_list if item.get('item_key') == message_key), None)
    if message_item is not None:
        notes = _merge_text(message_item.get('notes'), LOCAL_MESSAGE_NOTE, limit=MAX_NOTE_LENGTH)
        assigned_agent = str(message_item.get('assigned_agent') or 'agent-hub-dev')
        owner_agent = str(message_item.get('owner_agent') or 'qq-main')
        needs_update = any([
            str(message_item.get('notes') or '') != str(notes or ''),
            str(message_item.get('assigned_agent') or '') != assigned_agent,
            str(message_item.get('owner_agent') or '') != owner_agent,
            str(message_item.get('source') or '') != 'local_maintenance',
        ])
        if needs_update:
            await update_checklist_item(
                message_key,
                notes=notes,
                assigned_agent=assigned_agent,
                owner_agent=owner_agent,
                source='local_maintenance',
            )
            updates += 1

    return updates


async def sync_task_checklist_from_transcripts(log_path: str | Path, transcript_dir: str | Path, default_user_qq: int | None = None) -> int:
    log_path = Path(log_path)
    transcript_dir = Path(transcript_dir)
    if not log_path.exists() or not transcript_dir.exists():
        return 0

    route_index = _build_route_index(log_path, transcript_dir)
    transcript_session_ids = sorted({*route_index.keys(), *(path.stem for path in transcript_dir.glob('*.jsonl'))})
    if not transcript_session_ids:
        return 0

    records = [record.to_dict() for record in load_agent_collaboration_records(transcript_dir, transcript_session_ids, limit=500)]
    if not records:
        return 0

    cursor_dt = await _get_sync_cursor_time()
    active_route = await get_bridge_route_state() or {}
    updated_count = 0
    latest_dt = cursor_dt

    ordered_records = sorted(records, key=lambda item: (_parse_event_time(item.get('event_time')) or datetime.min, item.get('event_time') or ''))
    for record in ordered_records:
        if _should_ignore_record(record):
            continue
        event_dt = _parse_event_time(record.get('event_time'))
        if event_dt is None:
            continue
        if cursor_dt is not None and event_dt <= cursor_dt:
            continue

        route = route_index.get(str(record.get('transcript_session_id') or '').strip()) or {}
        chat_type = str(route.get('chat_type') or active_route.get('chat_type') or 'private')
        user_qq = route.get('user_qq') or active_route.get('user_id') or default_user_qq
        group_id = route.get('group_id')
        if group_id is None:
            group_id = active_route.get('group_id')

        if user_qq is None:
            continue

        await seed_capability_checklist(int(user_qq), chat_type=chat_type, group_id=int(group_id) if group_id not in (None, '', 0, '0') else None)
        checklist_items = await get_checklist_items(int(user_qq), chat_type, int(group_id) if group_id not in (None, '', 0, '0') else None)
        item_by_base_key = {
            str(item.get('item_key') or '').split(':', 1)[-1]: item
            for item in checklist_items
            if str(item.get('item_key') or '').strip()
        }

        matched_keys = _match_item_keys(record)
        if not matched_keys:
            latest_dt = event_dt if latest_dt is None or event_dt > latest_dt else latest_dt
            continue

        matched_titles = [str(item_by_base_key.get(base_key, {}).get('title') or base_key) for base_key in matched_keys]
        for base_key in matched_keys:
            item = item_by_base_key.get(base_key)
            if not item:
                continue
            item_key = str(item.get('item_key') or '')
            current_status = str(item.get('status') or 'pending')
            note = _build_note(record, matched_titles)
            merged_notes = _merge_text(item.get('notes'), note, limit=MAX_NOTE_LENGTH)
            validation_update = _build_validation(record)
            merged_validation = _merge_text(item.get('validation'), validation_update, limit=MAX_VALIDATION_LENGTH) if validation_update else None
            next_status = _infer_status(base_key, current_status, record, len(matched_keys))
            await update_checklist_item(
                item_key,
                status=next_status,
                notes=merged_notes,
                validation=merged_validation,
                assigned_agent=str(record.get('agent_id') or item.get('assigned_agent') or ''),
                owner_agent=str(item.get('owner_agent') or 'qq-main'),
                source='subagent_completion_sync',
            )
            updated_count += 1

        latest_dt = event_dt if latest_dt is None or event_dt > latest_dt else latest_dt

    if latest_dt is not None and (cursor_dt is None or latest_dt > cursor_dt):
        await _set_sync_cursor_time(latest_dt)

    return updated_count
