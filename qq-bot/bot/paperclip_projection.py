from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bot.chat_history import AgentCollaborationRecord, load_agent_collaboration_records, normalize_text, parse_log_timestamp
from bot.paperclip_client import PaperclipClient, PaperclipError
from bot.runtime_paths import OPENCLAW_TRANSCRIPT_DIR, OPENCLAW_TRANSCRIPT_DIRS, ensure_runtime_dirs
from bot.task_db import get_bridge_state_value, init_db, set_bridge_state_value

logger = logging.getLogger(__name__)

PROJECTOR_STATE_KEY = 'paperclip_auto_projection_v1'
DEFAULT_LIMIT = 500
DEFAULT_BOOTSTRAP_HOURS = 12
DONE_STATUSES = {'done', 'success', 'succeeded', 'completed', 'complete', 'ok'}
BLOCKED_STATUSES = {'error', 'failed', 'failure', 'timeout', 'timed_out', 'cancelled', 'canceled', 'blocked'}
ROLE_LABELS = {
    'qq-main': '大脑协调',
    'brain-secretary-dev': '技术执行',
    'brain-secretary-review': '方案验收',
}


@dataclass(slots=True)
class ProjectionStats:
    scanned_records: int = 0
    grouped_tasks: int = 0
    created_parents: int = 0
    updated_parents: int = 0
    created_children: int = 0
    updated_children: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run: bool = False
    first_sync: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _trim(text: str | None, limit: int = 240) -> str:
    normalized = normalize_text(text or '')
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + '…'


def _block(title: str, text: str | None, limit: int = 2400) -> str:
    cleaned = (text or '').strip()
    if not cleaned:
        return ''
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip() + '\n…'
    return f'## {title}\n\n```text\n{cleaned}\n```\n'


def _safe_log_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_log_timestamp(value)
    except Exception:
        return None


def _hash_key(*parts: str) -> str:
    payload = '||'.join(str(part or '').strip() for part in parts)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()[:20]


def _role_label(agent_id: str | None) -> str:
    normalized = str(agent_id or '').strip()
    return ROLE_LABELS.get(normalized, normalized or '未指明角色')


def _normalize_status(value: str | None) -> str:
    return str(value or '').strip().lower().replace('-', '_').replace(' ', '_')


def _record_effective_status(record: AgentCollaborationRecord) -> str:
    completion_status = _normalize_status(record.completion_status)
    spawn_status = _normalize_status(record.spawn_status)
    if completion_status in DONE_STATUSES:
        return 'done'
    if completion_status in BLOCKED_STATUSES:
        return 'blocked'
    if record.child_error or record.spawn_error:
        return 'blocked'
    if record.child_final_reply or record.completion_result:
        return 'done'
    if spawn_status in BLOCKED_STATUSES:
        return 'blocked'
    if spawn_status in {'accepted', 'requested'}:
        return 'todo'
    return 'todo'


def _group_status(records: list[AgentCollaborationRecord]) -> str:
    statuses = {_record_effective_status(record) for record in records}
    if statuses and statuses <= {'done'}:
        return 'done'
    if 'todo' in statuses:
        return 'todo'
    if 'blocked' in statuses:
        return 'blocked'
    return 'todo'


def _projection_group_key(record: AgentCollaborationRecord) -> str:
    return _hash_key(
        record.transcript_session_id or '',
        record.source_user_time or record.event_time or '',
        record.source_user_text or '',
    )


def _projection_child_key(record: AgentCollaborationRecord) -> str:
    task_fingerprint = record.task_label or _trim(record.task_text, 120) or ''
    return _hash_key(
        record.transcript_session_id or '',
        record.source_user_time or record.event_time or '',
        record.source_user_text or '',
        record.agent_id or '',
        task_fingerprint,
    )


def _merge_record(existing: AgentCollaborationRecord, incoming: AgentCollaborationRecord) -> AgentCollaborationRecord:
    existing_dt = _safe_log_time(existing.event_time)
    incoming_dt = _safe_log_time(incoming.event_time)
    newer = incoming
    older = existing
    if existing_dt and incoming_dt and existing_dt > incoming_dt:
        newer = existing
        older = incoming

    merged = older.to_dict()
    incoming_payload = newer.to_dict()
    for key, value in incoming_payload.items():
        if value not in (None, ''):
            merged[key] = value

    newer_spawn_status = _normalize_status(incoming_payload.get('spawn_status'))
    if newer_spawn_status in {'accepted', 'requested'} and not incoming_payload.get('spawn_error'):
        merged['spawn_error'] = None
    newer_completion_status = _normalize_status(incoming_payload.get('completion_status'))
    if newer_completion_status in DONE_STATUSES and not incoming_payload.get('child_error'):
        merged['child_error'] = None

    return AgentCollaborationRecord(**merged)


def _collapse_records(records: list[AgentCollaborationRecord]) -> list[AgentCollaborationRecord]:
    by_key: dict[str, AgentCollaborationRecord] = {}
    ordered = sorted(records, key=lambda item: _safe_log_time(item.event_time) or datetime.min)
    for record in ordered:
        if not record.agent_id:
            continue
        key = _projection_child_key(record)
        previous = by_key.get(key)
        by_key[key] = record if previous is None else _merge_record(previous, record)
    return list(by_key.values())


def _render_parent_title(records: list[AgentCollaborationRecord]) -> str:
    lead = records[0]
    summary = _trim(lead.source_user_text or lead.task_label or lead.task_text or 'QQ 协同任务', 64)
    return f'QQ 协同 | {summary}'


def _render_child_title(record: AgentCollaborationRecord) -> str:
    summary = _trim(record.task_label or record.source_user_text or record.child_task_excerpt or record.task_text or '子任务', 48)
    return f'QQ 子任务 | {_role_label(record.agent_id)} | {summary}'


def _render_parent_description(records: list[AgentCollaborationRecord]) -> str:
    lead = records[0]
    lines = [
        '# QQ 自动投影协同',
        '',
        '- 投影来源: OpenClaw `qq-main` / `auto-evolve-main` 子 agent 协作转录',
        f'- 来源请求: {_trim(lead.source_user_text or lead.task_text or "(未提取到)", 300)}',
        f'- 来源时间: {lead.source_user_time or lead.event_time or ""}',
        f'- 主会话: {lead.transcript_session_id or ""}',
        f'- 当前状态: {_group_status(records)}',
        f'- 自动同步时间: {_now_iso()}',
        '',
        '## 子任务概览',
        '',
    ]
    for record in records:
        lines.append(
            '- '
            f'{_role_label(record.agent_id)} (`{record.agent_id or ""}`) | '
            f'status={_record_effective_status(record)} | '
            f'label={record.task_label or "(无)"} | '
            f'child_session={record.child_session_id or record.child_session_key or "(无)"}'
        )
    brain_notes = [record.brain_note for record in records if record.brain_note]
    if brain_notes:
        lines.extend(['', _block('大脑派单说明', '\n\n'.join(brain_notes[:2]), limit=1600).rstrip()])
    return '\n'.join(part for part in lines if part is not None).strip() + '\n'


def _render_child_description(record: AgentCollaborationRecord) -> str:
    sections = [
        '# QQ 子任务自动投影',
        '',
        f'- 角色: {_role_label(record.agent_id)}',
        f'- agent_id: `{record.agent_id or ""}`',
        f'- 来源请求: {_trim(record.source_user_text or record.task_text or "(未提取到)", 300)}',
        f'- 来源时间: {record.source_user_time or record.event_time or ""}',
        f'- 主会话: `{record.transcript_session_id or ""}`',
        f'- spawn_message_id: `{record.spawn_message_id or ""}`',
        f'- task_label: `{record.task_label or ""}`',
        f'- spawn_status: `{record.spawn_status or ""}`',
        f'- completion_status: `{record.completion_status or ""}`',
        f'- child_session_key: `{record.child_session_key or ""}`',
        f'- child_session_id: `{record.child_session_id or ""}`',
        f'- child_run_id: `{record.child_run_id or ""}`',
        f'- child_session_path: `{record.child_session_path or ""}`',
        f'- 自动同步时间: {_now_iso()}',
        '',
    ]
    if record.spawn_error:
        sections.append(_block('派单异常', record.spawn_error, limit=800).rstrip())
    if record.brain_note:
        sections.append(_block('大脑派单说明', record.brain_note, limit=1600).rstrip())
    if record.task_text:
        sections.append(_block('子任务原文', record.task_text, limit=2400).rstrip())
    if record.child_task_excerpt and record.child_task_excerpt != record.task_text:
        sections.append(_block('子会话任务摘录', record.child_task_excerpt, limit=1800).rstrip())
    if record.completion_result:
        sections.append(_block('完成结果回推', record.completion_result, limit=2400).rstrip())
    if record.child_final_reply:
        sections.append(_block('子 agent 最终回复', record.child_final_reply, limit=2400).rstrip())
    if record.child_error:
        sections.append(_block('子会话错误', record.child_error, limit=1200).rstrip())
    return '\n'.join(part for part in sections if part).strip() + '\n'


def _payload_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def _clean_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {'version': 1, 'parents': {}, 'children': {}, 'bootstrapped_at': None}
    cleaned = dict(raw)
    cleaned.pop('_db_updated_at', None)
    cleaned.setdefault('version', 1)
    cleaned.setdefault('parents', {})
    cleaned.setdefault('children', {})
    cleaned.setdefault('bootstrapped_at', None)
    return cleaned


def _is_internal_paperclip_wake(text: str | None) -> bool:
    normalized = normalize_text(text or '').lower()
    if not normalized:
        return False
    if normalized.startswith('paperclip wake event'):
        return True
    if 'paperclip wake event for a cloud adapter' in normalized:
        return True
    if 'paperclip_run_id=' in normalized and 'paperclip_task_id=' in normalized:
        return True
    return False


def _filter_projectable_records(records: list[AgentCollaborationRecord]) -> list[AgentCollaborationRecord]:
    return [record for record in records if not _is_internal_paperclip_wake(record.source_user_text)]



def _filter_bootstrap_records(records: list[AgentCollaborationRecord], bootstrap_hours: int) -> list[AgentCollaborationRecord]:
    if bootstrap_hours <= 0:
        return records
    cutoff = datetime.now() - timedelta(hours=bootstrap_hours)
    filtered: list[AgentCollaborationRecord] = []
    for record in records:
        event_dt = _safe_log_time(record.event_time)
        if event_dt is None or event_dt >= cutoff:
            filtered.append(record)
    return filtered


def _resolve_transcript_dirs(transcript_dir: Any = None) -> list[Path]:
    if transcript_dir is None:
        candidates = list(OPENCLAW_TRANSCRIPT_DIRS)
    elif isinstance(transcript_dir, (str, Path)):
        raw = str(transcript_dir).strip()
        if not raw:
            candidates = list(OPENCLAW_TRANSCRIPT_DIRS)
        elif os.pathsep in raw:
            candidates = [Path(item).expanduser() for item in raw.split(os.pathsep) if str(item).strip()]
        else:
            candidates = [Path(raw).expanduser()]
    else:
        candidates = [Path(item).expanduser() for item in transcript_dir if str(item).strip()]

    resolved: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates or [OPENCLAW_TRANSCRIPT_DIR]:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        resolved.append(candidate)
    return resolved or [OPENCLAW_TRANSCRIPT_DIR]


async def sync_projection_once(
    *,
    transcript_dir: Any = None,
    limit: int = DEFAULT_LIMIT,
    bootstrap_hours: int = DEFAULT_BOOTSTRAP_HOURS,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_runtime_dirs()
    await init_db()
    stats = ProjectionStats(dry_run=dry_run)
    client = PaperclipClient.from_config({})
    if not client.configured:
        raise PaperclipError('Paperclip 未启用或未配置，无法做自动投影')

    transcript_bases = [item for item in _resolve_transcript_dirs(transcript_dir) if item.exists()]
    if not transcript_bases:
        raise PaperclipError(
            '转录目录不存在: ' + ', '.join(str(item) for item in _resolve_transcript_dirs(transcript_dir))
        )

    state = _clean_state(await get_bridge_state_value(PROJECTOR_STATE_KEY))
    first_sync = not state.get('bootstrapped_at')
    stats.first_sync = first_sync

    records: list[AgentCollaborationRecord] = []
    for transcript_base in transcript_bases:
        session_ids = sorted(path.stem for path in transcript_base.glob('*.jsonl'))
        records.extend(load_agent_collaboration_records(transcript_base, session_ids, limit=max(10, limit)))
    if first_sync:
        records = _filter_bootstrap_records(records, bootstrap_hours)
    collapsed_records = _filter_projectable_records(_collapse_records(records))
    collapsed_records.sort(key=lambda item: _safe_log_time(item.event_time) or datetime.min)
    if limit > 0:
        collapsed_records = collapsed_records[-max(10, limit):]
    stats.scanned_records = len(collapsed_records)

    grouped: dict[str, list[AgentCollaborationRecord]] = {}
    for record in collapsed_records:
        group_key = _projection_group_key(record)
        grouped.setdefault(group_key, []).append(record)
    stats.grouped_tasks = len(grouped)

    parent_bucket: dict[str, dict[str, Any]] = state.setdefault('parents', {})
    child_bucket: dict[str, dict[str, Any]] = state.setdefault('children', {})

    for group_key, group_records in sorted(
        grouped.items(),
        key=lambda item: _safe_log_time(item[1][0].source_user_time or item[1][0].event_time) or datetime.min,
    ):
        group_records.sort(key=lambda item: (_role_label(item.agent_id), item.task_label or item.agent_id or ''))
        parent_payload = {
            'title': _render_parent_title(group_records),
            'description': _render_parent_description(group_records),
            'status': _group_status(group_records),
            'priority': 'medium',
            'assignee_agent_id': '',
        }
        parent_digest = _payload_digest(parent_payload)
        parent_entry = parent_bucket.get(group_key) or {}
        parent_issue_id = str(parent_entry.get('issue_id') or '').strip()

        try:
            if not parent_issue_id:
                if dry_run:
                    parent_issue_id = f'dry-parent-{group_key}'
                else:
                    created_parent = client.create_issue(
                        title=parent_payload['title'],
                        description=parent_payload['description'],
                        assignee_agent_id=parent_payload['assignee_agent_id'],
                        priority=parent_payload['priority'],
                        status=parent_payload['status'],
                        use_default_assignee=False,
                    )
                    parent_issue_id = str(created_parent.get('id') or '').strip()
                parent_bucket[group_key] = {'issue_id': parent_issue_id, 'digest': parent_digest, 'updated_at': _now_iso()}
                stats.created_parents += 1
            elif parent_entry.get('digest') != parent_digest:
                if not dry_run:
                    try:
                        client.update_issue(
                            parent_issue_id,
                            title=parent_payload['title'],
                            description=parent_payload['description'],
                            status=parent_payload['status'],
                            priority=parent_payload['priority'],
                            assignee_agent_id=parent_payload['assignee_agent_id'],
                        )
                    except PaperclipError as exc:
                        if '404' not in str(exc):
                            raise
                        recreated_parent = client.create_issue(
                            title=parent_payload['title'],
                            description=parent_payload['description'],
                            assignee_agent_id=parent_payload['assignee_agent_id'],
                            priority=parent_payload['priority'],
                            status=parent_payload['status'],
                            use_default_assignee=False,
                        )
                        parent_issue_id = str(recreated_parent.get('id') or '').strip()
                parent_bucket[group_key] = {'issue_id': parent_issue_id, 'digest': parent_digest, 'updated_at': _now_iso()}
                stats.updated_parents += 1
            else:
                stats.skipped += 1
        except Exception as exc:
            stats.errors += 1
            logger.exception('同步父 issue 失败: group=%s err=%s', group_key, exc)
            continue

        for record in group_records:
            child_key = _projection_child_key(record)
            child_payload = {
                'title': _render_child_title(record),
                'description': _render_child_description(record),
                'status': _record_effective_status(record),
                'priority': 'medium',
                'assignee_agent_id': '',
                'parent_id': parent_issue_id or None,
            }
            child_digest = _payload_digest(child_payload)
            child_entry = child_bucket.get(child_key) or {}
            child_issue_id = str(child_entry.get('issue_id') or '').strip()

            try:
                if not child_issue_id:
                    if dry_run:
                        child_issue_id = f'dry-child-{child_key}'
                    else:
                        created_child = client.create_issue(
                            title=child_payload['title'],
                            description=child_payload['description'],
                            assignee_agent_id=child_payload['assignee_agent_id'],
                            priority=child_payload['priority'],
                            status=child_payload['status'],
                            parent_id=child_payload['parent_id'],
                            use_default_assignee=False,
                        )
                        child_issue_id = str(created_child.get('id') or '').strip()
                    child_bucket[child_key] = {
                        'issue_id': child_issue_id,
                        'group_key': group_key,
                        'digest': child_digest,
                        'updated_at': _now_iso(),
                    }
                    stats.created_children += 1
                elif child_entry.get('digest') != child_digest:
                    if not dry_run:
                        try:
                            client.update_issue(
                                child_issue_id,
                                title=child_payload['title'],
                                description=child_payload['description'],
                                status=child_payload['status'],
                                priority=child_payload['priority'],
                                assignee_agent_id=child_payload['assignee_agent_id'],
                                parent_id=child_payload['parent_id'],
                            )
                        except PaperclipError as exc:
                            if '404' not in str(exc):
                                raise
                            recreated_child = client.create_issue(
                                title=child_payload['title'],
                                description=child_payload['description'],
                                assignee_agent_id=child_payload['assignee_agent_id'],
                                priority=child_payload['priority'],
                                status=child_payload['status'],
                                parent_id=child_payload['parent_id'],
                                use_default_assignee=False,
                            )
                            child_issue_id = str(recreated_child.get('id') or '').strip()
                    child_bucket[child_key] = {
                        'issue_id': child_issue_id,
                        'group_key': group_key,
                        'digest': child_digest,
                        'updated_at': _now_iso(),
                    }
                    stats.updated_children += 1
                else:
                    stats.skipped += 1
            except Exception as exc:
                stats.errors += 1
                logger.exception('同步子 issue 失败: key=%s agent=%s err=%s', child_key, record.agent_id, exc)

    if not dry_run:
        state['bootstrapped_at'] = state.get('bootstrapped_at') or _now_iso()
        state['last_sync_at'] = _now_iso()
        await set_bridge_state_value(PROJECTOR_STATE_KEY, state)
    payload = stats.to_dict()
    payload['transcript_dirs'] = [str(item) for item in transcript_bases]
    return payload


async def watch_projection(
    *,
    transcript_dir: Any = None,
    limit: int = DEFAULT_LIMIT,
    bootstrap_hours: int = DEFAULT_BOOTSTRAP_HOURS,
    interval_seconds: int = 15,
) -> None:
    while True:
        try:
            result = await sync_projection_once(
                transcript_dir=transcript_dir,
                limit=limit,
                bootstrap_hours=bootstrap_hours,
                dry_run=False,
            )
            logger.info('Paperclip 自动投影同步完成: %s', json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            logger.exception('Paperclip 自动投影同步失败: %s', exc)
        await asyncio.sleep(max(5, int(interval_seconds)))
