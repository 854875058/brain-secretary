from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bot.runtime_paths import PROJECT_ROOT

REGISTRY_PATH = PROJECT_ROOT / 'ops' / 'project_registry.json'
SPACE_RE = re.compile(r'\s+')
TOKEN_RE = re.compile(r'[A-Za-z0-9_./:-]{2,}|[\u4e00-\u9fff]{2,}')


def _normalize_text(text: str | None) -> str:
    return SPACE_RE.sub(' ', str(text or '')).strip().lower()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value or '').strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _extract_tokens(text: str | None) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_RE.finditer(normalized):
        token = match.group(0).strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def load_project_registry(path: str | Path | None = None) -> list[dict[str, Any]]:
    registry_path = Path(path or REGISTRY_PATH)
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding='utf-8'))
    except Exception:
        return []
    raw_projects = payload.get('projects') if isinstance(payload, dict) else None
    if not isinstance(raw_projects, list):
        return []

    projects: list[dict[str, Any]] = []
    for item in raw_projects:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        aliases = _dedupe([name, str(item.get('id') or '').strip(), *(item.get('aliases') or [])])
        local_paths = _dedupe([str(path).strip() for path in (item.get('local_paths') or [])])
        projects.append(
            {
                'id': str(item.get('id') or name).strip() or name,
                'name': name,
                'aliases': aliases,
                'repo_url': str(item.get('repo_url') or '').strip(),
                'default_branch': str(item.get('default_branch') or 'main').strip() or 'main',
                'preferred_work_branch': str(item.get('preferred_work_branch') or '').strip(),
                'local_paths': local_paths,
                'notes': str(item.get('notes') or '').strip(),
            }
        )
    return projects


def iter_registry_local_projects(path: str | Path | None = None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for project in load_project_registry(path):
        for local_path in project.get('local_paths') or []:
            candidate = Path(local_path).expanduser()
            if not candidate.exists() or not candidate.is_dir():
                continue
            items.append(
                {
                    'name': str(project.get('name') or '').strip(),
                    'path': str(candidate),
                    'description': f"项目注册表: {project.get('repo_url') or project.get('notes') or candidate}",
                }
            )
            break
    return items


def _match_score(project: dict[str, Any], message: str) -> int:
    normalized_message = _normalize_text(message)
    if not normalized_message:
        return 0
    tokens = _extract_tokens(normalized_message)
    score = 0

    repo_url = _normalize_text(project.get('repo_url'))
    if repo_url and repo_url in normalized_message:
        score += 24

    for alias in project.get('aliases') or []:
        normalized_alias = _normalize_text(alias)
        if not normalized_alias:
            continue
        if normalized_alias == normalized_message:
            score += 18
        elif normalized_alias in normalized_message:
            score += 12

    for local_path in project.get('local_paths') or []:
        normalized_path = _normalize_text(local_path)
        if normalized_path and normalized_path in normalized_message:
            score += 10

    haystacks = [_normalize_text(project.get('name')), repo_url, _normalize_text(project.get('notes'))]
    haystacks.extend(_normalize_text(alias) for alias in (project.get('aliases') or []))
    merged = ' '.join(part for part in haystacks if part)
    for token in tokens:
        if token and token in merged:
            score += 3
    return score


def match_registry_projects(message: str, limit: int = 3, path: str | Path | None = None) -> list[dict[str, Any]]:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for project in load_project_registry(path):
        score = _match_score(project, message)
        if score <= 0:
            continue
        ranked.append((score, project))
    ranked.sort(key=lambda item: (item[0], item[1].get('name') or ''), reverse=True)
    return [item for _, item in ranked[: max(1, limit)]]


def build_project_registry_context(message: str, limit: int = 3, path: str | Path | None = None) -> str:
    matches = match_registry_projects(message, limit=limit, path=path)
    if not matches:
        return ''
    lines = [
        '[项目注册表上下文]',
        '以下项目是本轮问题最可能指向的真源；若已命中，默认按这里理解项目位置/仓库/分支，不要再让用户重复报项目在哪。',
    ]
    for project in matches:
        alias_text = '、'.join(project.get('aliases') or [])
        local_paths = project.get('local_paths') or []
        lines.append(f"- 项目: {project.get('name')}")
        if alias_text:
            lines.append(f"  - 别名: {alias_text}")
        if project.get('repo_url'):
            lines.append(f"  - 仓库: {project['repo_url']}")
        if project.get('default_branch'):
            lines.append(f"  - 默认分支: {project['default_branch']}")
        if project.get('preferred_work_branch'):
            lines.append(f"  - 首选工作分支: {project['preferred_work_branch']}")
        if local_paths:
            lines.append(f"  - 本地路径候选: {'；'.join(local_paths)}")
        if project.get('notes'):
            lines.append(f"  - 说明: {project['notes']}")
    return '\n'.join(lines).strip()


def render_registry_markdown(path: str | Path | None = None) -> str:
    projects = load_project_registry(path)
    lines = [
        '# 项目注册表',
        '',
        '这里记录当前已知项目的别名、仓库、分支与本地路径候选。',
        '用户提到这些别名时，默认按这里定位；只有这里没有命中，或信息明显失效时，才向用户追问。',
        '',
    ]
    for project in projects:
        lines.append(f"## {project.get('name')}")
        lines.append('')
        aliases = '、'.join(project.get('aliases') or []) or '（无）'
        lines.append(f"- 别名：{aliases}")
        if project.get('repo_url'):
            lines.append(f"- 仓库：`{project['repo_url']}`")
        if project.get('default_branch'):
            lines.append(f"- 默认分支：`{project['default_branch']}`")
        if project.get('preferred_work_branch'):
            lines.append(f"- 首选工作分支：`{project['preferred_work_branch']}`")
        local_paths = project.get('local_paths') or []
        if local_paths:
            lines.append('- 本地路径候选：')
            for local_path in local_paths:
                lines.append(f"  - `{local_path}`")
        if project.get('notes'):
            lines.append(f"- 说明：{project['notes']}")
        lines.append('')
    return '\n'.join(lines).strip() + '\n'
