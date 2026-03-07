from __future__ import annotations

import base64
import json
import mimetypes
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
import wave

from bot.qq_sender import QQSender

INBOX_ROOT = Path('data/inbox')
TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.csv', '.tsv', '.json', '.yaml', '.yml', '.ini', '.toml',
    '.log', '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.c', '.cpp', '.h',
    '.html', '.htm', '.css', '.sql', '.xml', '.sh', '.bat', '.ps1', '.properties', '.env',
}
MEDIA_TYPES = {'image', 'file', 'record', 'video'}
MAX_TEXT_PREVIEW = 3000
MAX_CONTEXT_BLOCK = 5000
TESSERACT_LANGS = 'chi_sim+eng'


def extract_plain_text(message_payload: Any, raw_message: str | None = None) -> str:
    parts: list[str] = []
    if isinstance(message_payload, list):
        for item in message_payload:
            if not isinstance(item, dict):
                continue
            item_type = item.get('type')
            data = item.get('data') or {}
            if item_type == 'text':
                text = str(data.get('text') or '').strip()
                if text:
                    parts.append(text)
            elif item_type == 'reply':
                reply_id = data.get('id') or data.get('message_id') or ''
                if reply_id:
                    parts.append(f'[引用消息:{reply_id}]')
            elif item_type == 'at':
                qq = data.get('qq') or ''
                if qq:
                    parts.append(f'@{qq}')
    text = '\n'.join(part for part in parts if part).strip()
    if text:
        return text
    return str(raw_message or '').strip()


def _message_storage_dir(event: dict[str, Any]) -> Path:
    timestamp = int(event.get('time') or 0)
    if timestamp > 0:
        dt = datetime.fromtimestamp(timestamp)
    else:
        dt = datetime.now()
    message_id = event.get('message_id') or f'local-{dt.strftime("%H%M%S")}'
    folder = INBOX_ROOT / dt.strftime('%Y-%m-%d') / f'msg-{message_id}'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _safe_name(name: str | None, fallback: str) -> str:
    raw = str(name or '').strip().replace('\\', '_').replace('/', '_')
    return raw or fallback


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _download_url(url: str, dest: Path, timeout: int = 20) -> Path | None:
    if not url:
        return None
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, dest.open('wb') as handle:
            shutil.copyfileobj(response, handle)
        return dest
    except Exception:
        return None


def _guess_mime(path: Path | None) -> str:
    if path is None:
        return ''
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    try:
        result = subprocess.run(['file', '--brief', '--mime-type', str(path)], capture_output=True, text=True, timeout=5, check=False)
        return result.stdout.strip()
    except Exception:
        return ''


def _read_text_preview(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime = _guess_mime(path)
    if suffix not in TEXT_EXTENSIONS and not mime.startswith('text/') and mime not in {'application/json', 'application/xml'}:
        return None
    for encoding in ('utf-8', 'utf-8-sig', 'gb18030', 'latin1'):
        try:
            content = path.read_text(encoding=encoding)
            return content[:MAX_TEXT_PREVIEW].strip()
        except Exception:
            continue
    return None


def _describe_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    size = path.stat().st_size
    mime = _guess_mime(path)
    parts = [path.name, f'{size} bytes']
    if mime:
        parts.append(mime)
    return ' · '.join(parts)


def _audio_summary(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    if path.suffix.lower() != '.wav':
        return _describe_file(path)
    try:
        with wave.open(str(path), 'rb') as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            duration = frames / rate if rate else 0
            channels = handle.getnchannels()
        return f'{path.name} · {duration:.2f}s · {rate}Hz · {channels}ch'
    except Exception:
        return _describe_file(path)


def _extract_ocr_text(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get('data')
    if isinstance(data, str) and data.strip():
        return data.strip()
    if isinstance(data, dict):
        parts: list[str] = []
        if isinstance(data.get('text'), str) and data.get('text').strip():
            parts.append(data['text'].strip())
        texts = data.get('texts') or data.get('ocrs') or data.get('result')
        if isinstance(texts, list):
            for item in texts:
                if isinstance(item, dict):
                    text = item.get('text') or item.get('words') or item.get('value')
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(item, str) and item.strip():
                    parts.append(item.strip())
        joined = '\n'.join(part for part in parts if part).strip()
        if joined:
            return joined[:MAX_TEXT_PREVIEW]
        if data:
            return json.dumps(data, ensure_ascii=False)[:MAX_TEXT_PREVIEW]
    return None


def _clean_ocr_text(text: str | None) -> str | None:
    raw = str(text or '').replace('\x0c', '\n')
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    cleaned = '\n'.join(lines).strip()
    if len(cleaned) <= 1:
        return None
    cjk_count = sum(1 for ch in cleaned if '\u4e00' <= ch <= '\u9fff')
    alnum_count = sum(1 for ch in cleaned if ch.isalnum())
    ascii_tokens = [token for token in cleaned.replace('\n', ' ').split() if token.isascii() and any(ch.isalpha() for ch in token)]
    if cjk_count < 2 and alnum_count < 6 and not any(len(token) >= 4 for token in ascii_tokens):
        return None
    return cleaned[:MAX_TEXT_PREVIEW]


def _run_tesseract(path: Path, *, psm: int) -> str | None:
    if shutil.which('tesseract') is None:
        return None
    try:
        result = subprocess.run(
            ['tesseract', str(path), 'stdout', '-l', TESSERACT_LANGS, '--psm', str(psm)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return None

    if result.returncode not in {0, 1}:
        return None
    return _clean_ocr_text(result.stdout)


def _preprocess_for_ocr(path: Path) -> Path | None:
    if shutil.which('ffmpeg') is None:
        return None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix='ocr-pre-', dir=str(path.parent)))
        output_path = temp_dir / f'{path.stem}-ocr.png'
        result = subprocess.run(
            [
                'ffmpeg', '-y', '-loglevel', 'error', '-i', str(path),
                '-vf', 'scale=iw*2:ih*2:flags=lanczos,format=gray,eq=contrast=1.35:brightness=0.03',
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0 or not output_path.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        return output_path
    except Exception:
        return None


def _tesseract_ocr(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None

    for psm in (6, 11):
        text = _run_tesseract(path, psm=psm)
        if text:
            return text

    preprocessed = _preprocess_for_ocr(path)
    if preprocessed is None:
        return None

    try:
        for psm in (6, 11):
            text = _run_tesseract(preprocessed, psm=psm)
            if text:
                return text
    finally:
        shutil.rmtree(preprocessed.parent, ignore_errors=True)

    return None


async def _napcat_ocr(qq_sender: QQSender, saved_path: Path | None, source_url: str) -> str | None:
    if saved_path is None or not saved_path.exists():
        return None
    if platform.system().lower() != 'windows':
        return None

    candidates: list[str] = []
    if source_url:
        candidates.append(source_url)

    resolved_path = saved_path.resolve()
    candidates.extend([
        resolved_path.as_uri(),
        str(resolved_path),
    ])

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate or '').strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            payload = await qq_sender.ocr_image(normalized)
        except Exception:
            continue
        text = _extract_ocr_text(payload)
        if text:
            return text
    return None


async def _resolve_image(segment: dict[str, Any], qq_sender: QQSender, store_dir: Path, index: int) -> dict[str, Any]:
    data = segment.get('data') or {}
    file_id = str(data.get('file') or '').strip()
    info = await qq_sender.get_image(file_id) if file_id else {}
    image_data = info.get('data') if isinstance(info, dict) else {}
    if not isinstance(image_data, dict):
        image_data = {}

    saved_path: Path | None = None
    local_path = Path(str(image_data.get('file') or '')) if image_data.get('file') else None
    file_name = _safe_name(image_data.get('file_name') or data.get('file'), f'image-{index}.bin')
    if local_path and local_path.exists():
        saved_path = store_dir / file_name
        if not saved_path.exists():
            try:
                shutil.copy2(local_path, saved_path)
            except Exception:
                saved_path = local_path
    elif isinstance(image_data.get('base64'), str) and image_data.get('base64').strip():
        saved_path = store_dir / file_name
        try:
            saved_path.write_bytes(base64.b64decode(image_data['base64']))
        except Exception:
            saved_path = None
    elif image_data.get('url'):
        saved_path = _download_url(str(image_data.get('url')), store_dir / file_name)

    source_url = str(image_data.get('url') or data.get('url') or '')
    ocr_text = await _napcat_ocr(qq_sender, saved_path, source_url)
    ocr_engine = 'napcat' if ocr_text else ''
    if not ocr_text:
        ocr_text = _tesseract_ocr(saved_path)
        if ocr_text:
            ocr_engine = 'tesseract'

    note = ''
    if not ocr_text:
        if source_url:
            note = '当前未识别出清晰文字；已保留图片链接与本地文件，可继续结合 QQ 摘要理解。'
        else:
            note = '当前未识别出清晰文字；已保留本地图片文件供后续排查。'

    payload = {
        'kind': 'image',
        'qq_file_id': file_id,
        'summary': data.get('summary') or '',
        'saved_path': str(saved_path) if saved_path else '',
        'source_url': source_url,
        'file_size': image_data.get('file_size') or data.get('file_size') or '',
        'ocr_text': ocr_text or '',
        'ocr_engine': ocr_engine,
        'description': _describe_file(saved_path) or '',
        'note': note,
    }
    _write_json(store_dir / f'image-{index}.json', payload)
    return payload


async def _resolve_file(segment: dict[str, Any], qq_sender: QQSender, store_dir: Path, index: int) -> dict[str, Any]:
    data = segment.get('data') or {}
    file_id = str(data.get('file') or data.get('file_id') or '').strip()
    info = await qq_sender.get_file(file_id) if file_id else None
    file_data = info.get('data') if isinstance(info, dict) else {}
    if not isinstance(file_data, dict):
        file_data = {}

    source_path = None
    for key in ('file', 'path', 'local', 'local_path'):
        value = file_data.get(key)
        if value:
            candidate = Path(str(value))
            if candidate.exists():
                source_path = candidate
                break

    saved_path: Path | None = None
    file_name = _safe_name(file_data.get('name') or data.get('name') or data.get('file'), f'file-{index}')
    if source_path is not None:
        saved_path = store_dir / file_name
        if not saved_path.exists():
            try:
                shutil.copy2(source_path, saved_path)
            except Exception:
                saved_path = source_path
    else:
        source_url = str(file_data.get('url') or data.get('url') or '')
        if source_url:
            saved_path = _download_url(source_url, store_dir / file_name)

    preview = _read_text_preview(saved_path)
    payload = {
        'kind': 'file',
        'qq_file_id': file_id,
        'name': file_name,
        'saved_path': str(saved_path) if saved_path else '',
        'source_url': str(file_data.get('url') or data.get('url') or ''),
        'description': _describe_file(saved_path) or '',
        'text_preview': preview or '',
        'note': '' if preview else '当前只对文本类文件自动摘录；二进制文件会保留路径与元数据。',
    }
    _write_json(store_dir / f'file-{index}.json', payload)
    return payload


async def _resolve_record(segment: dict[str, Any], qq_sender: QQSender, store_dir: Path, index: int) -> dict[str, Any]:
    data = segment.get('data') or {}
    file_id = str(data.get('file') or data.get('file_id') or '').strip()
    info = await qq_sender.get_record(file_id, out_format='wav') if file_id else None
    record_data = info.get('data') if isinstance(info, dict) else {}
    if not isinstance(record_data, dict):
        record_data = {}

    source_path = None
    for key in ('file', 'path', 'local', 'local_path'):
        value = record_data.get(key)
        if value:
            candidate = Path(str(value))
            if candidate.exists():
                source_path = candidate
                break

    saved_path: Path | None = None
    file_name = _safe_name(record_data.get('file_name') or data.get('file'), f'voice-{index}.wav')
    if source_path is not None:
        saved_path = store_dir / file_name
        if not saved_path.exists():
            try:
                shutil.copy2(source_path, saved_path)
            except Exception:
                saved_path = source_path

    payload = {
        'kind': 'record',
        'qq_file_id': file_id,
        'saved_path': str(saved_path) if saved_path else '',
        'source_url': str(record_data.get('url') or data.get('url') or ''),
        'description': _audio_summary(saved_path) or '',
        'note': '已拉取语音文件；当前环境暂未配置自动语音转写后端。',
    }
    _write_json(store_dir / f'record-{index}.json', payload)
    return payload


async def _resolve_video(segment: dict[str, Any], _qq_sender: QQSender, store_dir: Path, index: int) -> dict[str, Any]:
    data = segment.get('data') or {}
    source_url = str(data.get('url') or '').strip()
    file_name = _safe_name(data.get('file') or f'video-{index}.mp4', f'video-{index}.mp4')
    saved_path = None
    if source_url:
        saved_path = _download_url(source_url, store_dir / file_name, timeout=30)

    payload = {
        'kind': 'video',
        'qq_file_id': str(data.get('file') or ''),
        'saved_path': str(saved_path) if saved_path else '',
        'source_url': source_url,
        'description': _describe_file(saved_path) or '',
        'note': '已记录视频文件/链接；当前环境暂未配置自动视频理解后端。',
    }
    _write_json(store_dir / f'video-{index}.json', payload)
    return payload


async def _resolve_attachment(segment: dict[str, Any], qq_sender: QQSender, store_dir: Path, index: int) -> dict[str, Any]:
    item_type = str(segment.get('type') or '').strip().lower()
    if item_type == 'image':
        return await _resolve_image(segment, qq_sender, store_dir, index)
    if item_type == 'file':
        return await _resolve_file(segment, qq_sender, store_dir, index)
    if item_type == 'record':
        return await _resolve_record(segment, qq_sender, store_dir, index)
    if item_type == 'video':
        return await _resolve_video(segment, qq_sender, store_dir, index)
    return {'kind': item_type or 'unknown'}


def _render_attachment_context(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(items, 1):
        kind = str(item.get('kind') or 'unknown')
        lines.append(f'[附件{index}] 类型: {kind}')
        if item.get('summary'):
            lines.append(f"- QQ 摘要: {item['summary']}")
        if item.get('name'):
            lines.append(f"- 名称: {item['name']}")
        if item.get('saved_path'):
            lines.append(f"- 本地路径: {item['saved_path']}")
        if item.get('source_url'):
            lines.append(f"- 源链接: {item['source_url']}")
        if item.get('description'):
            lines.append(f"- 元数据: {item['description']}")
        if item.get('ocr_text'):
            lines.append(f"- OCR 文本:\n{str(item['ocr_text'])[:MAX_TEXT_PREVIEW]}")
        if item.get('ocr_engine'):
            lines.append(f"- OCR 来源: {item['ocr_engine']}")
        if item.get('text_preview'):
            lines.append(f"- 文件摘录:\n{str(item['text_preview'])[:MAX_TEXT_PREVIEW]}")
        if item.get('note'):
            lines.append(f"- 备注: {item['note']}")
    context = '\n'.join(lines).strip()
    if len(context) > MAX_CONTEXT_BLOCK:
        context = context[:MAX_CONTEXT_BLOCK].rstrip() + '…'
    return context


async def build_user_message_with_media_context(event: dict[str, Any], qq_sender: QQSender) -> str:
    raw_message = str(event.get('raw_message') or '').strip()
    message_payload = event.get('message')
    plain_text = extract_plain_text(message_payload, raw_message=raw_message)

    segments = message_payload if isinstance(message_payload, list) else []
    media_segments = [item for item in segments if isinstance(item, dict) and str(item.get('type') or '').lower() in MEDIA_TYPES]
    if not media_segments:
        return plain_text or raw_message

    store_dir = _message_storage_dir(event)
    attachments: list[dict[str, Any]] = []
    for index, segment in enumerate(media_segments, 1):
        try:
            attachments.append(await _resolve_attachment(segment, qq_sender, store_dir, index))
        except Exception as exc:
            attachments.append({
                'kind': str(segment.get('type') or 'unknown'),
                'note': f'解析失败: {exc}',
            })

    context = _render_attachment_context(attachments)
    headline = plain_text
    if not headline or str(headline).startswith('[CQ:'):
        headline = '用户发送了媒体内容，请结合附件上下文处理。'
    if not context:
        return headline
    return (
        f'{headline}\n\n'
        '[QQ 媒体附件上下文]\n'
        f'{context}\n\n'
        '请优先依据以上 QQ 摘要、OCR 结果、本地路径与元数据作答；若 OCR 没读出文字但 QQ 摘要可用，请明确基于摘要回答；如果是你要发回 QQ 的结果，继续走已有的 send_image/send_file/send_voice/send_video 指令即可。'
    ).strip()
