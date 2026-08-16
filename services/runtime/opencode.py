"""OpenCode adapter for structured SQL-issued agent tasks."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from services.contracts import (
    BUILDER_AGENT_ROLES,
    AgentInvocationResult,
    AgentResult,
    AgentTask,
    ProviderTokenUsage,
    validate_agent_role,
)
from services.core import AGENT_ENVIRONMENT_ALLOWLIST, build_child_environment

from .opencode_cli import validate_opencode_runtime
from .task_runtime import default_reasoning_rubrics

_RESULT = re.compile(r"<LASI_AGENT_RESULT>\s*(\{.*?\})\s*</LASI_AGENT_RESULT>", re.DOTALL)


class OpenCodeTaskInvoker:
    """Invoke exactly one leased task and capture its runtime usage receipt."""

    def __init__(self, workspace: Path, *, executable: str | None = None) -> None:
        self.workspace = workspace.resolve()
        self.executable = executable or os.environ.get("LASI_OPENCODE_EXECUTABLE", "opencode")

    def invoke(self, task: AgentTask) -> AgentInvocationResult:
        executable = validate_opencode_runtime(self.executable)
        completed = subprocess.run(  # noqa: S603 - resolved executable, no shell.
            [
                executable,
                "run",
                "--agent",
                task.task.agent_role,
                "--format",
                "json",
                "--auto",
                "--dir",
                str(self.workspace),
                "--title",
                f"LASI task {task.task.task_id} attempt {task.attempt_id}",
                _task_prompt(task),
            ],
            cwd=self.workspace,
            text=True,
            capture_output=True,
            timeout=3600,
            check=False,
            env=_agent_environment(task.task.agent_role),
        )
        response_dir = self.workspace / ".lasi" / "agent-responses"
        response_dir.mkdir(parents=True, exist_ok=True)
        response_path = response_dir / f"{task.attempt_id}.jsonl"
        response_path.write_text(completed.stdout, encoding="utf-8")
        usage = _usage_receipt(completed.stdout, source_reference=str(response_path))
        if completed.returncode != 0:
            return AgentInvocationResult(
                result=AgentResult(
                    task_id=task.task.task_id,
                    attempt_id=task.attempt_id,
                    status="failed",
                    summary="OpenCode agent invocation failed.",
                    criterion_results=[],
                    failure_reason=(
                        f"OpenCode exited {completed.returncode}: {completed.stderr[-1000:]}"
                    ),
                ),
                usage=usage,
                raw_response_artifact_ref=str(response_path),
            )
        text = _event_text(completed.stdout)
        matches = list(_RESULT.finditer(text))
        if not matches:
            result = AgentResult(
                task_id=task.task.task_id,
                attempt_id=task.attempt_id,
                status="failed",
                summary="Agent omitted the required structured return.",
                criterion_results=[],
                failure_reason="response did not contain LASI_AGENT_RESULT",
            )
        else:
            try:
                result = AgentResult.model_validate_json(matches[-1].group(1))
            except ValidationError as exc:
                # A rejected return (an undispatchable agent_role in a proposed
                # task graph, for instance) stays attributable evidence.
                result = AgentResult(
                    task_id=task.task.task_id,
                    attempt_id=task.attempt_id,
                    status="failed",
                    summary="Agent returned a structurally invalid result.",
                    criterion_results=[],
                    failure_reason=f"LASI_AGENT_RESULT failed contract validation: {exc}",
                )
        return AgentInvocationResult(
            result=result,
            usage=usage,
            raw_response_artifact_ref=str(response_path),
        )


def _task_prompt(task: AgentTask) -> str:
    available_rubrics = ", ".join(
        f"{item.rubric_id}@{item.version}" for item in default_reasoning_rubrics()
    )
    return f"""You are executing one SQL-issued LASI task. The runtime owns state.

Do not write operational state or claim authorization. Use the reasoning rubric
in the task envelope as your analysis procedure. Read only the minimum context
and artifact references needed for this task. Return artifacts and evidence
references, not unstructured handoff state.

Task envelope:
{task.model_dump_json(indent=2)}

Task rubric keys currently accepted by the runtime:
{available_rubrics}

Before returning, address every rubric criterion. For evidentiary criteria,
include durable evidence references. A scientific checkpoint must return claims
as explicit observations, inferences, or hypotheses. A scientific-critic task
must return critic_assessment and try to disprove the claim rather than merely
summarize it.

Return exactly one JSON object in these tags:
<LASI_AGENT_RESULT>
{{"task_id":"{task.task.task_id}","attempt_id":"{task.attempt_id}","status":"completed|partial|failed|blocked","summary":"...","criterion_results":[],"artifacts":[],"observations":[],"claims":[],"critic_assessment":null,"task_graph_proposal":null,"experiment_plans":[],"recommended_followup_tasks":[],"recommended_assignment_status":null,"knowledge_proposal_refs":[],"failure_reason":null}}
</LASI_AGENT_RESULT>

The coordinator is planning-only. For an orchestration task, return either a
versioned task_graph_proposal plus recommended_assignment_status="continue", or
recommended_assignment_status="complete". Do not execute proposed tasks during
the orchestration turn.
"""


def _agent_environment(agent_role: str) -> dict[str, str]:
    validate_agent_role(agent_role)
    environment = build_child_environment(
        AGENT_ENVIRONMENT_ALLOWLIST,
        overrides={"LASI_INTERNAL_TASK_AGENT": "1"},
    )
    raw = environment.get("OPENCODE_CONFIG_CONTENT")
    inline = json.loads(raw) if raw else {}
    if not isinstance(inline, dict):
        raise ValueError("OPENCODE_CONFIG_CONTENT must be a JSON object")
    agents = inline.setdefault("agent", {})
    if not isinstance(agents, dict):
        raise ValueError("inline OpenCode agent configuration must be an object")
    agent = agents.setdefault(agent_role, {})
    if not isinstance(agent, dict):
        raise ValueError("inline OpenCode agent configuration must be an object")
    agent["mode"] = "primary"
    if agent_role not in BUILDER_AGENT_ROLES:
        # Promotion to primary must not become a permission grant: only the
        # governed package builders write files or run commands.
        agent["permission"] = {**agent.get("permission", {}), "edit": "deny", "bash": "deny"}
    inline["default_agent"] = agent_role
    environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(inline)
    return environment


def _usage_receipt(raw: str, *, source_reference: str) -> ProviderTokenUsage | None:
    candidates: list[dict[str, object]] = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        _collect_usage(value, candidates)
    for candidate in reversed(candidates):
        normalized = _normalize_usage(candidate)
        if normalized is not None:
            return ProviderTokenUsage(
                reporting_source="opencode_runtime_json",
                source_reference=source_reference,
                reported_at=datetime.now(UTC),
                total_tokens=int(normalized["total_tokens"]),
                input_tokens=(
                    int(normalized["input_tokens"]) if "input_tokens" in normalized else None
                ),
                output_tokens=(
                    int(normalized["output_tokens"]) if "output_tokens" in normalized else None
                ),
                cached_input_tokens=(
                    int(normalized["cached_input_tokens"])
                    if "cached_input_tokens" in normalized
                    else None
                ),
                billed_cost_usd=(
                    float(normalized["billed_cost_usd"])
                    if "billed_cost_usd" in normalized
                    else None
                ),
            )
    return None


def _collect_usage(value: object, candidates: list[dict[str, object]]) -> None:
    if isinstance(value, Mapping):
        if any(key in value for key in ("total_tokens", "totalTokens", "tokens")):
            candidates.append(dict(value))
        for child in value.values():
            _collect_usage(child, candidates)
    elif isinstance(value, list):
        for child in value:
            _collect_usage(child, candidates)


def _normalize_usage(value: dict[str, object]) -> dict[str, int | float] | None:
    nested = value.get("tokens")
    source = dict(nested) if isinstance(nested, Mapping) else value
    input_tokens = _integer(source, "input_tokens", "inputTokens", "input")
    output_tokens = _integer(source, "output_tokens", "outputTokens", "output")
    cached_tokens = _integer(source, "cached_input_tokens", "cachedInputTokens", "cache_read")
    total_tokens = _integer(source, "total_tokens", "totalTokens", "total")
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    if total_tokens is None:
        return None
    result: dict[str, int | float] = {"total_tokens": total_tokens}
    if input_tokens is not None:
        result["input_tokens"] = input_tokens
    if output_tokens is not None:
        result["output_tokens"] = output_tokens
    if cached_tokens is not None:
        result["cached_input_tokens"] = cached_tokens
    cost = value.get("cost") or value.get("billed_cost_usd")
    if isinstance(cost, int | float) and cost >= 0:
        result["billed_cost_usd"] = float(cost)
    return result


def _integer(value: Mapping[str, object], *keys: str) -> int | None:
    for key in keys:
        item = value.get(key)
        if isinstance(item, int) and item >= 0:
            return item
    return None


def _event_text(raw: str) -> str:
    values: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            values.append(line)
            continue
        values.extend(_text_values(event))
    return "\n".join(values)


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _text_values(child)]
    if isinstance(value, Mapping):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return [str(value["text"])]
        return [item for child in value.values() for item in _text_values(child)]
    return []
