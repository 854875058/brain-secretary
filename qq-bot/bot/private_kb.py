from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from bot.memory_center import remember_text, search_entries
from bot.runtime_paths import PROJECT_ROOT

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]{2,}|[\u4e00-\u9fff]{2,}")
STOPWORDS = {
    "这个",
    "那个",
    "一下",
    "我们",
    "你们",
    "然后",
    "还有",
    "已经",
    "现在",
    "需要",
    "可以",
    "项目",
    "处理",
    "问题",
    "方案",
}


def _normalize_text(text: str | None) -> str:
    raw = str(text or "").replace("\r", "\n")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return "\n".join(lines).strip()


def _extract_tokens(text: str | None) -> list[str]:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_RE.finditer(normalized):
        token = match.group(0).strip().lower()
        if not token or token in STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _score_text(query: str, title: str, content: str) -> int:
    normalized_query = _normalize_text(query).lower()
    normalized_title = _normalize_text(title).lower()
    normalized_content = _normalize_text(content).lower()
    if not normalized_query:
        return 0
    score = 0
    if normalized_query in normalized_title:
        score += 10
    if normalized_query in normalized_content:
        score += 6
    for token in _extract_tokens(normalized_query):
        if token in normalized_title:
            score += 4
        if token in normalized_content:
            score += 2
    return score


@dataclass(slots=True)
class KnowledgeHit:
    source: str
    title: str
    content: str
    score: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def summary(self) -> str:
        text = _normalize_text(self.content).replace("\n", " / ")
        if len(text) <= 160:
            return text
        return text[:160].rstrip() + "..."


class KnowledgeSource(Protocol):
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeHit]:
        ...


class MemoryLedgerKnowledgeSource:
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeHit]:
        hits: list[KnowledgeHit] = []
        for entry in search_entries(query, limit=max(limit, 1)):
            content = _normalize_text(entry.get("content"))
            score = _score_text(query, str(entry.get("category") or ""), content)
            if score <= 0:
                continue
            hits.append(
                KnowledgeHit(
                    source="memory-ledger",
                    title=f"{entry.get('category') or 'general'}:{entry.get('id') or ''}",
                    content=content,
                    score=score,
                    metadata={
                        "id": entry.get("id"),
                        "category": entry.get("category"),
                        "created_at": entry.get("created_at"),
                    },
                )
            )
        return hits[:limit]


class MarkdownKnowledgeSource:
    def __init__(self, paths: Iterable[Path]):
        self.paths = [Path(path) for path in paths]

    def _iter_files(self) -> list[Path]:
        files: list[Path] = []
        for raw_path in self.paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            if path.is_file():
                files.append(path)
                continue
            for file_path in sorted(path.rglob("*.md")):
                if file_path.is_file():
                    files.append(file_path)
        return files

    @staticmethod
    def _split_sections(path: Path) -> list[tuple[str, str]]:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []

        sections: list[tuple[str, str]] = []
        current_title = path.name
        current_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("#"):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = line.lstrip("#").strip() or path.name
                current_lines = []
                continue
            current_lines.append(line)
        if current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))
        return [(title, content) for title, content in sections if _normalize_text(content)]

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeHit]:
        hits: list[KnowledgeHit] = []
        for path in self._iter_files():
            for title, content in self._split_sections(path):
                score = _score_text(query, title, content)
                if score <= 0:
                    continue
                hits.append(
                    KnowledgeHit(
                        source="markdown",
                        title=f"{path.relative_to(PROJECT_ROOT)}::{title}",
                        content=content,
                        score=score,
                        metadata={"path": str(path.relative_to(PROJECT_ROOT))},
                    )
                )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]


class ProjectRegistryKnowledgeSource:
    def __init__(self, path: Path):
        self.path = Path(path)

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeHit]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        projects = payload.get("projects") if isinstance(payload, dict) else None
        if not isinstance(projects, list):
            return []

        hits: list[KnowledgeHit] = []
        for item in projects:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            aliases = ", ".join(str(alias).strip() for alias in item.get("aliases") or [] if str(alias).strip())
            content = "\n".join(
                [
                    f"name: {name}",
                    f"aliases: {aliases}",
                    f"repo_url: {item.get('repo_url') or ''}",
                    f"local_paths: {', '.join(item.get('local_paths') or [])}",
                    f"work_branch: {item.get('work_branch') or ''}",
                    f"agent_branch: {item.get('agent_branch') or ''}",
                    f"notes: {item.get('notes') or ''}",
                ]
            ).strip()
            score = _score_text(query, name, content)
            if score <= 0:
                continue
            hits.append(
                KnowledgeHit(
                    source="project-registry",
                    title=f"project:{name}",
                    content=content,
                    score=score,
                    metadata={"project_id": item.get("id"), "name": name},
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]


class CombinedPrivateKnowledgeBase:
    def __init__(self, sources: Iterable[KnowledgeSource]):
        self.sources = list(sources)

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeHit]:
        hits: list[KnowledgeHit] = []
        seen: set[tuple[str, str, str]] = set()
        for source in self.sources:
            for hit in source.retrieve(query, limit=limit):
                dedupe_key = (hit.source, hit.title, hit.summary)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                hits.append(hit)
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def render_context(self, query: str, *, limit: int = 6) -> str:
        hits = self.retrieve(query, limit=limit)
        if not hits:
            return ""
        lines = [
            "[私有知识库检索结果]",
            "以下内容来自本地沉淀的业务规则、项目记忆和注册信息；执行时优先遵守，如与本轮明确要求冲突，以本轮要求为准。",
        ]
        for hit in hits[:limit]:
            lines.append(f"- [{hit.source}] {hit.title}: {hit.summary}")
        return "\n".join(lines).strip()

    def remember(self, note: str, *, kind: str = "remember", source: str = "agentteam") -> dict[str, Any] | None:
        normalized = _normalize_text(note)
        if not normalized:
            return None
        return remember_text(normalized, kind=kind, source=source)


def build_default_private_kb() -> CombinedPrivateKnowledgeBase:
    return CombinedPrivateKnowledgeBase(
        [
            MemoryLedgerKnowledgeSource(),
            MarkdownKnowledgeSource([PROJECT_ROOT / "MEMORY.md", PROJECT_ROOT / "memory"]),
            ProjectRegistryKnowledgeSource(PROJECT_ROOT / "ops" / "project_registry.json"),
        ]
    )
