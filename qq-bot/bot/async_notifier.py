from __future__ import annotations

import json
import logging
from datetime import datetime
import re
from pathlib import Path
from typing import Any

from bot.task_db import (
    async_delivery_exists,
    get_bridge_route_state,
    get_bridge_state_value,
    record_async_delivery,
    set_bridge_state_value,
)
from bot.evolution_loop import update_evolution_request_from_async_followup

logger = logging.getLogger(__name__)
CONTROL_MARKER_RE = re.compile(r'\[\[(?:reply_to_current)\]\]\s*')
INTERNAL_EVENT_MARKER = '[Internal task completion event]'
ASYNC_NOTIFIER_CURSOR_KEY = 'async_notifier_cursor'


def _extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get('type') != 'text':
                continue
            text = item.get('text')
            if isinstance(text, str) and text.strip():
                parts.append(text.rstrip())
    return '\n'.join(parts).strip()


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except Exception:
        return None


def _iter_internal_followups(transcript_dir: Path):
    transcript_files = sorted(transcript_dir.glob('*.jsonl'))
    for transcript_path in transcript_files:
        try:
            lines = transcript_path.read_text(encoding='utf-8', errors='replace').splitlines()
        except Exception as exc:
            logger.error('读取转录失败: %s %s', transcript_path, exc)
            continue

        pending_internal: dict[str, Any] | None = None
        for raw_line in lines:
            try:
                payload = json.loads(raw_line)
            except Exception:
                continue
            if payload.get('type') != 'message':
                continue
            message = payload.get('message') or {}
            role = message.get('role')
            text = _extract_content_text(message.get('content'))

            if role == 'user':
                if INTERNAL_EVENT_MARKER in text:
                    pending_internal = {
                        'id': str(payload.get('id') or ''),
                        'timestamp': str(payload.get('timestamp') or ''),
                        'text': text,
                        'transcript_path': str(transcript_path),
                    }
                else:
                    pending_internal = None
                continue

            if role != 'assistant':
                continue

            if not pending_internal:
                continue

            if '[[reply_to_current]]' in text:
                cleaned_text = CONTROL_MARKER_RE.sub('', text).strip()
                item_timestamp = str(payload.get('timestamp') or pending_internal.get('timestamp') or '')
                if cleaned_text:
                    yield {
                        'delivery_key': f"{transcript_path}:{payload.get('id')}",
                        'transcript_message_id': str(payload.get('id') or ''),
                        'timestamp': item_timestamp,
                        'content': cleaned_text,
                        'transcript_path': str(transcript_path),
                        'event_timestamp': pending_internal.get('timestamp') or '',
                        'event_text': pending_internal.get('text') or '',
                    }
            pending_internal = None


async def _get_async_cursor_time() -> datetime | None:
    value = await get_bridge_state_value(ASYNC_NOTIFIER_CURSOR_KEY)
    if isinstance(value, dict):
        return _parse_iso_datetime(value.get('latest_timestamp') or value.get('updated_at') or value.get('_db_updated_at'))
    return _parse_iso_datetime(value)


async def _set_async_cursor_time(cursor_dt: datetime, reason: str):
    await set_bridge_state_value(
        ASYNC_NOTIFIER_CURSOR_KEY,
        {
            'latest_timestamp': cursor_dt.isoformat(),
            'reason': reason,
            'updated_at': datetime.now().astimezone().isoformat(),
        },
    )


async def deliver_async_internal_updates(qq_sender, transcript_dir: str | Path, default_user_qq: int | None = None):
    transcript_base = Path(transcript_dir)
    if not transcript_base.exists():
        return 0

    cursor_dt = await _get_async_cursor_time()
    items = list(_iter_internal_followups(transcript_base))
    if not items:
        return 0

    if cursor_dt is None:
        bootstrap_dt = max(
            (
                parsed_dt
                for parsed_dt in (_parse_iso_datetime(item.get('timestamp')) for item in items)
                if parsed_dt is not None
            ),
            default=None,
        )
        if bootstrap_dt is not None:
            await _set_async_cursor_time(bootstrap_dt, 'bootstrap_skip_history')
            logger.info('异步回推游标已初始化到 %s，跳过历史完成记录', bootstrap_dt.isoformat())
        return 0

    route = await get_bridge_route_state() or {}
    target_chat_type = str(route.get('chat_type') or 'private')
    target_user_qq = route.get('user_id') or default_user_qq
    target_group_id = route.get('group_id')
    route_updated_at = _parse_iso_datetime(route.get('updated_at') or route.get('_db_updated_at'))

    delivered_count = 0
    latest_delivered_dt = cursor_dt
    for item in items:
        item_dt = _parse_iso_datetime(item.get('timestamp'))
        if item_dt is None:
            logger.debug('跳过无时间戳异步回推项: %s', item['delivery_key'])
            continue
        if item_dt <= cursor_dt:
            continue
        if await async_delivery_exists(item['delivery_key']):
            if item_dt > latest_delivered_dt:
                latest_delivered_dt = item_dt
            continue
        if route_updated_at is not None and item_dt < route_updated_at:
            if item_dt > latest_delivered_dt:
                latest_delivered_dt = item_dt
            continue

        if target_chat_type == 'group' and target_group_id:
            prefix = f"[CQ:at,qq={target_user_qq}] " if target_user_qq else ''
            await qq_sender.send_group_msg(int(target_group_id), f"{prefix}{item['content']}")
        elif target_user_qq:
            await qq_sender.send_private_msg(int(target_user_qq), item['content'])
        else:
            logger.warning('跳过异步回推：缺少有效目标 route=%s item=%s', route, item['delivery_key'])
            continue

        await record_async_delivery(
            delivery_key=item['delivery_key'],
            transcript_message_id=item['transcript_message_id'],
            transcript_path=item['transcript_path'],
            target_chat_type=target_chat_type,
            target_user_qq=int(target_user_qq) if target_user_qq is not None else None,
            target_group_id=int(target_group_id) if target_group_id else None,
            content=item['content'],
        )
        await update_evolution_request_from_async_followup(
            chat_type=target_chat_type,
            user_qq=int(target_user_qq) if target_user_qq is not None else None,
            group_id=int(target_group_id) if target_group_id else None,
            content=item['content'],
            event_timestamp=item.get('event_timestamp') or item.get('timestamp'),
            event_text=item.get('event_text'),
        )
        delivered_count += 1
        if item_dt > latest_delivered_dt:
            latest_delivered_dt = item_dt
        logger.info('异步回推已发送: chat=%s user=%s group=%s key=%s', target_chat_type, target_user_qq, target_group_id, item['delivery_key'])

    if latest_delivered_dt > cursor_dt:
        await _set_async_cursor_time(latest_delivered_dt, 'processed')

    return delivered_count
