import httpx
import logging

logger = logging.getLogger(__name__)


class PenguinAI:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def chat(self, user_message: str, history: list | None = None):
        """调用 AI 获取回复"""
        messages = list(history or [])
        messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": 2000
                    },
                    timeout=60
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            logger.error("AI API 请求超时")
            return "抱歉，AI 响应超时，请稍后再试"
        except Exception as e:
            logger.error(f"AI API 调用失败: {e}")
            return f"抱歉，AI 服务暂时不可用: {str(e)}"
