import json
import httpx
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QQSender:
    def __init__(self, napcat_url: str):
        self.base_url = napcat_url.rstrip('/')

    @staticmethod
    def _normalize_media_source(media_source: str, field_name: str = 'media_source') -> str:
        value = str(media_source or '').strip()
        if not value:
            raise ValueError(f'{field_name} 不能为空')
        if value.startswith(('http://', 'https://', 'file://', 'base64://')):
            return value
        path = Path(value).expanduser()
        if path.exists():
            return path.resolve().as_uri()
        return value

    @staticmethod
    def _normalize_image_source(image_source: str) -> str:
        return QQSender._normalize_media_source(image_source, field_name='image_source')

    @staticmethod
    def _normalize_video_source(video_source: str) -> str:
        return QQSender._normalize_media_source(video_source, field_name='video_source')

    @staticmethod
    def _normalize_file_source(file_source: str) -> str:
        return QQSender._normalize_media_source(file_source, field_name='file_source')

    @staticmethod
    def _normalize_voice_source(voice_source: str) -> str:
        return QQSender._normalize_media_source(voice_source, field_name='voice_source')

    @staticmethod
    def _build_message_segments(
        text: str | None = None,
        image_sources: list[str] | None = None,
        video_sources: list[str] | None = None,
        file_sources: list[str] | None = None,
        voice_sources: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        text_value = str(text or '').strip()
        if text_value:
            segments.append({'type': 'text', 'data': {'text': text_value}})
        for image_source in image_sources or []:
            segments.append({'type': 'image', 'data': {'file': QQSender._normalize_image_source(image_source)}})
        for video_source in video_sources or []:
            segments.append({'type': 'video', 'data': {'file': QQSender._normalize_video_source(video_source)}})
        for file_source in file_sources or []:
            segments.append({'type': 'file', 'data': {'file': QQSender._normalize_file_source(file_source)}})
        for voice_source in voice_sources or []:
            normalized = QQSender._normalize_voice_source(voice_source)
            segments.append({'type': 'record', 'data': {'file': normalized}})
        return segments

    @staticmethod
    def _preview_message(message: Any) -> str:
        if isinstance(message, str):
            return message[:120]
        if isinstance(message, list):
            preview_parts: list[str] = []
            for item in message:
                if not isinstance(item, dict):
                    continue
                item_type = item.get('type')
                data = item.get('data') or {}
                if item_type == 'text':
                    preview_parts.append(str(data.get('text') or '').strip())
                elif item_type == 'image':
                    preview_parts.append(f"[CQ:image,file={data.get('file')}]")
                elif item_type == 'video':
                    preview_parts.append(f"[CQ:video,file={data.get('file')}]")
                elif item_type == 'file':
                    preview_parts.append(f"[CQ:file,file={data.get('file')}]")
                elif item_type == 'record':
                    preview_parts.append(f"[CQ:record,file={data.get('file')}]")
                else:
                    preview_parts.append(f"[CQ:{item_type}]")
            preview = '\n'.join(part for part in preview_parts if part).strip()
            return preview[:240] if preview else json.dumps(message, ensure_ascii=False)[:240]
        return str(message)[:120]

    async def call_action(self, endpoint: str, payload: dict[str, Any] | None = None, *, timeout: float = 20) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{endpoint}",
                json=payload or {},
                timeout=timeout,
            )
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {
                    'status': 'ok' if response.is_success else 'failed',
                    'retcode': 0 if response.is_success else response.status_code,
                    'data': None,
                    'raw_text': response.text,
                }

    async def _post_message(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.call_action(endpoint, payload, timeout=20)

    async def send_private_msg(self, user_id: int, message: str | list[dict[str, Any]]):
        try:
            result = await self._post_message('send_private_msg', {'user_id': user_id, 'message': message})
            logger.info(f"发送私聊消息到 {user_id}: {self._preview_message(message)}")
            return result
        except Exception as e:
            logger.error(f"发送私聊消息失败: {e}")
            return None

    async def send_group_msg(self, group_id: int, message: str | list[dict[str, Any]]):
        try:
            result = await self._post_message('send_group_msg', {'group_id': group_id, 'message': message})
            logger.info(f"发送群聊消息到 {group_id}: {self._preview_message(message)}")
            return result
        except Exception as e:
            logger.error(f"发送群聊消息失败: {e}")
            return None

    async def send_private_media_msg(
        self,
        user_id: int,
        text: str | None = None,
        image_sources: list[str] | None = None,
        video_sources: list[str] | None = None,
        file_sources: list[str] | None = None,
        voice_sources: list[str] | None = None,
    ):
        message = self._build_message_segments(
            text=text,
            image_sources=image_sources,
            video_sources=video_sources,
            file_sources=file_sources,
            voice_sources=voice_sources,
        )
        if not message:
            raise ValueError('至少需要文本、图片、视频、文件或语音之一')
        return await self.send_private_msg(user_id, message)

    async def send_group_media_msg(
        self,
        group_id: int,
        text: str | None = None,
        image_sources: list[str] | None = None,
        video_sources: list[str] | None = None,
        file_sources: list[str] | None = None,
        voice_sources: list[str] | None = None,
    ):
        message = self._build_message_segments(
            text=text,
            image_sources=image_sources,
            video_sources=video_sources,
            file_sources=file_sources,
            voice_sources=voice_sources,
        )
        if not message:
            raise ValueError('至少需要文本、图片、视频、文件或语音之一')
        return await self.send_group_msg(group_id, message)

    async def get_image(self, file_id: str) -> dict[str, Any]:
        return await self.call_action('get_image', {'file': str(file_id)}, timeout=25)

    async def ocr_image(self, image: str) -> dict[str, Any]:
        return await self.call_action('ocr_image', {'image': str(image)}, timeout=12)

    async def get_record(self, file_id: str, out_format: str = 'wav') -> dict[str, Any] | None:
        payload_candidates = [
            {'file': str(file_id), 'out_format': out_format},
            {'file': str(file_id), 'format': out_format},
            {'file_id': str(file_id), 'out_format': out_format},
        ]
        for payload in payload_candidates:
            try:
                result = await self.call_action('get_record', payload, timeout=25)
            except Exception:
                continue
            if str(result.get('status') or '').lower() == 'ok' and result.get('data') is not None:
                return result
        return None

    async def get_file(self, file_id: str) -> dict[str, Any] | None:
        payload_candidates = [
            {'file': str(file_id)},
            {'file_id': str(file_id)},
            {'id': str(file_id)},
        ]
        for payload in payload_candidates:
            try:
                result = await self.call_action('get_file', payload, timeout=25)
            except Exception:
                continue
            if str(result.get('status') or '').lower() == 'ok' and result.get('data') is not None:
                return result
        return None
