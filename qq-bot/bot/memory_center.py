from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bot.runtime_paths import PROJECT_ROOT

MEMORY_ROOT = PROJECT_ROOT / 'memory'
LEDGER_PATH = MEMORY_ROOT / 'qq-memory-ledger.jsonl'
TOPIC_FILES = {
    'rule': MEMORY_ROOT / 'work-rules.md',
    'preference': MEMORY_ROOT / 'user-preferences.md',
    'workflow': MEMORY_ROOT / 'workflow-patterns.md',
    'project': MEMORY_ROOT / 'project-context.md',
    'general': MEMORY_ROOT / 'general-notes.md',
}
TOPIC_TITLES = {
    'rule': '工作规则',
    'preference': '用户偏好',
    'workflow': '工作流/闭环',
    'project': '项目上下文',
    'general': '通用记录',
}
CATEGORY_KEYWORDS = {
    'rule': ['以后', '默认', '优先', '不要', '必须', '规则', '规范', '约定', '记住', '按这个来', '固定', '习惯'],
    'preference': ['喜欢', '不喜欢', '偏好', '称呼', '口吻', '语气', '风格', '别叫', '叫我'],
    'workflow': ['闭环', '自助进化', '巡检', '告警', '验收', '回推', '同步', '自动', '流程'],
    'project': ['项目', '仓库', '分支', 'git', '服务器', 'windows', 'openclaw', 'qq', 'napcat', '桥接'],
}
QUERY_STOPWORDS = {
    '这个', '那个', '一下', '一下子', '一个', '一种', '我们', '你们', '然后', '还有', '就是', '已经',
    '现在', '以后', '需要', '可以', '一下吧', '帮我', '帮忙', '记住', '处理', '问题', '功能', '方案',
}
DUPLICATE_WINDOW_DAYS = 14
MAX_RENDER_ITEMS = 10


def ensure_memory_files() -> None:
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    if not LEDGER_PATH.exists():
        LEDGER_PATH.write_text('', encoding='utf-8')
    for category, path in TOPIC_FILES.items():
        if path.exists():
            continue
        title = TOPIC_TITLES[category]
        path.write_text(
            f'# {title}\n\n'
            '自动沉淀来自 QQ / 桥接层的长期记忆，按时间追加。\n',
            encoding='utf-8',
        )


def _normalize_text(text: str | None) -> str:
    raw = str(text or '').replace('\r', '\n')
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return '\n'.join(lines).strip()


TOKEN_RE = re.compile(r'[A-Za-z0-9_./:-]{2,}|[\u4e00-\u9fff]{2,}')


def _extract_tokens(text: str | None) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_RE.finditer(normalized):
        token = match.group(0).strip().lower()
        if not token or token in QUERY_STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _detect_category(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return 'general'
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return 'general'


def _load_entries(limit: int | None = None) -> list[dict[str, Any]]:
    ensure_memory_files()
    if not LEDGER_PATH.exists():
        return []
    lines = LEDGER_PATH.read_text(encoding='utf-8', errors='replace').splitlines()
    if limit is not None and limit > 0:
        lines = lines[-limit:]
    items: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _entry_summary(text: str, limit: int = 110) -> str:
    normalized = _normalize_text(text).replace('\n', ' / ')
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + '…'


def _entry_markdown(entry: dict[str, Any]) -> str:
    timestamp = str(entry.get('created_at') or '').strip() or datetime.now().isoformat()
    source = str(entry.get('source') or 'qq').strip()
    kind = str(entry.get('kind') or 'remember').strip()
    content = _normalize_text(entry.get('content'))
    lines = [f'- {timestamp} | source={source} | kind={kind}']
    if entry.get('chat_type'):
        lines.append(f'  - chat_type: {entry["chat_type"]}')
    if entry.get('user_qq') is not None:
        lines.append(f'  - user_qq: {entry["user_qq"]}')
    if entry.get('group_id') is not None:
        lines.append(f'  - group_id: {entry["group_id"]}')
    lines.append(f'  - content: {content}')
    return '\n'.join(lines) + '\n'


def _find_duplicate(content_hash: str, *, category: str, kind: str) -> dict[str, Any] | None:
    threshold = datetime.now().astimezone() - timedelta(days=DUPLICATE_WINDOW_DAYS)
    for entry in reversed(_load_entries(limit=240)):
        if str(entry.get('content_hash') or '') != content_hash:
            continue
        if str(entry.get('category') or '') != category:
            continue
        if str(entry.get('kind') or '') != kind:
            continue
        created_at = str(entry.get('created_at') or '').strip()
        if not created_at:
            return entry
        try:
            parsed = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except Exception:
            return entry
        if parsed >= threshold:
            return entry
    return None


def remember_text(
    content: str,
    *,
    kind: str = 'remember',
    source: str = 'qq',
    user_qq: int | None = None,
    group_id: int | None = None,
    chat_type: str = 'private',
    agent_id: str | None = None,
) -> dict[str, Any]:
    ensure_memory_files()
    normalized = _normalize_text(content)
    if not normalized:
        raise ValueError('content 不能为空')

    category = _detect_category(normalized)
    content_hash = hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]
    duplicate = _find_duplicate(content_hash, category=category, kind=str(kind or 'remember'))
    if duplicate is not None:
        result = dict(duplicate)
        result['duplicate'] = True
        result['topic_path'] = str(TOPIC_FILES.get(category, TOPIC_FILES['general']))
        result['daily_path'] = str(MEMORY_ROOT / f"{datetime.now().date().isoformat()}.md")
        return result

    now = datetime.now().astimezone()
    entry = {
        'id': f'mem-{now.strftime("%Y%m%d%H%M%S")}-{content_hash[:6]}',
        'created_at': now.isoformat(),
        'category': category,
        'kind': str(kind or 'remember').strip() or 'remember',
        'source': str(source or 'qq').strip() or 'qq',
        'user_qq': int(user_qq) if user_qq is not None else None,
        'group_id': int(group_id) if group_id is not None else None,
        'chat_type': str(chat_type or 'private').strip() or 'private',
        'agent_id': str(agent_id or '').strip(),
        'content': normalized,
        'summary': _entry_summary(normalized),
        'content_hash': content_hash,
        'tokens': _extract_tokens(normalized)[:18],
    }

    with LEDGER_PATH.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')

    daily_path = MEMORY_ROOT / f'{now.date().isoformat()}.md'
    if not daily_path.exists():
        daily_path.write_text(f'# {now.date().isoformat()}\n\n', encoding='utf-8')
    with daily_path.open('a', encoding='utf-8') as handle:
        handle.write('## QQ 记忆固化\n\n') if daily_path.stat().st_size <= len(f'# {now.date().isoformat()}\n\n'.encode('utf-8')) else None
        handle.write(_entry_markdown(entry) + '\n')

    topic_path = TOPIC_FILES.get(category, TOPIC_FILES['general'])
    with topic_path.open('a', encoding='utf-8') as handle:
        handle.write(_entry_markdown(entry) + '\n')

    result = dict(entry)
    result['duplicate'] = False
    result['daily_path'] = str(daily_path)
    result['topic_path'] = str(topic_path)
    return result


def list_recent_entries(limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
    entries = _load_entries(limit=max(limit * 8, 80))
    if category:
        entries = [entry for entry in entries if str(entry.get('category') or '') == category]
    entries = entries[-max(1, limit):]
    entries.reverse()
    return entries


def search_entries(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    text = _normalize_text(keyword)
    if not text:
        return []
    query_tokens = _extract_tokens(text)
    results: list[tuple[int, int, dict[str, Any]]] = []
    for index, entry in enumerate(reversed(_load_entries(limit=400))):
        content = str(entry.get('content') or '')
        score = 0
        if text in content:
            score += 8
        for token in query_tokens:
            if token and token in content.lower():
                score += 3
        if score <= 0:
            continue
        results.append((score, -index, entry))
    results.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [entry for _, _, entry in results[:max(1, limit)]]


def _score_entry(entry: dict[str, Any], message: str) -> int:
    content = str(entry.get('content') or '')
    category = str(entry.get('category') or 'general')
    kind = str(entry.get('kind') or 'remember')
    score = 0
    if category in {'rule', 'preference', 'workflow'}:
        score += 3
    if kind == 'remember':
        score += 1

    query_tokens = _extract_tokens(message)
    haystack = content.lower()
    for token in query_tokens:
        if token in haystack:
            score += 4
    if message and _normalize_text(message)[:40] in content:
        score += 6
    return score


def build_memory_context(message: str, limit: int = 6) -> str:
    entries = _load_entries(limit=240)
    if not entries:
        return ''
    normalized = _normalize_text(message)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, entry in enumerate(reversed(entries)):
        score = _score_entry(entry, normalized)
        if score <= 0:
            continue
        scored.append((score, -index, entry))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for _, _, entry in scored[: max(limit * 3, 12)]:
        entry_id = str(entry.get('id') or '')
        if entry_id and entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        selected.append(entry)
        if len(selected) >= limit:
            break

    if not selected:
        for entry in reversed(entries):
            if str(entry.get('category') or '') not in {'rule', 'preference', 'workflow'}:
                continue
            entry_id = str(entry.get('id') or '')
            if entry_id and entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            selected.append(entry)
            if len(selected) >= min(limit, 4):
                break

    if not selected:
        return ''

    lines = ['[本地长期记忆上下文]', '以下内容来自桥接层已固化记忆，回答时优先遵守；若与用户本轮明确要求冲突，以本轮要求为准。']
    for entry in selected[:limit]:
        category = str(entry.get('category') or 'general')
        created_at = str(entry.get('created_at') or '')[:10]
        summary = str(entry.get('summary') or '')
        lines.append(f'- [{category}] {created_at}: {summary}')
    return '\n'.join(lines).strip()


def render_recent_entries(limit: int = 8) -> str:
    entries = list_recent_entries(limit=limit)
    if not entries:
        return '当前还没有桥接层长期记忆。'
    lines = ['最近记忆：']
    for entry in entries[:MAX_RENDER_ITEMS]:
        lines.append(
            f"- #{entry.get('id')} [{entry.get('category')}] {str(entry.get('created_at') or '')[:16]} {entry.get('summary') or ''}"
        )
    return '\n'.join(lines)


def render_search_results(keyword: str, limit: int = 8) -> str:
    entries = search_entries(keyword, limit=limit)
    if not entries:
        return f"没找到和“{keyword}”相关的桥接层记忆。"
    lines = [f'记忆搜索结果：{keyword}']
    for entry in entries[:MAX_RENDER_ITEMS]:
        lines.append(
            f"- #{entry.get('id')} [{entry.get('category')}] {str(entry.get('created_at') or '')[:16]} {entry.get('summary') or ''}"
        )
    return '\n'.join(lines)
