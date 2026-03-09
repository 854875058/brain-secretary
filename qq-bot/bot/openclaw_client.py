import asyncio
import json
import logging
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)

VALID_THINKING_LEVELS = {'low', 'medium', 'high', 'xhigh'}
THINKING_ALIASES = {'minimal': 'low'}


class OpenClawError(RuntimeError):
    pass


@dataclass(slots=True)
class OpenClawTurnResult:
    text: str
    media_urls: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class OpenClawClient:
    def __init__(
        self,
        agent_id: str = "",
        thinking: str = "low",
        timeout_seconds: int = 600,
        openclaw_bin: str = "openclaw",
    ):
        self.agent_id = (agent_id or "").strip()
        self.thinking = self._normalize_thinking(thinking)
        self.timeout_seconds = int(timeout_seconds or 600)
        self.openclaw_bin = openclaw_bin

        self._locks = {}
        self._locks_guard = asyncio.Lock()

    @staticmethod
    def _normalize_thinking(value: str | None) -> str:
        normalized = str(value or '').strip().lower()
        normalized = THINKING_ALIASES.get(normalized, normalized)
        if normalized in VALID_THINKING_LEVELS:
            return normalized
        if normalized:
            logger.warning('OpenClaw thinking level %r 不受支持，已回退为 low', value)
        return 'low'

    async def _get_lock(self, session_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[session_id] = lock
            return lock

    @staticmethod
    def _extract_turn_result(response: dict) -> OpenClawTurnResult:
        result = response.get("result") or {}
        payloads = result.get("payloads") or []

        text_parts: list[str] = []
        media_urls: list[str] = []
        if isinstance(payloads, list):
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue

                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.rstrip())

                candidates: list[str] = []
                media_url = payload.get("mediaUrl")
                if isinstance(media_url, str) and media_url.strip():
                    candidates.append(media_url.strip())
                media_urls_list = payload.get("mediaUrls")
                if isinstance(media_urls_list, list):
                    for url in media_urls_list:
                        if isinstance(url, str) and url.strip():
                            candidates.append(url.strip())
                for url in candidates:
                    if url not in media_urls:
                        media_urls.append(url)

        text = "\n".join(text_parts).strip()
        if not text:
            summary = response.get("summary")
            if isinstance(summary, str) and summary.strip():
                text = summary.strip()

        if not text:
            alt = result.get("text") if isinstance(result, dict) else None
            if isinstance(alt, str) and alt.strip():
                text = alt.strip()

        if not text and not media_urls:
            text = "（OpenClaw 未返回可用文本）"

        return OpenClawTurnResult(text=text, media_urls=media_urls, raw=response if isinstance(response, dict) else {})

    async def agent_turn_result(self, session_id: str, message: str) -> OpenClawTurnResult:
        if not session_id or not str(session_id).strip():
            raise OpenClawError("session_id 不能为空")
        if not message or not str(message).strip():
            raise OpenClawError("message 不能为空")

        session_id = str(session_id).strip()
        message = str(message)

        lock = await self._get_lock(session_id)
        async with lock:
            cmd = [
                self.openclaw_bin,
                "agent",
                "--session-id",
                session_id,
                "--message",
                message,
                "--json",
                "--thinking",
                self.thinking,
                "--timeout",
                str(self.timeout_seconds),
            ]
            if self.agent_id:
                cmd.extend(["--agent", self.agent_id])

            logger.info(f"OpenClaw 调用: session={session_id} agent={self.agent_id or '(default)'}")

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as e:
                raise OpenClawError("找不到 openclaw 命令，请确认 OpenClaw CLI 已安装并在 PATH 中") from e

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=max(10, self.timeout_seconds + 30),
                )
            except asyncio.TimeoutError as e:
                process.kill()
                await process.wait()
                raise OpenClawError("OpenClaw 调用超时") from e

            out_text = (stdout or b"").decode("utf-8", errors="replace").strip()
            err_text = (stderr or b"").decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                logger.error(f"OpenClaw 调用失败: rc={process.returncode} stderr={err_text[:500]}")
                hint = "OpenClaw 调用失败。"
                low = err_text.lower() if err_text else ""
                if "unknown agent id" in low:
                    hint = (
                        "OpenClaw 调用失败：未找到配置的 agent_id。请先创建 agent（示例）：\n"
                        'openclaw agents add brain-secretary --workspace "E:\\朗驰\\软研院\\AI数据集项目开发\\测试文件夹" --non-interactive'
                    )
                elif "gateway closed" in low or "econnrefused" in low:
                    hint = "OpenClaw 调用失败：Gateway 未启动或不可达。请先运行：openclaw gateway"
                elif "eperm" in low or "operation not permitted" in low:
                    hint = "OpenClaw 调用失败：权限不足，当前进程无法写入 OpenClaw 数据目录。请用正常权限运行本服务。"
                else:
                    hint += "请确认：Gateway 已启动（openclaw gateway），且本进程有权限写入 OpenClaw 数据目录。"
                snippet = err_text[:300] if err_text else ""
                if snippet:
                    raise OpenClawError(f"{hint}\n\n错误片段:\n{snippet}")
                raise OpenClawError(hint)

            try:
                payload = json.loads(out_text) if out_text else {}
            except Exception:
                logger.error(f"OpenClaw JSON 解析失败，输出前 500 字: {out_text[:500]}")
                return OpenClawTurnResult(text=out_text or "（OpenClaw 返回为空）", media_urls=[], raw={})

            return self._extract_turn_result(payload)

    async def agent_turn(self, session_id: str, message: str) -> str:
        result = await self.agent_turn_result(session_id, message)
        parts: list[str] = []
        if result.text:
            parts.append(result.text)
        for url in result.media_urls:
            if url not in parts:
                parts.append(url)
        return "\n".join(parts).strip() if parts else "（OpenClaw 未返回可用文本）"
