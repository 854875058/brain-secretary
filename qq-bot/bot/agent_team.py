from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from bot.openclaw_client import OpenClawClient
from bot.private_kb import CombinedPrivateKnowledgeBase, build_default_private_kb

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
SLUG_RE = re.compile(r"[^a-z0-9]+")

AgentLLMCallable = Callable[[str, "TeamState", "BaseAgentNode"], str | Awaitable[str]]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _slugify(value: str) -> str:
    normalized = SLUG_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or "agent"


def _build_state_session_id(context: str, prefix: str = "agentteam") -> str:
    normalized = str(context or "").strip() or "empty"
    short_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{short_hash}"


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    match = JSON_BLOCK_RE.search(raw)
    if match:
        raw = match.group(1).strip()

    candidates = [raw]
    for index, char in enumerate(raw):
        if char in "{[":
            candidates.append(raw[index:].strip())
            break

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


@dataclass(slots=True)
class TeamStep:
    agent: str
    phase: str
    status_before: str
    status_after: str
    prompt: str
    result: str
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TeamState:
    context: str = ""
    memory_query: str = ""
    memory_retrieved: str = ""
    intermediate_steps: list[TeamStep] = field(default_factory=list)
    final_output: str = ""
    current_status: str = "init"
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    review_rounds: int = 0
    max_review_rounds: int = 1

    def append_step(self, step: TeamStep) -> None:
        self.intermediate_steps.append(step)

    def last_step(self, phase: str | None = None) -> TeamStep | None:
        for step in reversed(self.intermediate_steps):
            if phase is None or step.phase == phase:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["intermediate_steps"] = [step.to_dict() for step in self.intermediate_steps]
        return payload


class BaseAgentNode:
    def __init__(
        self,
        name: str,
        role_prompt: str,
        *,
        phase: str,
        agent_id: str = "",
        thinking: str = "low",
        timeout_seconds: int = 600,
        llm_callable: AgentLLMCallable | None = None,
    ):
        self.name = name
        self.role_prompt = role_prompt.strip()
        self.phase = phase
        self.agent_id = str(agent_id or "").strip()
        self.llm_callable = llm_callable
        self._client = None
        if self.llm_callable is None and self.agent_id:
            self._client = OpenClawClient(
                agent_id=self.agent_id,
                thinking=thinking,
                timeout_seconds=timeout_seconds,
            )

    def _build_agent_session_id(self, state: TeamState) -> str:
        base = state.session_id or _build_state_session_id(state.context)
        return f"{base}:{self.phase}:{_slugify(self.name)}"

    async def call_llm(self, prompt: str, state: TeamState) -> str:
        if self.llm_callable is not None:
            result = self.llm_callable(prompt, state, self)
            if inspect.isawaitable(result):
                result = await result
            return str(result or "").strip()
        if self._client is None:
            raise RuntimeError(f"{self.name} 未配置 llm_callable 或 agent_id")
        return await self._client.agent_turn(self._build_agent_session_id(state), prompt)

    async def execute(self, state: TeamState) -> TeamState:
        raise NotImplementedError


class ResearchAgentNode(BaseAgentNode):
    def __init__(self, *args: Any, knowledge_base: CombinedPrivateKnowledgeBase, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.knowledge_base = knowledge_base

    async def execute(self, state: TeamState) -> TeamState:
        state.current_status = "researching"
        memory_query = state.memory_query or state.context
        memory_context = self.knowledge_base.render_context(memory_query, limit=6)
        state.memory_retrieved = memory_context

        prompt = "\n".join(
            [
                f"角色: {self.role_prompt}",
                f"原始需求:\n{state.context}",
                f"私有知识库:\n{memory_context or '(无命中，按通用工程标准分析)'}",
                "输出要求：",
                "1. 提炼业务规则和隐性约束",
                "2. 给出后续执行计划",
                "3. 明确需要严格遵守的输出格式和风险点",
            ]
        ).strip()

        result = await self.call_llm(prompt, state)
        state.metadata["research_summary"] = result
        state.append_step(
            TeamStep(
                agent=self.name,
                phase=self.phase,
                status_before="researching",
                status_after="coding",
                prompt=prompt,
                result=result,
                metadata={
                    "agent_id": self.agent_id,
                    "memory_query": memory_query,
                    "memory_attached": bool(memory_context),
                },
            )
        )
        state.current_status = "coding"
        return state


class ExecutionAgentNode(BaseAgentNode):
    async def execute(self, state: TeamState) -> TeamState:
        state.current_status = "coding"
        research_summary = str(state.metadata.get("research_summary") or "").strip()
        review_feedback = str(state.metadata.get("review_feedback") or "").strip()

        prompt_parts = [
            f"角色: {self.role_prompt}",
            f"原始需求:\n{state.context}",
            f"研究结论:\n{research_summary or '(无)'}",
            f"私有知识库:\n{state.memory_retrieved or '(无)'}",
        ]
        if review_feedback:
            prompt_parts.append(f"上轮复核反馈:\n{review_feedback}")
        prompt_parts.extend(
            [
                "执行要求：",
                "1. 直接产出可交付结果",
                "2. 如果需要结构化输出，优先给严格 JSON 或稳定 Markdown",
                "3. 不要只给建议，要给可以直接落地的内容",
            ]
        )
        prompt = "\n".join(prompt_parts).strip()

        result = await self.call_llm(prompt, state)
        state.final_output = result
        state.append_step(
            TeamStep(
                agent=self.name,
                phase=self.phase,
                status_before="coding",
                status_after="reviewing",
                prompt=prompt,
                result=result,
                metadata={
                    "agent_id": self.agent_id,
                    "review_feedback_used": bool(review_feedback),
                },
            )
        )
        state.current_status = "reviewing"
        return state


class ReviewAgentNode(BaseAgentNode):
    def __init__(self, *args: Any, knowledge_base: CombinedPrivateKnowledgeBase, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.knowledge_base = knowledge_base

    @staticmethod
    def _parse_review_payload(text: str) -> dict[str, Any]:
        payload = _extract_json_object(text)
        if payload is not None:
            return payload

        normalized = str(text or "").strip().lower()
        approved = False
        if "approved" in normalized or "通过" in normalized:
            approved = "未通过" not in normalized and "not approved" not in normalized
        feedback = str(text or "").strip() or "未提供结构化复核结果"
        return {
            "approved": approved,
            "feedback": feedback,
            "remember": False,
            "memory_note": "",
        }

    async def execute(self, state: TeamState) -> TeamState:
        state.current_status = "reviewing"
        prompt = "\n".join(
            [
                f"角色: {self.role_prompt}",
                f"原始需求:\n{state.context}",
                f"研究摘要:\n{state.metadata.get('research_summary') or '(无)'}",
                f"候选交付物:\n{state.final_output or '(空)'}",
                "请严格返回 JSON，字段如下：",
                '{"approved": true/false, "feedback": "...", "remember": true/false, "memory_note": "..."}',
                "approved=true 表示可以交付；approved=false 表示要打回执行节点继续修。",
            ]
        ).strip()

        result = await self.call_llm(prompt, state)
        payload = self._parse_review_payload(result)
        approved = bool(payload.get("approved"))
        feedback = str(payload.get("feedback") or "").strip()
        remember = bool(payload.get("remember"))
        memory_note = str(payload.get("memory_note") or "").strip()

        next_status = "done"
        if not approved and state.review_rounds < state.max_review_rounds:
            state.review_rounds += 1
            state.metadata["review_feedback"] = feedback or result
            next_status = "coding"
        elif not approved:
            state.errors.append(feedback or "review_not_approved")
            state.metadata["review_feedback"] = feedback or result

        if approved and remember and memory_note:
            remember_result = self.knowledge_base.remember(memory_note, kind="workflow", source="agentteam-review")
            state.metadata["memory_writeback"] = remember_result or {}

        state.metadata["review_result"] = payload
        state.append_step(
            TeamStep(
                agent=self.name,
                phase=self.phase,
                status_before="reviewing",
                status_after=next_status,
                prompt=prompt,
                result=result,
                metadata={
                    "agent_id": self.agent_id,
                    "review_payload": payload,
                },
            )
        )
        state.current_status = next_status
        return state


class StateGraphCoordinator:
    def __init__(self, nodes: dict[str, BaseAgentNode], *, max_loops: int = 12):
        self.nodes = dict(nodes)
        self.max_loops = max(2, int(max_loops))

    async def run(
        self,
        initial_context: str,
        *,
        memory_query: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        max_review_rounds: int = 1,
    ) -> TeamState:
        state = TeamState(
            context=str(initial_context or "").strip(),
            memory_query=str(memory_query or initial_context or "").strip(),
            session_id=str(session_id or "").strip() or _build_state_session_id(initial_context),
            current_status="researching",
            metadata=dict(metadata or {}),
            max_review_rounds=max(0, int(max_review_rounds)),
        )

        loop_count = 0
        while state.current_status != "done":
            loop_count += 1
            if loop_count > self.max_loops:
                state.errors.append("state_graph_loop_limit_exceeded")
                state.current_status = "done"
                break

            node = self.nodes.get(state.current_status)
            if node is None:
                state.errors.append(f"missing_node:{state.current_status}")
                state.current_status = "done"
                break

            try:
                state = await node.execute(state)
            except Exception as exc:
                state.errors.append(str(exc))
                state.append_step(
                    TeamStep(
                        agent=node.name,
                        phase=node.phase,
                        status_before=state.current_status,
                        status_after="done",
                        prompt="",
                        result="",
                        error=str(exc),
                        metadata={"agent_id": node.agent_id},
                    )
                )
                state.current_status = "done"
                break
        return state

    def run_sync(
        self,
        initial_context: str,
        *,
        memory_query: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        max_review_rounds: int = 1,
    ) -> TeamState:
        return asyncio.run(
            self.run(
                initial_context,
                memory_query=memory_query,
                metadata=metadata,
                session_id=session_id,
                max_review_rounds=max_review_rounds,
            )
        )


def build_default_agent_team(
    *,
    knowledge_base: CombinedPrivateKnowledgeBase | None = None,
    researcher_callable: AgentLLMCallable | None = None,
    executor_callable: AgentLLMCallable | None = None,
    reviewer_callable: AgentLLMCallable | None = None,
    researcher_agent_id: str = "brain-secretary-dev",
    executor_agent_id: str = "brain-secretary-dev",
    reviewer_agent_id: str = "brain-secretary-review",
    thinking: str = "low",
    timeout_seconds: int = 900,
) -> StateGraphCoordinator:
    kb = knowledge_base or build_default_private_kb()
    nodes: dict[str, BaseAgentNode] = {
        "researching": ResearchAgentNode(
            "需求架构师",
            "你负责理解业务需求、提取规则、识别隐性约束，并给出可执行计划。",
            phase="research",
            knowledge_base=kb,
            agent_id=researcher_agent_id,
            thinking=thinking,
            timeout_seconds=timeout_seconds,
            llm_callable=researcher_callable,
        ),
        "coding": ExecutionAgentNode(
            "执行工程师",
            "你负责严格按照研究结论、私有规则和复核反馈产出最终交付物。",
            phase="execute",
            agent_id=executor_agent_id,
            thinking=thinking,
            timeout_seconds=timeout_seconds,
            llm_callable=executor_callable,
        ),
        "reviewing": ReviewAgentNode(
            "验收复核员",
            "你负责验收最终结果，判断能否交付，并在必要时沉淀新的长期规则。",
            phase="review",
            knowledge_base=kb,
            agent_id=reviewer_agent_id,
            thinking=thinking,
            timeout_seconds=timeout_seconds,
            llm_callable=reviewer_callable,
        ),
    }
    return StateGraphCoordinator(nodes)
