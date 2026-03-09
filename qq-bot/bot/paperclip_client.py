from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_ENV_FILE = PROJECT_ROOT / 'ops' / 'paperclip.local.env'


class PaperclipError(RuntimeError):
    pass


DEFAULT_TIMEOUT_SECONDS = 30


def _load_local_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            raw = line.strip()
            if not raw or raw.startswith('#') or '=' not in raw:
                continue
            key, value = raw.split('=', 1)
            result[key.strip()] = value.strip()
    except Exception as exc:
        logger.warning('读取 Paperclip 本地 env 文件失败: path=%s err=%s', path, exc)
    return result


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
class PaperclipClient:
    enabled: bool = False
    api_base_url: str = ""
    company_id: str = ""
    api_key: str = ""
    auth_cookie: str = ""
    default_assignee_agent_id: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "PaperclipClient":
        config = config or {}
        env_file_value = str(config.get('env_file') or '').strip() or os.environ.get('QQ_BOT_PAPERCLIP_ENV_FILE', '').strip()
        env_file = Path(env_file_value).expanduser() if env_file_value else DEFAULT_LOCAL_ENV_FILE
        local_env = _load_local_env_file(env_file)

        def pick(key: str, config_value: Any = '') -> str:
            env_value = os.environ.get(key)
            if env_value is not None and str(env_value).strip() != '':
                return str(env_value).strip()
            local_value = local_env.get(key)
            if local_value is not None and str(local_value).strip() != '':
                return str(local_value).strip()
            return str(config_value or '').strip()

        enabled_raw = os.environ.get('QQ_BOT_PAPERCLIP_ENABLED')
        if enabled_raw is None:
            enabled_raw = local_env.get('QQ_BOT_PAPERCLIP_ENABLED')
        enabled = (
            str(enabled_raw).strip().lower() in {'1', 'true', 'yes', 'on'}
            if enabled_raw is not None
            else bool(config.get('enabled', False))
        )
        api_base_url = pick('QQ_BOT_PAPERCLIP_API_BASE_URL', config.get('api_base_url') or config.get('base_url') or '')
        company_id = pick('QQ_BOT_PAPERCLIP_COMPANY_ID', config.get('company_id') or '')
        api_key = pick('QQ_BOT_PAPERCLIP_API_KEY', config.get('api_key') or '')
        auth_cookie = pick('QQ_BOT_PAPERCLIP_AUTH_COOKIE', config.get('auth_cookie') or '')
        default_assignee_agent_id = pick('QQ_BOT_PAPERCLIP_DEFAULT_ASSIGNEE_AGENT_ID', config.get('default_assignee_agent_id') or '')
        timeout_raw = os.environ.get('QQ_BOT_PAPERCLIP_TIMEOUT_SECONDS')
        if timeout_raw is None:
            timeout_raw = local_env.get('QQ_BOT_PAPERCLIP_TIMEOUT_SECONDS')
        try:
            timeout_seconds = int(str(timeout_raw).strip()) if timeout_raw is not None and str(timeout_raw).strip() else int(config.get('timeout_seconds') or DEFAULT_TIMEOUT_SECONDS)
        except Exception:
            timeout_seconds = int(config.get('timeout_seconds') or DEFAULT_TIMEOUT_SECONDS)
        return cls(
            enabled=enabled,
            api_base_url=api_base_url.rstrip('/'),
            company_id=company_id,
            api_key=api_key,
            auth_cookie=auth_cookie,
            default_assignee_agent_id=default_assignee_agent_id,
            timeout_seconds=max(3, timeout_seconds),
        )

    @property
    def auth_mode(self) -> str:
        if self.api_key:
            return "bearer"
        if self.auth_cookie:
            return "cookie"
        return "none"

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_base_url)

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "api_base_url": self.api_base_url,
            "company_id": self.company_id,
            "auth_mode": self.auth_mode,
            "default_assignee_agent_id": self.default_assignee_agent_id,
            "timeout_seconds": self.timeout_seconds,
        }

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "brain-secretary-paperclip/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.auth_cookie:
            headers["Cookie"] = self.auth_cookie
        return headers

    def _build_url(self, path: str, query: dict[str, Any] | None = None) -> str:
        if not self.api_base_url:
            raise PaperclipError("Paperclip 未配置 api_base_url")
        base = self.api_base_url.rstrip("/")
        suffix = "/" + str(path or "").lstrip("/")
        if not query:
            return base + suffix
        clean_query = {
            key: value
            for key, value in query.items()
            if value is not None and str(value).strip() != ""
        }
        if not clean_query:
            return base + suffix
        return base + suffix + "?" + urlencode(clean_query)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured:
            raise PaperclipError("Paperclip 未启用或未配置 api_base_url")
        data = None
        headers = self._headers()
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
            detail = body.strip()
            try:
                parsed = json.loads(detail) if detail else {}
            except Exception:
                parsed = {}
            error_text = ""
            if isinstance(parsed, dict):
                error_text = str(parsed.get("error") or parsed.get("message") or "").strip()
            message = error_text or detail or str(getattr(exc, "reason", "") or "unknown error")
            raise PaperclipError(f"Paperclip 请求失败 {exc.code}: {message}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            raise PaperclipError(f"无法连接 Paperclip: {reason or exc}") from exc
        except json.JSONDecodeError as exc:
            raise PaperclipError(f"Paperclip 返回了非法 JSON: {exc}") from exc

    def health(self) -> Any:
        try:
            return self._request("GET", "/api/health")
        except PaperclipError:
            return self._request("GET", "/health")

    def list_companies(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/api/companies")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    def find_company_by_name(self, name: str) -> dict[str, Any] | None:
        needle = str(name or '').strip().lower()
        if not needle:
            return None
        for company in self.list_companies():
            company_name = str(company.get('name') or '').strip().lower()
            if company_name == needle:
                return company
        return None

    def create_company(self, name: str, description: str | None = None) -> dict[str, Any]:
        result = self._request('POST', '/api/companies', payload={
            'name': str(name or '').strip(),
            'description': (description or '').strip() or None,
        })
        if not isinstance(result, dict):
            raise PaperclipError('Paperclip create company 返回格式异常')
        return result

    def resolve_company_id(self) -> str:
        if self.company_id:
            return self.company_id
        companies = self.list_companies()
        if len(companies) == 1:
            company_id = str(companies[0].get("id") or "").strip()
            if company_id:
                return company_id
        raise PaperclipError("未配置 Paperclip company_id；请设置 QQ_BOT_PAPERCLIP_COMPANY_ID 或在配置里填写")

    def list_agents(self) -> list[dict[str, Any]]:
        company_id = self.resolve_company_id()
        result = self._request("GET", f"/api/companies/{quote(company_id, safe='')}/agents")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    def find_agent_by_name(self, ref: str) -> dict[str, Any] | None:
        needle = str(ref or '').strip().lower()
        if not needle:
            return None
        for agent in self.list_agents():
            values = [
                str(agent.get('id') or '').strip().lower(),
                str(agent.get('name') or '').strip().lower(),
                str(agent.get('title') or '').strip().lower(),
                str(agent.get('shortname') or '').strip().lower(),
            ]
            if needle in {value for value in values if value}:
                return agent
        return None

    def create_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        company_id = self.resolve_company_id()
        result = self._request('POST', f'/api/companies/{quote(company_id, safe="")}/agents', payload=payload)
        if not isinstance(result, dict):
            raise PaperclipError('Paperclip create agent 返回格式异常')
        return result

    def update_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request('PATCH', f'/api/agents/{quote(agent_id.strip(), safe="")}', payload=payload)
        if not isinstance(result, dict):
            raise PaperclipError('Paperclip update agent 返回格式异常')
        return result

    def update_agent_permissions(self, agent_id: str, *, can_create_agents: bool) -> dict[str, Any]:
        result = self._request('PATCH', f'/api/agents/{quote(agent_id.strip(), safe="")}/permissions', payload={
            'canCreateAgents': bool(can_create_agents),
        })
        if not isinstance(result, dict):
            raise PaperclipError('Paperclip update agent permissions 返回格式异常')
        return result

    def create_agent_key(self, agent_id: str, *, name: str = 'default') -> dict[str, Any]:
        result = self._request('POST', f'/api/agents/{quote(agent_id.strip(), safe="")}/keys', payload={'name': name})
        if not isinstance(result, dict):
            raise PaperclipError('Paperclip create agent key 返回格式异常')
        return result

    def list_issues(
        self,
        *,
        status: str | None = None,
        assignee_agent_id: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        company_id = self.resolve_company_id()
        result = self._request(
            "GET",
            f"/api/companies/{quote(company_id, safe='')}/issues",
            query={
                "status": status,
                "assigneeAgentId": assignee_agent_id,
                "q": q,
            },
        )
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    def get_issue(self, issue_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/api/issues/{quote(issue_id.strip(), safe='')}")
        if not isinstance(result, dict):
            raise PaperclipError("Paperclip issue 返回格式异常")
        return result

    def create_issue(
        self,
        *,
        title: str,
        description: str | None = None,
        assignee_agent_id: str | None = None,
        priority: str = "medium",
        status: str = "backlog",
        parent_id: str | None = None,
        use_default_assignee: bool = True,
    ) -> dict[str, Any]:
        company_id = self.resolve_company_id()
        payload: dict[str, Any] = {
            "title": title.strip(),
            "description": (description or "").strip() or None,
            "priority": priority,
            "status": status,
        }
        explicit_agent_id = str(assignee_agent_id or "").strip()
        agent_id = explicit_agent_id or (self.default_assignee_agent_id.strip() if use_default_assignee else "") or None
        if agent_id:
            payload["assigneeAgentId"] = agent_id
        normalized_parent_id = str(parent_id or "").strip()
        if normalized_parent_id:
            payload["parentId"] = normalized_parent_id
        result = self._request("POST", f"/api/companies/{quote(company_id, safe='')}/issues", payload=payload)
        if not isinstance(result, dict):
            raise PaperclipError("Paperclip create issue 返回格式异常")
        return result

    def update_issue(
        self,
        issue_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee_agent_id: str | None = None,
        parent_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = str(title).strip()
        if description is not None:
            payload["description"] = (description or "").strip() or None
        if status is not None:
            payload["status"] = str(status).strip()
        if priority is not None:
            payload["priority"] = str(priority).strip()
        if assignee_agent_id is not None:
            normalized_agent_id = str(assignee_agent_id or "").strip()
            payload["assigneeAgentId"] = normalized_agent_id or None
        if parent_id is not None:
            normalized_parent_id = str(parent_id or "").strip()
            payload["parentId"] = normalized_parent_id or None
        if comment is not None:
            payload["comment"] = (comment or "").strip() or None
        if not payload:
            raise PaperclipError("update issue 缺少可更新字段")
        result = self._request("PATCH", f"/api/issues/{quote(issue_id.strip(), safe='')}", payload=payload)
        if not isinstance(result, dict):
            raise PaperclipError("Paperclip update issue 返回格式异常")
        return result

    def wake_agent(
        self,
        agent_id: str,
        *,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        result = self._request(
            "POST",
            f"/api/agents/{quote(agent_id.strip(), safe='')}/wakeup",
            payload={
                "source": "on_demand",
                "triggerDetail": "manual",
                "reason": (reason or "").strip() or None,
                "payload": payload or None,
            },
        )
        if result is None or isinstance(result, dict):
            return result
        raise PaperclipError("Paperclip wake agent 返回格式异常")

    def resolve_agent_ref(self, ref: str) -> dict[str, Any]:
        needle = str(ref or "").strip().lower()
        if not needle:
            raise PaperclipError("agent 标识不能为空")
        agents = self.list_agents()
        exact: list[dict[str, Any]] = []
        fuzzy: list[dict[str, Any]] = []
        for agent in agents:
            values = {
                str(agent.get("id") or "").strip(),
                str(agent.get("name") or "").strip(),
                str(agent.get("title") or "").strip(),
                str(agent.get("shortname") or "").strip(),
            }
            lowered = {value.lower() for value in values if value}
            if needle in lowered:
                exact.append(agent)
                continue
            if any(needle in value for value in lowered):
                fuzzy.append(agent)
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise PaperclipError(f"agent 标识 {ref!r} 命中了多个对象，请改用更精确的 id / 名称")
        if len(fuzzy) == 1:
            return fuzzy[0]
        if len(fuzzy) > 1:
            raise PaperclipError(f"agent 标识 {ref!r} 模糊匹配到多个对象，请改用更精确的 id / 名称")
        raise PaperclipError(f"未找到 Paperclip agent: {ref}")
