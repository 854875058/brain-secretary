import httpx
import logging

logger = logging.getLogger(__name__)


class PenguinAI:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(self, user_message: str, history: list | None = None):
        """调用 AI 获取回复"""
        messages = list(history or [])
        messages.append({"role": "user", "content": user_message})

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 2000
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            logger.error("AI API 请求超时")
            return "抱歉，AI 响应超时，请稍后再试"
        except Exception as e:
            logger.error(f"AI API 调用失败: {e}")
            return f"抱歉，AI 服务暂时不可用: {str(e)}"
