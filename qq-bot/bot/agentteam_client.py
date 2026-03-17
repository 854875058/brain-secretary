from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20


class AgentTeamError(RuntimeError):
    pass


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _str_env(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip()


@dataclass(slots=True)
class AgentTeamClient:
    enabled: bool = False
    api_base_url: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    label: str = "AgentTeam"

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "AgentTeamClient":
        config = config or {}
        enabled = _bool_env("QQ_BOT_AGENTTEAM_ENABLED", bool(config.get("enabled", False)))
        api_base_url = _str_env(
            "QQ_BOT_AGENTTEAM_API_BASE_URL",
            str(config.get("api_base_url") or config.get("base_url") or ""),
        ).rstrip("/")
        timeout_seconds = max(
            3,
            _int_env("QQ_BOT_AGENTTEAM_TIMEOUT_SECONDS", int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)),
        )
        label = _str_env("QQ_BOT_AGENTTEAM_LABEL", str(config.get("label") or "AgentTeam")) or "AgentTeam"
        return cls(
            enabled=enabled,
            api_base_url=api_base_url,
            timeout_seconds=timeout_seconds,
            label=label,
        )

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_base_url)

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "api_base_url": self.api_base_url,
            "timeout_seconds": self.timeout_seconds,
            "label": self.label,
        }

    def _build_url(self, path: str, query: dict[str, Any] | None = None) -> str:
        if not self.api_base_url:
            raise AgentTeamError("AgentTeam 未配置 api_base_url")
        suffix = "/" + str(path or "").lstrip("/")
        if not query:
            return self.api_base_url + suffix
        clean_query = {
            key: value
            for key, value in query.items()
            if value is not None and str(value).strip() != ""
        }
        if not clean_query:
            return self.api_base_url + suffix
        return self.api_base_url + suffix + "?" + urlencode(clean_query)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured:
            raise AgentTeamError("AgentTeam 未启用或未配置 api_base_url")
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "brain-secretary-agentteam/1.0",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self._build_url(path, query=query), data=data, method=method.upper(), headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return None
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = body.strip() or str(getattr(exc, "reason", "") or "unknown error")
            raise AgentTeamError(f"AgentTeam 请求失败 {exc.code}: {message}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            raise AgentTeamError(f"无法连接 AgentTeam: {reason or exc}") from exc
        except json.JSONDecodeError as exc:
            raise AgentTeamError(f"AgentTeam 返回了非法 JSON: {exc}") from exc

    def status(self) -> dict[str, Any]:
        result = self._request("GET", "/status")
        if isinstance(result, dict):
            return result
        raise AgentTeamError("AgentTeam /status 返回格式异常")

    def list_tasks(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/tasks")
        if isinstance(result, dict):
            items = result.get("tasks")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        raise AgentTeamError("AgentTeam /tasks 返回格式异常")

    def get_task(self, task_id: int) -> dict[str, Any]:
        result = self._request("GET", f"/tasks/{int(task_id)}")
        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        raise AgentTeamError("AgentTeam /tasks/{id} 返回格式异常")

    def list_requests(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/requests")
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, dict):
                items = data.get("items")
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        raise AgentTeamError("AgentTeam /requests 返回格式异常")

    def create_request(
        self,
        *,
        title: str,
        description: str,
        priority: int = 3,
        acceptance_criteria: str = "",
    ) -> dict[str, Any]:
        result = self._request(
            "POST",
            "/requests",
            payload={
                "title": str(title or "").strip(),
                "description": str(description or "").strip(),
                "priority": max(1, min(int(priority or 3), 5)),
                "acceptance_criteria": str(acceptance_criteria or "").strip(),
            },
        )
        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        raise AgentTeamError("AgentTeam 创建需求返回格式异常")
