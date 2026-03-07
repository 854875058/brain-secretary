from __future__ import annotations

import ast
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.task_db import DB_PATH

LOG_ENTRY_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<logger>.+?) - (?P<level>[A-Z]+) - (?P<message>.*)$")
TRANSCRIPT_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")
WHITESPACE_RE = re.compile(r"\s+")
CHILD_SESSION_KEY_RE = re.compile(r"agent:(?P<agent_id>[^:]+):subagent:(?P<child_key>[^\s]+)")
SUBAGENT_TASK_RE = re.compile(r"\[Subagent Task\]:\s*(.*)", re.DOTALL)


@dataclass
class ChatRecord:
    qq_time: str
    user_id: int
    nickname: str
    chat_type: str
    qq_message_id: int | None
    qq_text: str
    session_label: str
    reply_time: str | None = None
    reply_text: str | None = None
    reply_source: str | None = None
    transcript_path: str | None = None
    transcript_session_id: str | None = None
    matched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptPair:
    user_time: str
    user_text: str
    reply_time: str | None
    reply_text: str | None
    transcript_path: str
    transcript_session_id: str | None


@dataclass
class AgentCollaborationRecord:
    event_time: str
    agent_id: str | None
    task_label: str | None
    task_text: str | None
    brain_note: str | None = None
    spawn_status: str | None = None
    spawn_error: str | None = None
    child_session_key: str | None = None
    child_session_id: str | None = None
    child_session_path: str | None = None
    completion_status: str | None = None
    completion_result: str | None = None
    child_task_excerpt: str | None = None
    child_final_reply: str | None = None
    child_error: str | None = None
    transcript_session_id: str | None = None
    transcript_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", (text or "")).strip()


def strip_transcript_prefix(text: str) -> str:
    cleaned = text or ""
    while True:
        next_text = TRANSCRIPT_PREFIX_RE.sub("", cleaned, count=1)
        if next_text == cleaned:
            return cleaned.strip()
        cleaned = next_text


def parse_log_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S,%f")


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def format_display_timestamp(value: str | None) -> str | None:
    parsed = parse_iso_timestamp(value)
    if parsed is None:
        return value
    try:
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    except Exception:
        return value


def normalize_date_input(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        return None


def same_date_from_log(ts: str | None, date_str: str | None) -> bool:
    normalized_date = normalize_date_input(date_str)
    if not normalized_date:
        return True
    if not ts:
        return False
    return str(ts).startswith(normalized_date)


def same_date_from_iso(ts: str | None, date_str: str | None) -> bool:
    normalized_date = normalize_date_input(date_str)
    if not normalized_date:
        return True
    formatted = format_display_timestamp(ts)
    return same_date_from_log(formatted, normalized_date)


def texts_match(left: str, right: str) -> bool:
    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if normalized_left == normalized_right:
        return True
    if normalized_left.startswith("[CQ:image") and normalized_right.startswith("[CQ:image"):
        return True
    if normalized_left.startswith("[CQ:face") and normalized_right.startswith("[CQ:face"):
        return True
    return False


def extract_message_text(payload: dict[str, Any]) -> str:
    raw_message = payload.get("raw_message")
    if isinstance(raw_message, str) and raw_message.strip():
        return raw_message.strip()

    message = payload.get("message")
    parts: list[str] = []
    if isinstance(message, str) and message.strip():
        parts.append(message.strip())
    elif isinstance(message, list):
        for item in message:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            data = item.get("data") or {}
            if item_type == "text":
                text = data.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif item_type and isinstance(data, dict):
                if item_type == "image":
                    parts.append(f"[CQ:image,file={data.get('file') or ''}]")
                else:
                    parts.append(f"[CQ:{item_type}]")
    return "\n".join(part for part in parts if part).strip()


def extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.rstrip())
    return "\n".join(parts).strip()


def extract_assistant_text_and_tool_calls(content: Any) -> tuple[list[str], list[dict[str, Any]]]:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.rstrip())
            elif item_type == "toolCall":
                tool_calls.append(item)
    elif isinstance(content, str) and content.strip():
        text_parts.append(content.strip())
    return text_parts, tool_calls


def iter_log_entries(log_path: Path):
    if not log_path.exists():
        return

    current = None
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            match = LOG_ENTRY_RE.match(line)
            if match:
                if current is not None:
                    current["full_message"] = "\n".join(current.pop("lines"))
                    yield current
                current = {
                    "timestamp": match.group("ts"),
                    "logger": match.group("logger"),
                    "level": match.group("level"),
                    "lines": [match.group("message")],
                }
                continue
            if current is not None:
                current["lines"].append(line)
        if current is not None:
            current["full_message"] = "\n".join(current.pop("lines"))
            yield current


def parse_received_message(entry: dict[str, Any]) -> dict[str, Any] | None:
    message = entry["full_message"]
    if not message.startswith("收到消息: "):
        return None

    payload_text = message[len("收到消息: "):]
    try:
        payload = ast.literal_eval(payload_text)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("post_type") != "message":
        return None

    message_type = payload.get("message_type")
    if message_type not in {"private", "group"}:
        return None

    user_id = payload.get("user_id")
    if user_id is None:
        return None

    return {
        "timestamp": entry["timestamp"],
        "chat_type": message_type,
        "user_id": int(user_id),
        "group_id": int(payload.get("group_id") or 0),
        "self_id": str(payload.get("self_id") or "bot"),
        "nickname": str((payload.get("sender") or {}).get("nickname") or ""),
        "message_id": int(payload.get("message_id")) if payload.get("message_id") is not None else None,
        "text": extract_message_text(payload),
    }


def parse_sent_message(entry: dict[str, Any]) -> dict[str, Any] | None:
    message = entry["full_message"]
    if entry["logger"] != "bot.qq_sender":
        return None

    if message.startswith("发送私聊消息到 "):
        prefix, _, text = message.partition(": ")
        try:
            user_id = int(prefix.replace("发送私聊消息到 ", "").strip())
        except Exception:
            return None
        return {
            "timestamp": entry["timestamp"],
            "chat_type": "private",
            "user_id": user_id,
            "group_id": 0,
            "text": text.strip(),
            "truncated": True,
        }

    if message.startswith("发送群聊消息到 "):
        prefix, _, text = message.partition(": ")
        try:
            group_id = int(prefix.replace("发送群聊消息到 ", "").strip())
        except Exception:
            return None
        return {
            "timestamp": entry["timestamp"],
            "chat_type": "group",
            "user_id": 0,
            "group_id": group_id,
            "text": text.strip(),
            "truncated": True,
        }

    return None


def build_session_label(self_id: str, chat_type: str, user_id: int, group_id: int = 0) -> str:
    if chat_type == "private":
        return f"qq-{self_id}-private-{user_id}"
    return f"qq-{self_id}-group-{group_id}"


def load_received_messages(log_path: Path, user_id: int | None, chat_type: str, limit: int, date: str | None = None, group_id: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in iter_log_entries(log_path) or []:
        parsed = parse_received_message(entry)
        if not parsed:
            continue
        if parsed["chat_type"] != chat_type:
            continue
        if chat_type == "private":
            if user_id is not None and parsed["user_id"] != user_id:
                continue
        else:
            if group_id is not None and parsed["group_id"] != group_id:
                continue
            if user_id is not None and parsed["user_id"] != user_id:
                continue
        if not same_date_from_log(parsed["timestamp"], date):
            continue
        records.append(parsed)
    return records[-limit:]


def load_sent_fallbacks(log_path: Path, user_id: int | None, chat_type: str, date: str | None = None, group_id: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in iter_log_entries(log_path) or []:
        parsed = parse_sent_message(entry)
        if not parsed:
            continue
        if parsed["chat_type"] != chat_type:
            continue
        if chat_type == "private":
            if user_id is not None and parsed["user_id"] != user_id:
                continue
        elif group_id is not None and parsed["group_id"] != group_id:
            continue
        if not same_date_from_log(parsed["timestamp"], date):
            continue
        records.append(parsed)
    return records


def build_history_overview(log_path: Path, user_id: int | None, date: str | None = None) -> dict[str, Any]:
    total_counts = {"private": 0, "group": 0}
    user_counts = {"private": 0, "group": 0}
    recent_group_ids: list[int] = []
    seen_group_ids: set[int] = set()

    for entry in iter_log_entries(log_path) or []:
        parsed = parse_received_message(entry)
        if not parsed:
            continue
        if not same_date_from_log(parsed["timestamp"], date):
            continue

        current_chat_type = parsed["chat_type"]
        total_counts[current_chat_type] = total_counts.get(current_chat_type, 0) + 1

        if user_id is not None and parsed["user_id"] == user_id:
            user_counts[current_chat_type] = user_counts.get(current_chat_type, 0) + 1
            if current_chat_type == "group" and parsed["group_id"] and parsed["group_id"] not in seen_group_ids:
                seen_group_ids.add(parsed["group_id"])
                recent_group_ids.append(parsed["group_id"])

    return {
        "date": normalize_date_input(date),
        "total_counts": total_counts,
        "user_counts": user_counts,
        "recent_group_ids": recent_group_ids[:8],
    }


def is_internal_runtime_context(text: str) -> bool:
    return "OpenClaw runtime context (internal):" in (text or "") and "[Internal task completion event]" in (text or "")


def load_transcript_pairs(transcript_dir: Path) -> list[TranscriptPair]:
    pairs: list[TranscriptPair] = []
    if not transcript_dir.exists():
        return pairs

    for transcript_path in sorted(transcript_dir.glob("*.jsonl")):
        try:
            lines = transcript_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        current_session_id: str | None = None
        current_user_time: str | None = None
        current_user_text: str | None = None
        current_reply_time: str | None = None
        current_reply_parts: list[str] = []

        for raw_line in lines:
            try:
                item = json.loads(raw_line)
            except Exception:
                continue

            if item.get("type") == "session":
                current_session_id = str(item.get("id") or current_session_id or "") or None
                continue

            if item.get("type") != "message":
                continue

            message = item.get("message") or {}
            role = message.get("role")
            timestamp = item.get("timestamp") or message.get("timestamp")

            if role == "user":
                user_text = strip_transcript_prefix(extract_content_text(message.get("content")))
                if not user_text or is_internal_runtime_context(user_text):
                    continue
                if current_user_text is not None:
                    pairs.append(
                        TranscriptPair(
                            user_time=current_user_time or "",
                            user_text=current_user_text,
                            reply_time=current_reply_time,
                            reply_text="\n\n".join(part for part in current_reply_parts if part).strip() or None,
                            transcript_path=str(transcript_path),
                            transcript_session_id=current_session_id,
                        )
                    )
                current_user_time = timestamp or ""
                current_user_text = user_text
                current_reply_time = None
                current_reply_parts = []
                continue

            if role == "assistant" and current_user_text is not None:
                reply_text = strip_transcript_prefix(extract_content_text(message.get("content")))
                if reply_text:
                    current_reply_parts.append(reply_text)
                    current_reply_time = timestamp or current_reply_time

        if current_user_text is not None:
            pairs.append(
                TranscriptPair(
                    user_time=current_user_time or "",
                    user_text=current_user_text,
                    reply_time=current_reply_time,
                    reply_text="\n\n".join(part for part in current_reply_parts if part).strip() or None,
                    transcript_path=str(transcript_path),
                    transcript_session_id=current_session_id,
                )
            )
    return pairs


def match_transcript_pair(incoming: dict[str, Any], transcript_pairs: list[TranscriptPair], start_index: int) -> tuple[TranscriptPair | None, int]:
    incoming_text = normalize_text(incoming.get("text") or "")
    for index in range(start_index, len(transcript_pairs)):
        pair = transcript_pairs[index]
        if not texts_match(pair.user_text, incoming_text):
            continue
        return pair, index + 1
    return None, start_index


def match_sent_fallback(incoming: dict[str, Any], sent_fallbacks: list[dict[str, Any]], start_index: int) -> tuple[dict[str, Any] | None, int]:
    incoming_time = parse_log_timestamp(incoming["timestamp"])
    for index in range(start_index, len(sent_fallbacks)):
        item = sent_fallbacks[index]
        if item["chat_type"] != incoming["chat_type"]:
            continue
        if incoming["chat_type"] == "private" and item["user_id"] != incoming["user_id"]:
            continue
        if incoming["chat_type"] == "group" and item["group_id"] != incoming["group_id"]:
            continue
        delta_seconds = (parse_log_timestamp(item["timestamp"]) - incoming_time).total_seconds()
        if delta_seconds < 0:
            continue
        if delta_seconds > 900:
            break
        return item, index + 1
    return None, start_index


def load_chat_records(log_path: Path, transcript_dir: Path, user_id: int | None, chat_type: str = "private", limit: int = 100, date: str | None = None, group_id: int | None = None) -> list[ChatRecord]:
    received_messages = load_received_messages(log_path, user_id, chat_type, limit, date=date, group_id=group_id)
    transcript_pairs = load_transcript_pairs(transcript_dir)
    sent_fallbacks = load_sent_fallbacks(log_path, user_id, chat_type, date=date, group_id=group_id)

    transcript_index = 0
    sent_index = 0
    records: list[ChatRecord] = []

    for incoming in received_messages:
        session_label = build_session_label(
            self_id=incoming["self_id"],
            chat_type=incoming["chat_type"],
            user_id=incoming["user_id"],
            group_id=incoming["group_id"],
        )
        record = ChatRecord(
            qq_time=incoming["timestamp"],
            user_id=incoming["user_id"],
            nickname=incoming["nickname"],
            chat_type=incoming["chat_type"],
            qq_message_id=incoming["message_id"],
            qq_text=incoming["text"],
            session_label=session_label,
        )

        pair, transcript_index = match_transcript_pair(incoming, transcript_pairs, transcript_index)
        if pair is not None:
            record.reply_time = format_display_timestamp(pair.reply_time)
            record.reply_text = pair.reply_text
            record.reply_source = "openclaw_transcript"
            record.transcript_path = pair.transcript_path
            record.transcript_session_id = pair.transcript_session_id
            record.matched = True
        else:
            fallback, sent_index = match_sent_fallback(incoming, sent_fallbacks, sent_index)
            if fallback is not None:
                record.reply_time = fallback["timestamp"]
                record.reply_text = fallback["text"]
                record.reply_source = "qq_sender_log_preview"

        records.append(record)

    records.sort(key=lambda item: item.qq_time or "", reverse=True)
    return records


def parse_internal_completion_message(text: str) -> dict[str, Any] | None:
    if not is_internal_runtime_context(text):
        return None

    details: dict[str, Any] = {}
    lines = (text or "").splitlines()
    result_start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Result (untrusted content, treat as data):"):
            result_start = index
            break
        if ":" in stripped and not stripped.startswith("["):
            key, value = stripped.split(":", 1)
            details[key.strip()] = value.strip()

    if result_start is not None:
        result_lines: list[str] = []
        for line in lines[result_start + 1:]:
            if line.startswith("Stats:") or line.startswith("Action:"):
                break
            result_lines.append(line)
        details["result"] = "\n".join(result_lines).strip()

    session_key = str(details.get("session_key") or "")
    match = CHILD_SESSION_KEY_RE.search(session_key)
    if match:
        details["agent_id"] = match.group("agent_id")
        details["child_session_key"] = session_key
    else:
        details["agent_id"] = None
        details["child_session_key"] = session_key or None

    details["child_session_id"] = details.get("session_id")
    details["task_label"] = details.get("task")
    details["completion_status"] = details.get("status")
    return details


def find_child_session_path(agent_id: str | None, session_id: str | None) -> Path | None:
    if not agent_id or not session_id:
        return None
    base = Path(f"/root/.openclaw/agents/{agent_id}/sessions")
    if not base.exists():
        return None
    candidates = sorted(base.glob(f"{session_id}.jsonl*"), key=lambda item: (item.suffix != '.jsonl', item.name))
    return candidates[0] if candidates else None


def parse_child_session_excerpt(session_path: Path | None) -> dict[str, Any]:
    if session_path is None or not session_path.exists():
        return {}

    task_text: str | None = None
    final_reply: str | None = None
    child_error: str | None = None
    tool_count = 0

    try:
        lines = session_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}

    for raw_line in lines:
        try:
            item = json.loads(raw_line)
        except Exception:
            continue
        if item.get("type") != "message":
            continue
        message = item.get("message") or {}
        role = message.get("role")
        if role == "user":
            text = extract_content_text(message.get("content"))
            match = SUBAGENT_TASK_RE.search(text)
            if match and task_text is None:
                task_text = match.group(1).strip()
        elif role == "assistant":
            text_parts, tool_calls = extract_assistant_text_and_tool_calls(message.get("content"))
            tool_count += len(tool_calls)
            if text_parts:
                candidate = "\n".join(part for part in text_parts if part).strip()
                if candidate and candidate != "NO_REPLY":
                    final_reply = candidate
            error_message = message.get("errorMessage")
            if isinstance(error_message, str) and error_message.strip():
                child_error = error_message.strip()

    return {
        "task_text": task_text,
        "final_reply": final_reply,
        "error": child_error,
        "tool_count": tool_count,
    }


def load_agent_collaboration_records(transcript_dir: Path, transcript_session_ids: list[str], date: str | None = None, limit: int = 100) -> list[AgentCollaborationRecord]:
    records: list[AgentCollaborationRecord] = []
    if not transcript_session_ids:
        return records

    for session_id in sorted(set(item for item in transcript_session_ids if item)):
        transcript_path = transcript_dir / f"{session_id}.jsonl"
        if not transcript_path.exists():
            continue

        pending_by_call_id: dict[str, AgentCollaborationRecord] = {}
        pending_by_session_key: dict[str, AgentCollaborationRecord] = {}

        try:
            lines = transcript_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        for raw_line in lines:
            try:
                item = json.loads(raw_line)
            except Exception:
                continue
            if item.get("type") != "message":
                continue

            message = item.get("message") or {}
            role = message.get("role")
            item_timestamp = item.get("timestamp")
            display_time = format_display_timestamp(item_timestamp) or str(item_timestamp or "")

            if role == "assistant":
                text_parts, tool_calls = extract_assistant_text_and_tool_calls(message.get("content"))
                brain_note = "\n".join(part for part in text_parts if part).strip() or None
                for tool_call in tool_calls:
                    if tool_call.get("name") != "sessions_spawn":
                        continue
                    arguments = tool_call.get("arguments") or {}
                    record = AgentCollaborationRecord(
                        event_time=display_time,
                        agent_id=str(arguments.get("agentId") or "") or None,
                        task_label=str(arguments.get("label") or "") or None,
                        task_text=str(arguments.get("task") or "") or None,
                        brain_note=brain_note,
                        spawn_status="requested",
                        transcript_session_id=session_id,
                        transcript_path=str(transcript_path),
                    )
                    pending_by_call_id[str(tool_call.get("id") or "")] = record
                    records.append(record)
                continue

            if role == "toolResult" and message.get("toolName") == "sessions_spawn":
                tool_call_id = str(message.get("toolCallId") or "")
                record = pending_by_call_id.get(tool_call_id)
                if record is None:
                    continue
                details = message.get("details") or {}
                record.spawn_status = str(details.get("status") or record.spawn_status or "") or record.spawn_status
                record.spawn_error = str(details.get("error") or "") or record.spawn_error
                child_session_key = str(details.get("childSessionKey") or "") or None
                if child_session_key:
                    record.child_session_key = child_session_key
                    pending_by_session_key[child_session_key] = record
                continue

            if role == "user":
                user_text = extract_content_text(message.get("content"))
                internal = parse_internal_completion_message(user_text)
                if not internal:
                    continue
                event_time = format_display_timestamp(item_timestamp) or display_time
                child_session_key = internal.get("child_session_key")
                record = pending_by_session_key.get(str(child_session_key or "")) if child_session_key else None
                if record is None:
                    record = AgentCollaborationRecord(
                        event_time=event_time,
                        agent_id=internal.get("agent_id"),
                        task_label=internal.get("task_label"),
                        task_text=None,
                        transcript_session_id=session_id,
                        transcript_path=str(transcript_path),
                    )
                    records.append(record)
                    if child_session_key:
                        pending_by_session_key[str(child_session_key)] = record
                record.event_time = event_time
                record.agent_id = internal.get("agent_id") or record.agent_id
                record.child_session_key = internal.get("child_session_key") or record.child_session_key
                record.child_session_id = internal.get("child_session_id") or record.child_session_id
                record.task_label = internal.get("task_label") or record.task_label
                record.completion_status = internal.get("completion_status") or record.completion_status
                record.completion_result = internal.get("result") or record.completion_result

                child_session_path = find_child_session_path(record.agent_id, record.child_session_id)
                if child_session_path is not None:
                    record.child_session_path = str(child_session_path)
                    excerpt = parse_child_session_excerpt(child_session_path)
                    record.child_task_excerpt = excerpt.get("task_text") or record.child_task_excerpt
                    record.child_final_reply = excerpt.get("final_reply") or record.child_final_reply
                    record.child_error = excerpt.get("error") or record.child_error

    filtered = [
        item for item in records
        if same_date_from_log(item.event_time, date)
    ]
    filtered.sort(key=lambda item: item.event_time or "", reverse=True)
    return filtered[:limit]


def build_chat_history_payload(
    log_path: Path,
    transcript_dir: Path,
    user_id: int | None,
    chat_type: str = "private",
    limit: int = 100,
    date: str | None = None,
    group_id: int | None = None,
    task_status: str | None = None,
    task_agent: str | None = None,
    task_query: str | None = None,
    agent_id: str | None = None,
    agent_status: str | None = None,
    agent_query: str | None = None,
    show_completed: bool = False,
) -> dict[str, Any]:
    normalized_date = normalize_date_input(date)
    records = load_chat_records(
        log_path=log_path,
        transcript_dir=transcript_dir,
        user_id=user_id,
        chat_type=chat_type,
        limit=limit,
        date=normalized_date,
        group_id=group_id,
    )
    transcript_session_ids = [record.transcript_session_id for record in records if record.transcript_session_id]
    agent_records = load_agent_collaboration_records(
        transcript_dir=transcript_dir,
        transcript_session_ids=transcript_session_ids,
        date=normalized_date,
        limit=limit,
    )

    normalized_agent_id = str(agent_id or '').strip() or None
    normalized_agent_status = str(agent_status or '').strip() or None
    normalized_agent_query = normalize_text(agent_query or '')
    filtered_agent_records = []
    for record in agent_records:
        if normalized_agent_id and (record.agent_id or '') != normalized_agent_id:
            continue
        status_value = record.completion_status or record.spawn_status or ''
        if normalized_agent_status and status_value != normalized_agent_status:
            continue
        if normalized_agent_query:
            haystack = normalize_text('\n'.join([
                record.task_label or '',
                record.task_text or '',
                record.brain_note or '',
                record.child_task_excerpt or '',
                record.child_final_reply or '',
                record.completion_result or '',
                record.child_error or '',
            ]))
            if normalized_agent_query not in haystack:
                continue
        filtered_agent_records.append(record)

    all_task_items = load_checklist_items(
        db_path=Path(DB_PATH),
        user_id=user_id,
        group_id=group_id,
        chat_type=chat_type,
        task_status=task_status,
        task_agent=task_agent,
        task_query=task_query,
        limit=max(limit, 100),
    )
    completed_task_items = [item for item in all_task_items if str(item.get("status") or "").strip() in DONE_TASK_STATUSES]
    active_task_items = [item for item in all_task_items if str(item.get("status") or "").strip() not in DONE_TASK_STATUSES]
    normalized_task_status = str(task_status or '').strip()
    if normalized_task_status in DONE_TASK_STATUSES:
        task_items = completed_task_items
        hidden_completed_task_items: list[dict[str, Any]] = []
    else:
        task_items = active_task_items
        hidden_completed_task_items = completed_task_items

    return {
        "user_id": user_id,
        "group_id": group_id,
        "chat_type": chat_type,
        "limit": limit,
        "date": normalized_date,
        "task_status": normalized_task_status,
        "task_agent": str(task_agent or '').strip(),
        "task_query": str(task_query or '').strip(),
        "agent_id": str(agent_id or '').strip(),
        "agent_status": str(agent_status or '').strip(),
        "agent_query": str(agent_query or '').strip(),
        "show_completed": bool(show_completed),
        "log_path": str(log_path),
        "transcript_dir": str(transcript_dir),
        "count": len(records),
        "agent_count": len(filtered_agent_records),
        "task_count": len(task_items),
        "all_task_count": len(all_task_items),
        "active_task_count": len(active_task_items),
        "completed_task_count": len(completed_task_items),
        "records": [record.to_dict() for record in records],
        "agent_records": [record.to_dict() for record in filtered_agent_records],
        "task_items": task_items,
        "active_task_items": active_task_items,
        "completed_task_items": hidden_completed_task_items,
        "overview": build_history_overview(log_path=log_path, user_id=user_id, date=normalized_date),
    }


def html_escape(value: str | None) -> str:
    text = value or ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', '&quot;')
    )


TASK_STATUS_LABELS = {
    "pending": "待开始",
    "in_progress": "进行中",
    "implemented_pending_verify": "已接线待验证",
    "done": "已完成",
    "completed": "已完成",
    "blocked": "阻塞",
    "failed": "失败",
}
TASK_STATUS_CLASS = {
    "pending": "pending",
    "in_progress": "progress",
    "implemented_pending_verify": "verify",
    "done": "done",
    "completed": "done",
    "blocked": "blocked",
    "failed": "failed",
}
TASK_AGENT_OPTIONS = ["", "qq-main", "brain-secretary-dev", "agent-hub-dev"]
TASK_STATUS_OPTIONS = ["", "pending", "in_progress", "implemented_pending_verify", "done", "blocked", "failed"]
AGENT_STATUS_OPTIONS = ["", "accepted", "completed successfully", "timed out", "failed", "unknown"]
DONE_TASK_STATUSES = {"done", "completed"}


def load_checklist_items(
    db_path: Path,
    user_id: int | None,
    group_id: int | None,
    chat_type: str,
    task_status: str | None = None,
    task_agent: str | None = None,
    task_query: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    sql = "SELECT * FROM checklist_items WHERE 1=1"
    params: list[Any] = []

    if user_id is not None:
        sql += " AND user_qq=?"
        params.append(int(user_id))
    if chat_type:
        sql += " AND chat_type=?"
        params.append(str(chat_type))
    if group_id is not None:
        sql += " AND group_id=?"
        params.append(int(group_id))
    if task_status:
        sql += " AND status=?"
        params.append(str(task_status))
    if task_agent:
        sql += " AND (assigned_agent=? OR owner_agent=?)"
        params.extend([str(task_agent), str(task_agent)])
    normalized_query = str(task_query or "").strip()
    if normalized_query:
        sql += " AND (title LIKE ? OR detail LIKE ? OR validation LIKE ? OR notes LIKE ?)"
        like = f"%{normalized_query}%"
        params.extend([like, like, like, like])

    sql += " ORDER BY sort_index ASC, id ASC LIMIT ?"
    params.append(int(limit))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def render_option(value: str, label: str, selected_value: str) -> str:
    selected = "selected" if value == selected_value else ""
    return f'<option value="{html_escape(value)}" {selected}>{html_escape(label)}</option>'


def render_status_badge(status: str | None) -> str:
    raw = str(status or "pending").strip() or "pending"
    label = TASK_STATUS_LABELS.get(raw, raw)
    css = TASK_STATUS_CLASS.get(raw, "pending")
    return f'<span class="badge {css}">{html_escape(label)}</span>'


def build_task_overview_text(task_items: list[dict[str, Any]]) -> str:
    if not task_items:
        return "当前筛选下没有任务项。"
    counts: dict[str, int] = {}
    for item in task_items:
        status = str(item.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    ordered = [
        f"{TASK_STATUS_LABELS.get(status, status)} {counts[status]}"
        for status in ["done", "implemented_pending_verify", "in_progress", "pending", "blocked", "failed"]
        if counts.get(status)
    ]
    return " · ".join(ordered)


def preview_text(text: str | None, max_chars: int = 180, max_lines: int = 4) -> str:
    raw = str(text or "").strip()
    if not raw:
        return "（空）"
    lines = raw.splitlines()
    clipped_lines = lines[:max_lines]
    preview = " / ".join(line.strip() for line in clipped_lines if line.strip())
    preview = re.sub(r"\s+", " ", preview).strip()
    if len(lines) > max_lines or len(raw) > max_chars:
        preview = preview[:max_chars].rstrip()
        if not preview.endswith("…"):
            preview = preview.rstrip("…") + "…"
    return preview or "（空）"


def is_long_text(text: str | None, max_chars: int = 360, max_lines: int = 8) -> bool:
    raw = str(text or "")
    return len(raw) > max_chars or len(raw.splitlines()) > max_lines


def render_message_block(kind: str, title: str, text: str | None, *, meta: str | None = None, open_by_default: bool = False) -> str:
    raw = str(text or "").strip() or "（空）"
    meta_html = f'<div class="meta">{html_escape(title)}' + (f' · {html_escape(meta)}' if meta else '') + '</div>'
    if not is_long_text(raw):
        return (
            f'<div class="message {kind}">'
            f'{meta_html}'
            f'<pre>{html_escape(raw)}</pre>'
            '</div>'
        )

    open_attr = ' open' if open_by_default else ''
    return (
        f'<div class="message {kind}">'
        f'{meta_html}'
        f'<pre class="preview">{html_escape(preview_text(raw, max_chars=280, max_lines=5))}</pre>'
        f'<details class="fold"{open_attr}>'
        '<summary>展开全文</summary>'
        f'<pre>{html_escape(raw)}</pre>'
        '</details>'
        '</div>'
    )


def render_task_card(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "未命名任务")
    detail = str(item.get("detail") or "")
    validation = str(item.get("validation") or "")
    notes = str(item.get("notes") or "")
    assigned_agent = str(item.get("assigned_agent") or "")
    owner_agent = str(item.get("owner_agent") or "")
    updated_at = str(item.get("updated_at") or item.get("created_at") or "")
    body_parts = [
        render_message_block("agent-task", "任务说明", detail or "暂无说明", open_by_default=False),
    ]
    if validation:
        body_parts.append(render_message_block("assistant", "验证 / 证据", validation, open_by_default=False))
    if notes:
        body_parts.append(render_message_block("brain", "备注", notes, open_by_default=False))

    meta_parts = []
    if owner_agent:
        meta_parts.append(f"owner={owner_agent}")
    if assigned_agent:
        meta_parts.append(f"assigned={assigned_agent}")
    if updated_at:
        meta_parts.append(updated_at)

    summary_text = preview_text(detail or validation or notes, max_chars=110, max_lines=2)
    return (
        '<details class="task-card fold-card">'
        f'<summary><span class="summary-title">{html_escape(title)}</span>'
        f'<span class="summary-text">{html_escape(summary_text)}</span></summary>'
        '<div class="card-body compact">'
        f'<div class="task-head"><div class="meta">{" · ".join(html_escape(part) for part in meta_parts if part)}</div>{render_status_badge(item.get("status"))}</div>'
        f'{"".join(body_parts)}'
        '</div>'
        '</details>'
    )


def build_overview_text(payload: dict[str, Any]) -> str:
    overview = payload.get("overview") or {}
    total_counts = overview.get("total_counts") or {}
    user_counts = overview.get("user_counts") or {}
    user_id = payload.get("user_id")
    group_id = payload.get("group_id")
    date = payload.get("date") or "全部日期"

    parts = [
        f"日期范围：{date}",
        f"该用户私聊 {user_counts.get('private', 0)} 条",
        f"该用户群聊 {user_counts.get('group', 0)} 条",
        f"系统总私聊 {total_counts.get('private', 0)} 条",
        f"系统总群聊 {total_counts.get('group', 0)} 条",
    ]
    if user_id is not None:
        parts.insert(1, f"user_id={user_id}")
    if group_id is not None:
        parts.insert(2, f"group_id={group_id}")
    recent_group_ids = overview.get("recent_group_ids") or []
    if recent_group_ids:
        parts.append("该用户最近出现过的 group_id：" + ", ".join(str(item) for item in recent_group_ids))
    return " · ".join(parts)


def build_empty_chat_html(payload: dict[str, Any]) -> str:
    chat_type = payload.get("chat_type") or "private"
    user_id = payload.get("user_id")
    group_id = payload.get("group_id")
    overview = payload.get("overview") or {}
    total_counts = overview.get("total_counts") or {}
    user_counts = overview.get("user_counts") or {}
    recent_group_ids = overview.get("recent_group_ids") or []

    messages = ["没有查到 QQ ↔ OpenClaw 对话记录。"]
    if chat_type == "group":
        if total_counts.get("group", 0) <= 0:
            messages.append("当前日志里还没有任何群聊消息；先在群里 @机器人 说一句，再来刷新。")
        elif group_id is not None:
            messages.append(f"当前筛选的 group_id={group_id} 没有命中记录。")
        elif user_id is not None and user_counts.get("group", 0) <= 0:
            messages.append(f"当前日志里没有 user_id={user_id} 的群聊发言记录。")
            messages.append("如果你其实想看和机器人当前这条 QQ 私聊，请把 chat_type 切回 private。")
        else:
            messages.append("请补充 group_id，或切回 private 查看当前管理员私聊记录。")
        if recent_group_ids:
            messages.append("这个用户最近出现过的 group_id：" + ", ".join(str(item) for item in recent_group_ids))
    else:
        if total_counts.get("private", 0) <= 0:
            messages.append("当前日志里还没有任何私聊消息。")
        elif user_id is not None and user_counts.get("private", 0) <= 0:
            messages.append(f"当前日志里没有 user_id={user_id} 的私聊记录。")

    inner = "<br>".join(html_escape(message) for message in messages if message)
    return f'<div class="empty">{inner}</div>'


def build_empty_agent_html(payload: dict[str, Any]) -> str:
    if not (payload.get("records") or []):
        return '<div class="empty">当前筛选下没有命中的 QQ 对话记录，所以暂时无法关联到大脑 ↔ 子 Agent 协作转录。</div>'
    return '<div class="empty">当前命中的 QQ 会话里，没有解析到大脑 ↔ 子 Agent 协作记录。</div>'


def build_empty_brain_html(payload: dict[str, Any]) -> str:
    if payload.get("records"):
        return '<div class="empty">当前记录里没有解析到可展示的大脑主回复。</div>'
    return '<div class="empty">当前筛选下没有命中的 QQ 对话记录，所以也没有可展示的大脑主回复。</div>'


def build_empty_task_html(payload: dict[str, Any]) -> str:
    user_id = payload.get("user_id")
    if user_id is not None:
        return f'<div class="empty">当前筛选下没有任务项。你可以继续让系统派单；此处会展示 user_id={html_escape(str(user_id))} 的任务清单。</div>'
    return '<div class="empty">当前筛选下没有任务项。</div>'


def render_task_list_html(task_items: list[dict[str, Any]]) -> str:
    return "\n".join(render_task_card(item) for item in task_items) if task_items else ""


def build_completed_task_section(task_items: list[dict[str, Any]], *, open_by_default: bool = False) -> str:
    if not task_items:
        return ""
    open_attr = ' open' if open_by_default else ''
    return (
        '<details class="task-card fold-card completed-tasks"' + open_attr + '>'
        f'<summary><span class="summary-title">已完成任务（{len(task_items)}）</span>'
        '<span class="summary-text">默认折叠，避免长期占用主列表</span></summary>'
        '<div class="card-body compact">'
        f'{render_task_list_html(task_items)}'
        '</div>'
        '</details>'
    )


def render_chat_history_page(payload: dict[str, Any], token: str | None = None) -> str:
    selected_user_id = payload.get("user_id") or ""
    selected_group_id = payload.get("group_id") or ""
    selected_limit = payload.get("limit") or 50
    chat_type = payload.get("chat_type") or "private"
    selected_date = payload.get("date") or ""
    selected_task_status = str(payload.get("task_status") or "")
    selected_task_agent = str(payload.get("task_agent") or "")
    selected_task_query = str(payload.get("task_query") or "")
    selected_agent_id = str(payload.get("agent_id") or "")
    selected_agent_status = str(payload.get("agent_status") or "")
    selected_agent_query = str(payload.get("agent_query") or "")
    selected_show_completed = bool(payload.get("show_completed"))
    records = payload.get("records") or []
    agent_records = payload.get("agent_records") or []
    task_items = payload.get("task_items") or []
    completed_task_items = payload.get("completed_task_items") or []
    all_task_items = list(task_items) + list(completed_task_items)
    active_task_count = int(payload.get("active_task_count") or 0)
    completed_task_count = int(payload.get("completed_task_count") or 0)

    chat_cards: list[str] = []
    brain_cards: list[str] = []
    for index, record in enumerate(records):
        reply_source = record.get("reply_source")
        source_label = "OpenClaw 转录" if reply_source == "openclaw_transcript" else "发送日志预览"
        qq_summary = preview_text(record.get("qq_text"), max_chars=70, max_lines=2)
        reply_summary = preview_text(record.get("reply_text") or "未匹配到明确回复记录", max_chars=90, max_lines=2)

        meta_bits = [
            html_escape(record.get("qq_time") or ""),
            f'user_id={record.get("user_id") or ""}',
            f'message_id={record.get("qq_message_id") or ""}',
        ]
        if record.get("chat_type") == "group":
            session_label = record.get("session_label") or ""
            if "-group-" in session_label:
                meta_bits.append(f'group_session={html_escape(session_label)}')

        reply_meta_bits = [html_escape(record.get("reply_time") or ""), source_label]
        if record.get("transcript_path"):
            reply_meta_bits.append(html_escape(record.get("transcript_path") or ""))

        user_block = render_message_block(
            "user",
            "QQ",
            record.get("qq_text") or "",
            meta=" · ".join(bit for bit in meta_bits if bit),
            open_by_default=index == 0,
        )

        if record.get("reply_text"):
            reply_block = render_message_block(
                "assistant",
                "OpenClaw",
                record.get("reply_text") or "",
                meta=" · ".join(bit for bit in reply_meta_bits if bit),
                open_by_default=index == 0,
            )
        else:
            reply_block = (
                '<div class="message assistant missing">'
                '<div class="meta">OpenClaw</div>'
                '<pre>未匹配到明确回复记录</pre>'
                '</div>'
            )

        open_attr = ' open' if index < 2 else ''
        chat_cards.append(
            '<details class="chat-card fold-card"' + open_attr + '>'
            f'<summary><span class="summary-title">QQ · {html_escape(record.get("qq_time") or "")}</span>'
            f'<span class="summary-text">{html_escape(qq_summary)} → {html_escape(reply_summary)}</span></summary>'
            '<div class="card-body">'
            f'{user_block}'
            f'{reply_block}'
            f'<div class="session">session={html_escape(record.get("session_label") or "")}</div>'
            '</div>'
            '</details>'
        )

        brain_meta_parts = [
            html_escape(record.get("reply_time") or record.get("qq_time") or ""),
            source_label,
        ]
        if record.get("matched"):
            brain_meta_parts.append("matched")
        if record.get("transcript_session_id"):
            brain_meta_parts.append(f'session_id={html_escape(record.get("transcript_session_id") or "")}')
        brain_cards.append(
            '<details class="mini-card fold-card"' + open_attr + '>'
            '<summary>'
            '<span class="summary-title">大脑主回复</span>'
            f'<span class="summary-text">{html_escape(reply_summary)}</span>'
            '</summary>'
            '<div class="card-body compact">'
            f'{render_message_block("assistant", "大脑主回复", record.get("reply_text") or "未匹配到明确回复记录", meta=" · ".join(part for part in brain_meta_parts if part), open_by_default=index == 0)}'
            f'<div class="session">来自 QQ：{html_escape(qq_summary)}</div>'
            '</div>'
            '</details>'
        )

    agent_cards: list[str] = []
    for index, record in enumerate(agent_records):
        meta_parts = [
            html_escape(record.get("event_time") or ""),
            html_escape(record.get("agent_id") or "unknown-agent"),
            html_escape(record.get("completion_status") or record.get("spawn_status") or "unknown"),
        ]
        if record.get("task_label"):
            meta_parts.append(html_escape(record.get("task_label") or ""))

        detail_blocks: list[str] = []
        if record.get("brain_note"):
            detail_blocks.append(render_message_block("brain", "大脑派单说明", record.get("brain_note") or "", open_by_default=index == 0))
        if record.get("task_text") or record.get("child_task_excerpt"):
            detail_blocks.append(render_message_block("agent-task", "任务内容", record.get("task_text") or record.get("child_task_excerpt") or "", open_by_default=index == 0))
        if record.get("completion_result") or record.get("child_final_reply"):
            detail_blocks.append(render_message_block("agent", "子 Agent 返回", record.get("child_final_reply") or record.get("completion_result") or "", open_by_default=index == 0))
        if record.get("spawn_error") or record.get("child_error"):
            detail_blocks.append(render_message_block("assistant missing", "错误 / 异常", record.get("spawn_error") or record.get("child_error") or "", open_by_default=index == 0))

        footer_parts: list[str] = []
        if record.get("child_session_key"):
            footer_parts.append(f'child_key={html_escape(record.get("child_session_key") or "")}')
        if record.get("child_session_path"):
            footer_parts.append(html_escape(record.get("child_session_path") or ""))
        if record.get("transcript_path"):
            footer_parts.append(html_escape(record.get("transcript_path") or ""))

        details_html = "".join(detail_blocks) or '<div class="empty">没有解析到更多子 agent 细节</div>'
        footer_html = " · ".join(part for part in footer_parts if part)
        summary_text = preview_text(record.get("task_text") or record.get("child_task_excerpt") or record.get("child_final_reply") or record.get("completion_result"), max_chars=90, max_lines=2)
        open_attr = ' open' if index < 2 else ''
        agent_cards.append(
            '<details class="mini-card fold-card"' + open_attr + '>'
            f'<summary><span class="summary-title">脑内协作 · {html_escape(record.get("agent_id") or "unknown-agent")}</span>'
            f'<span class="summary-text">{html_escape(summary_text)}</span></summary>'
            '<div class="card-body compact">'
            f'<div class="meta">{" · ".join(part for part in meta_parts if part)}</div>'
            f'{details_html}'
            f'<div class="session">{footer_html}</div>'
            '</div>'
            '</details>'
        )

    visible_task_html = render_task_list_html(task_items)
    completed_task_section = build_completed_task_section(completed_task_items, open_by_default=selected_show_completed)
    if visible_task_html:
        task_content = visible_task_html + ("\n" + completed_task_section if completed_task_section else "")
    elif completed_task_section:
        task_content = completed_task_section
    else:
        task_content = build_empty_task_html(payload)
    chat_content = "\n".join(chat_cards) if chat_cards else build_empty_chat_html(payload)
    brain_content = "\n".join(brain_cards) if brain_cards else build_empty_brain_html(payload)
    agent_content = "\n".join(agent_cards) if agent_cards else build_empty_agent_html(payload)

    private_selected = 'selected' if chat_type == 'private' else ''
    group_selected = 'selected' if chat_type == 'group' else ''

    query_parts = [
        f'user_id={selected_user_id}',
        f'limit={selected_limit}',
        f'chat_type={chat_type}',
    ]
    if selected_group_id:
        query_parts.append(f'group_id={selected_group_id}')
    if selected_date:
        query_parts.append(f'date={selected_date}')
    if selected_task_status:
        query_parts.append(f'task_status={selected_task_status}')
    if selected_task_agent:
        query_parts.append(f'task_agent={selected_task_agent}')
    if selected_task_query:
        query_parts.append(f'task_query={selected_task_query}')
    if selected_agent_id:
        query_parts.append(f'agent_id={selected_agent_id}')
    if selected_agent_status:
        query_parts.append(f'agent_status={selected_agent_status}')
    if selected_agent_query:
        query_parts.append(f'agent_query={selected_agent_query}')
    if selected_show_completed:
        query_parts.append('show_completed=1')
    if token:
        query_parts.append(f'token={token}')
    api_href = '/api/chat-history?' + '&'.join(query_parts)

    overview_text = build_overview_text(payload)
    task_overview_text = build_task_overview_text(all_task_items)

    task_status_options_html = ''.join(render_option(value, TASK_STATUS_LABELS.get(value, '全部状态' if value == '' else value), selected_task_status) for value in TASK_STATUS_OPTIONS)
    task_agent_options_html = ''.join(render_option(value, '全部 Agent' if value == '' else value, selected_task_agent) for value in TASK_AGENT_OPTIONS)
    agent_id_options_html = ''.join(render_option(value, '全部 Agent' if value == '' else value, selected_agent_id) for value in TASK_AGENT_OPTIONS)
    agent_status_options_html = ''.join(render_option(value, '全部状态' if value == '' else value, selected_agent_status) for value in AGENT_STATUS_OPTIONS)
    show_completed_checked = 'checked' if selected_show_completed else ''
    if selected_task_status in DONE_TASK_STATUSES:
        task_section_meta = f'当前筛出已完成 {payload.get("task_count") or 0} 条；支持按状态 / Agent / 关键词筛选'
    elif completed_task_count > 0:
        fold_state = '已展开' if selected_show_completed else '默认折叠'
        task_section_meta = f'主列表 {payload.get("task_count") or 0} 条；已完成 {completed_task_count} 条{fold_state}'
    else:
        task_section_meta = f'主列表 {payload.get("task_count") or 0} 条；支持按状态 / Agent / 关键词筛选'

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QQ ↔ OpenClaw 聊天记录</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#0b1020; color:#e8ecf3; margin:0; padding:24px; }}
    .wrap {{ max-width: 1460px; margin: 0 auto; }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:0; font-size:20px; }}
    .sub {{ color:#9aa7bd; margin-bottom:20px; }}
    form {{ display:flex; gap:12px; flex-wrap:wrap; background:#131a2b; padding:16px; border-radius:14px; margin-bottom:14px; }}
    label {{ display:flex; flex-direction:column; gap:6px; font-size:13px; color:#9aa7bd; min-width:160px; }}
    input, select, button {{ border-radius:10px; border:1px solid #2b3550; background:#0f1525; color:#e8ecf3; padding:10px 12px; font-size:14px; }}
    button {{ cursor:pointer; background:#2563eb; border-color:#2563eb; }}
    .tips {{ margin: 10px 0 16px; color:#9aa7bd; font-size:13px; line-height:1.7; }}
    .tips a, .nav a {{ color:#8ab4ff; text-decoration:none; }}
    .hint {{ color:#7f8aa3; font-size:12px; line-height:1.55; }}
    .inline-check {{ min-width:220px; justify-content:center; }}
    .inline-check .toggle {{ display:flex; align-items:center; gap:10px; min-height:44px; }}
    .inline-check input[type="checkbox"] {{ width:18px; height:18px; margin:0; }}
    .nav {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }}
    .nav a {{ display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background:#131a2b; border:1px solid #27314a; }}
    .layout {{ display:grid; grid-template-columns:minmax(0, 1.55fr) minmax(360px, 1fr); gap:20px; align-items:start; }}
    .panel {{ min-width:0; }}
    .panel-shell {{ background:#0f1525; border:1px solid #27314a; border-radius:18px; padding:16px; margin-bottom:20px; }}
    .panel-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }}
    .section-meta {{ color:#9aa7bd; font-size:13px; line-height:1.6; }}
    .sidebar {{ position:sticky; top:16px; display:flex; flex-direction:column; gap:18px; max-height:calc(100vh - 32px); overflow:auto; padding-right:4px; }}
    .chat-card, .mini-card, .task-card {{ background:#131a2b; border:1px solid #27314a; border-radius:16px; margin-bottom:14px; overflow:hidden; }}
    .fold-card > summary {{ list-style:none; cursor:pointer; padding:14px 16px; display:flex; flex-direction:column; gap:6px; background:#131a2b; }}
    .fold-card > summary::-webkit-details-marker {{ display:none; }}
    .fold-card[open] > summary {{ border-bottom:1px solid #27314a; }}
    .summary-title {{ font-size:13px; color:#9aa7bd; }}
    .summary-text {{ font-size:14px; color:#e8ecf3; line-height:1.55; }}
    .card-body {{ padding:16px; }}
    .card-body.compact {{ padding:14px; }}
    .message {{ border-radius:12px; padding:12px 14px; margin-bottom:12px; }}
    .user {{ background:#1a2440; }}
    .assistant {{ background:#10221a; }}
    .assistant.missing {{ background:#2a1c1c; }}
    .brain {{ background:#2a2238; }}
    .agent-task {{ background:#17253a; }}
    .agent {{ background:#10221a; }}
    .meta {{ color:#9aa7bd; font-size:12px; margin-bottom:8px; line-height:1.55; }}
    .session {{ color:#7f8aa3; font-size:12px; line-height:1.6; }}
    pre {{ margin:0; white-space:pre-wrap; word-break:break-word; font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,Liberation Mono,monospace; line-height:1.55; }}
    pre.preview {{ color:#d7deea; }}
    .fold {{ margin-top:10px; border-top:1px dashed #31405f; padding-top:10px; }}
    .fold > summary {{ cursor:pointer; color:#8ab4ff; margin-bottom:10px; }}
    .empty {{ padding:24px; background:#131a2b; border-radius:16px; color:#9aa7bd; line-height:1.75; }}
    .task-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }}
    .badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:600; }}
    .badge.pending {{ background:#2b3550; color:#d4dcf0; }}
    .badge.progress {{ background:#553a12; color:#ffd58b; }}
    .badge.verify {{ background:#173a57; color:#9bd3ff; }}
    .badge.done {{ background:#153c25; color:#9ef0b8; }}
    .badge.blocked {{ background:#4a1f1f; color:#ffaaaa; }}
    .badge.failed {{ background:#5a1d28; color:#ffb2bf; }}
    @media (max-width: 1100px) {{
      .layout {{ grid-template-columns:1fr; }}
      .sidebar {{ position:static; max-height:none; overflow:visible; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>QQ ↔ OpenClaw 聊天记录</h1>
    <div class="sub">现在支持任务清单筛选、子 Agent 协作筛选、右侧固定大脑主回复，并补上了异步完成回推链路所需的运维可视化。</div>
    <form method="get" action="/chat-history">
      <label>user_id
        <input name="user_id" value="{html_escape(str(selected_user_id))}" />
        <span class="hint">private 查私聊对象；group 查群内发言人</span>
      </label>
      <label>group_id
        <input name="group_id" value="{html_escape(str(selected_group_id))}" />
        <span class="hint">群聊建议填写群号；private 可留空</span>
      </label>
      <label>chat_type
        <select name="chat_type">
          <option value="private" {private_selected}>private</option>
          <option value="group" {group_selected}>group</option>
        </select>
      </label>
      <label>date
        <input type="date" name="date" value="{html_escape(selected_date)}" />
      </label>
      <label>limit
        <input name="limit" value="{selected_limit}" />
        <span class="hint">对话 / 协作记录条数</span>
      </label>
      <label>task_status
        <select name="task_status">{task_status_options_html}</select>
      </label>
      <label>task_agent
        <select name="task_agent">{task_agent_options_html}</select>
      </label>
      <label>task_query
        <input name="task_query" value="{html_escape(selected_task_query)}" />
        <span class="hint">筛任务标题、说明、验证</span>
      </label>
      <label class="inline-check">show_completed
        <span class="toggle"><input type="checkbox" name="show_completed" value="1" {show_completed_checked} /><span>展开已完成任务</span></span>
        <span class="hint">默认折叠到“已完成任务”分组，避免长期占主列表</span>
      </label>
      <label>agent_id
        <select name="agent_id">{agent_id_options_html}</select>
      </label>
      <label>agent_status
        <select name="agent_status">{agent_status_options_html}</select>
      </label>
      <label>agent_query
        <input name="agent_query" value="{html_escape(selected_agent_query)}" />
        <span class="hint">筛派单说明、任务内容、子 Agent 返回</span>
      </label>
      <input type="hidden" name="token" value="{html_escape(token or '')}" />
      <label>&nbsp;
        <button type="submit">刷新</button>
      </label>
    </form>
    <div class="nav">
      <a href="#task-section">任务清单（{payload.get("task_count") or 0}）</a>
      <a href="#qq-section">QQ 对话（{payload.get("count") or 0}）</a>
      <a href="#brain-section">大脑主回复（{len(records)}）</a>
      <a href="#agent-section">子 Agent 协作（{payload.get("agent_count") or 0}）</a>
      <a href="{api_href}">JSON 接口</a>
    </div>
    <div class="tips">
      当前可用数据：{html_escape(overview_text)}<br>
      任务状态概览：{html_escape(task_overview_text)}<br>
      数据来源：`logs/bot.log` 的 QQ 原始消息 + `~/.openclaw/agents/qq-main/sessions/*.jsonl` 的主脑转录 + 子 agent sessions 转录 + `data/tasks.db` 的任务清单。
    </div>

    <section class="panel-shell" id="task-section">
      <div class="panel-head">
        <h2>任务清单</h2>
        <div class="section-meta">{html_escape(task_section_meta)}</div>
      </div>
      {task_content}
    </section>

    <div class="layout">
      <section class="panel" id="qq-section">
        <div class="panel-shell">
          <div class="panel-head">
            <h2>QQ 对话</h2>
            <div class="section-meta">共 {payload.get("count") or 0} 条，按时间倒序</div>
          </div>
          {chat_content}
        </div>
      </section>

      <aside class="panel sidebar">
        <section class="panel-shell" id="brain-section">
          <div class="panel-head">
            <h2>大脑主回复</h2>
            <div class="section-meta">单 Agent / 多 Agent 都显示</div>
          </div>
          {brain_content}
        </section>

        <section class="panel-shell" id="agent-section">
          <div class="panel-head">
            <h2>大脑 ↔ 子 Agent 协作</h2>
            <div class="section-meta">共 {payload.get("agent_count") or 0} 条；支持按 Agent / 状态 / 关键词筛选</div>
          </div>
          {agent_content}
        </section>
      </aside>
    </div>
  </div>
</body>
</html>'''
