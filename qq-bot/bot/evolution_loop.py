from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from bot.task_db import (
    get_bridge_state_value,
    set_bridge_state_value,
    update_checklist_item,
    upsert_checklist_item,
)

EVOLUTION_STATE_PREFIX = 'active_evolution_request:'
MAX_NOTE_LENGTH = 2400
DEFAULT_SORT_INDEX = 900
AGENT_FROM_EVENT_RE = re.compile(r'session_key:\s*agent:(?P<agent_id>[^:\s]+):subagent:', re.IGNORECASE)
WHITESPACE_RE = re.compile(r'\s+')
STRIP_PREFIX_RE = re.compile(r'^(?:请|帮我|麻烦|现在|以后|希望你|你要|你得|让你|把你|把这个|给你)')
BLOCKED_KEYWORDS = ['失败', '做不了', '无法', '不能', '阻塞', '卡住', '超时', '中断']
DONE_VERIFIED_KEYWORDS = ['已验证', '验证通过', '测试通过', '端到端通过', '验收通过']
DONE_KEYWORDS = ['已完成', '已经完成', '已落地', '已经落地', '已修复', '已经修复', '已支持', '已经支持', '已接入', '已经接入', '搞定', '完成了', '改好了']
PROGRESS_KEYWORDS = ['已开始', '开始处理', '已安排', '已派', '正在', '处理中', '继续推进', '拆成', '下一步']


def _chat_scope_key(chat_type: str, user_qq: int | None, group_id: int | None) -> str:
    normalized_chat = 'group' if str(chat_type or '').strip() == 'group' else 'private'
    normalized_user = int(user_qq) if user_qq is not None else 0
    normalized_group = int(group_id) if group_id not in (None, '', 0, '0') else 0
    if normalized_chat == 'group':
        return f'group:{normalized_group}:{normalized_user}'
    return f'private:{normalized_user}'


def _state_key(chat_type: str, user_qq: int | None, group_id: int | None) -> str:
    return EVOLUTION_STATE_PREFIX + _chat_scope_key(chat_type, user_qq, group_id)


def _normalize_text(text: str | None) -> str:
    return WHITESPACE_RE.sub(' ', str(text or '')).strip()


def _merge_text(existing: str | None, new_text: str | None, *, limit: int = MAX_NOTE_LENGTH) -> str | None:
    normalized_new = str(new_text or '').strip()
    if not normalized_new:
        return str(existing or '').strip() or None
    normalized_existing = str(existing or '').strip()
    if not normalized_existing:
        merged = normalized_new
    elif normalized_new in normalized_existing:
        merged = normalized_existing
    else:
        merged = f'{normalized_existing}\n\n{normalized_new}'
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except Exception:
        return None


def _summarize_request_title(user_message: str) -> str:
    text = _normalize_text(user_message)
    if not text:
        return '自助进化任务'
    text = STRIP_PREFIX_RE.sub('', text, count=1).strip('：:，,。；; ')
    if not text:
        text = _normalize_text(user_message)
    if len(text) > 28:
        text = text[:28].rstrip() + '…'
    return f'自助进化：{text}'


def _build_item_key(chat_type: str, user_qq: int, group_id: int | None, user_message: str) -> str:
    now_stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    scope_key = _chat_scope_key(chat_type, user_qq, group_id)
    digest = hashlib.sha1(f'{scope_key}|{user_message}|{now_stamp}'.encode('utf-8')).hexdigest()[:10]
    return f'{int(user_qq)}:evolution:{now_stamp}:{digest}'


def _infer_status(text: str | None, current_status: str = 'in_progress') -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return current_status or 'in_progress'
    if any(keyword in normalized for keyword in BLOCKED_KEYWORDS):
        return 'blocked'
    if any(keyword in normalized for keyword in DONE_VERIFIED_KEYWORDS):
        return 'done'
    if any(keyword in normalized for keyword in DONE_KEYWORDS):
        return 'implemented_pending_verify'
    if any(keyword in normalized for keyword in PROGRESS_KEYWORDS):
        return 'in_progress'
    return current_status or 'in_progress'


def _extract_agent_id(event_text: str | None) -> str | None:
    text = str(event_text or '').strip()
    if not text:
        return None
    match = AGENT_FROM_EVENT_RE.search(text)
    if match:
        return match.group('agent_id')
    return None


async def begin_evolution_request(
    *,
    chat_type: str,
    user_qq: int,
    group_id: int | None,
    user_message: str,
) -> dict[str, Any]:
    now = datetime.now().astimezone().isoformat()
    item_key = _build_item_key(chat_type, int(user_qq), group_id, user_message)
    title = _summarize_request_title(user_message)
    detail = _normalize_text(user_message)
    validation = '由 qq-main 统筹落地；若涉及工程实现，应自动派给对应子 agent，并在 QQ 异步回推进展。'
    notes = '来自 QQ 的自助进化诉求，已进入闭环执行。'
    await upsert_checklist_item(
        item_key=item_key,
        title=title,
        detail=detail,
        status='in_progress',
        sort_index=DEFAULT_SORT_INDEX,
        assigned_agent='qq-main',
        owner_agent='qq-main',
        category='evolution',
        source='qq_evolution_request',
        user_qq=int(user_qq),
        group_id=int(group_id) if group_id not in (None, '', 0, '0') else None,
        chat_type=str(chat_type or 'private'),
        notes=notes,
        validation=validation,
    )
    state = {
        'item_key': item_key,
        'title': title,
        'detail': detail,
        'chat_type': str(chat_type or 'private'),
        'user_qq': int(user_qq),
        'group_id': int(group_id) if group_id not in (None, '', 0, '0') else None,
        'status': 'in_progress',
        'created_at': now,
        'updated_at': now,
        'progress_count': 0,
        'source': 'qq_evolution_request',
    }
    await set_bridge_state_value(_state_key(chat_type, user_qq, group_id), state, updated_at=now)
    return state


def build_evolution_ack_text(state: dict[str, Any] | None) -> str:
    if not isinstance(state, dict):
        return '收到，我会按自助进化流程处理，并在 QQ 里继续回推进展。'
    title = str(state.get('title') or '这次自助进化').strip()
    return f'收到，已记录任务：{title}。接下来会优先拆解并落地，完成一件回一件。'


async def _load_active_request(chat_type: str, user_qq: int | None, group_id: int | None) -> dict[str, Any] | None:
    value = await get_bridge_state_value(_state_key(chat_type, user_qq, group_id))
    return value if isinstance(value, dict) else None


async def update_evolution_request_from_sync_reply(
    *,
    chat_type: str,
    user_qq: int | None,
    group_id: int | None,
    reply_text: str | None,
) -> None:
    state = await _load_active_request(chat_type, user_qq, group_id)
    if not state:
        return
    item_key = str(state.get('item_key') or '').strip()
    if not item_key:
        return
    summary = _normalize_text(reply_text)
    if not summary:
        return
    next_status = _infer_status(summary, str(state.get('status') or 'in_progress'))
    notes = _merge_text(state.get('last_note'), f'【主脑回复】{summary}')
    now = datetime.now().astimezone().isoformat()
    await update_checklist_item(
        item_key,
        status=next_status,
        notes=notes,
        assigned_agent='qq-main',
        owner_agent='qq-main',
        source='qq_evolution_reply',
    )
    state.update({
        'status': next_status,
        'updated_at': now,
        'last_note': notes,
        'last_reply': summary[:600],
    })
    await set_bridge_state_value(_state_key(chat_type, user_qq, group_id), state, updated_at=now)


async def update_evolution_request_from_async_followup(
    *,
    chat_type: str,
    user_qq: int | None,
    group_id: int | None,
    content: str | None,
    event_timestamp: str | None = None,
    event_text: str | None = None,
) -> None:
    state = await _load_active_request(chat_type, user_qq, group_id)
    if not state:
        return
    item_key = str(state.get('item_key') or '').strip()
    if not item_key:
        return
    created_dt = _parse_iso_datetime(state.get('created_at'))
    event_dt = _parse_iso_datetime(event_timestamp)
    if created_dt is not None and event_dt is not None and event_dt < created_dt:
        return
    summary = _normalize_text(content)
    if not summary:
        return
    agent_id = _extract_agent_id(event_text) or str(state.get('assigned_agent') or 'qq-main')
    progress_count = int(state.get('progress_count') or 0) + 1
    next_status = _infer_status(summary, str(state.get('status') or 'in_progress'))
    note = f'【进展#{progress_count} · {agent_id}】{summary}'
    notes = _merge_text(state.get('last_note'), note)
    now = datetime.now().astimezone().isoformat()
    await update_checklist_item(
        item_key,
        status=next_status,
        notes=notes,
        assigned_agent=agent_id,
        owner_agent='qq-main',
        source='qq_evolution_async',
    )
    state.update({
        'status': next_status,
        'updated_at': now,
        'progress_count': progress_count,
        'assigned_agent': agent_id,
        'last_note': notes,
        'last_event_text': str(event_text or '')[:600],
        'last_reply': summary[:600],
    })
    if event_timestamp:
        state['last_event_timestamp'] = event_timestamp
    await set_bridge_state_value(_state_key(chat_type, user_qq, group_id), state, updated_at=now)
