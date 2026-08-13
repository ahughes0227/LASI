"""Automatic review boundary for project-scoped experimental components."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from services.contracts import ComponentRequest, ComponentReview
from services.contracts.models import BudgetEstimate, Provenance

from .registry import ComponentHandler, ComponentRegistry


@dataclass(frozen=True)
class ComponentReviewContext:
    """Evidence produced by source, dependency, test, and containment inspection."""

    source_hash_verified: bool
    tests_passed: bool
    config_schema_strict: bool
    static_handler_binding: bool
    isolation_enforced: bool
    approved_dependencies: frozenset[str] = frozenset()
    resource_envelope: BudgetEstimate = field(default_factory=BudgetEstimate)


class ComponentReviewService:
    """Approve safe project-local components and escalate genuine system risk."""

    def evaluate(
        self, request: ComponentRequest, *, context: ComponentReviewContext
    ) -> ComponentReview:
        security = {
            "project_scope": request.requested_scope == "project_experimental",
            "source_hash": context.source_hash_verified,
            "network_denied": not request.requires_network,
            "subprocess_denied": not request.requires_subprocess,
            "external_provider_denied": not request.requires_external_provider,
            "secrets_denied": not request.requires_secrets,
            "native_code_absent": not request.includes_native_code,
            "workdir_confined": not request.writes_outside_workdir,
            "shared_state_immutable": not request.mutates_shared_state,
            "dependencies_approved": set(request.dependencies).issubset(
                context.approved_dependencies
            ),
            "isolation_enforced": context.isolation_enforced,
        }
        stability = {
            "tests_passed": context.tests_passed,
            "strict_config_schema": context.config_schema_strict,
            "static_handler_binding": context.static_handler_binding,
            "resources_bounded": _within_budget(
                request.expected_resource_use, context.resource_envelope
            ),
            "typed_outputs_declared": bool(request.component.outputs),
            "tests_referenced": bool(request.test_refs),
        }
        security_failures = [name for name, passed in security.items() if not passed]
        stability_failures = [name for name, passed in stability.items() if not passed]

        if request.requested_scope == "shared_toolbox":
            return self._review(
                request,
                decision="escalate_for_human_review",
                allowed=False,
                risk_level="high",
                security=security,
                stability=stability,
                blocked_by=["shared_toolbox_promotion"],
                rationale="Shared toolbox promotion changes the trusted system surface.",
            )
        if security_failures:
            return self._review(
                request,
                decision="escalate_for_human_review",
                allowed=False,
                risk_level="high",
                security=security,
                stability=stability,
                blocked_by=security_failures,
                rationale="The component may cross a security or isolation boundary.",
            )
        if stability_failures:
            return self._review(
                request,
                decision="request_revision",
                allowed=False,
                risk_level="medium",
                security=security,
                stability=stability,
                required_revisions=stability_failures,
                rationale="The component needs stronger stability evidence before execution.",
            )
        return self._review(
            request,
            decision="auto_approve_project_experimental",
            allowed=True,
            risk_level="low",
            security=security,
            stability=stability,
            rationale="Security, containment, interface, resource, and stability checks passed.",
        )

    @staticmethod
    def approve_and_register(
        request: ComponentRequest,
        review: ComponentReview,
        registry: ComponentRegistry,
        config_model: type[BaseModel],
        handler: ComponentHandler,
    ) -> None:
        if not review.allowed or review.decision != "auto_approve_project_experimental":
            raise PermissionError("component review does not authorize experimental registration")
        if review.request_id != request.request_id or review.project_id != request.project_id:
            raise PermissionError("component review does not match the request")
        if (
            review.component_id != request.component.component_id
            or review.component_version != request.component.version
            or review.source_hash != request.source_hash
        ):
            raise PermissionError("component review does not match component source")
        if not registry.allow_experimental:
            raise PermissionError("registry does not allow experimental components")
        if registry.experimental_project_id != request.project_id:
            raise PermissionError("experimental registry belongs to another project")
        source = inspect.getsourcefile(handler)
        if source is None or Path(source).resolve() != Path(request.source_ref).resolve():
            raise PermissionError("component handler is not statically bound to requested source")
        observed_hash = f"sha256:{sha256(Path(source).read_bytes()).hexdigest()}"
        if observed_hash != request.source_hash:
            raise PermissionError("component handler source does not match requested source hash")
        experimental = request.component.model_copy(update={"lifecycle": "experimental"})
        registry.register(experimental, config_model, handler, source_hash=request.source_hash)

    @staticmethod
    def _review(
        request: ComponentRequest,
        *,
        decision: str,
        allowed: bool,
        risk_level: str,
        security: dict[str, bool],
        stability: dict[str, bool],
        blocked_by: list[str] | None = None,
        required_revisions: list[str] | None = None,
        rationale: str,
    ) -> ComponentReview:
        return ComponentReview(
            review_id=f"component-review-{uuid4().hex}",
            request_id=request.request_id,
            project_id=request.project_id,
            component_id=request.component.component_id,
            component_version=request.component.version,
            source_hash=request.source_hash,
            decision=decision,
            allowed=allowed,
            risk_level=risk_level,
            security_checks=security,
            stability_checks=stability,
            blocked_by=blocked_by or [],
            required_revisions=required_revisions or [],
            rationale=rationale,
            created_at=datetime.now(UTC),
            provenance=Provenance(
                project_id=request.project_id,
                source_records=[request.request_id],
                content_hash=request.source_hash,
            ),
        )


def _within_budget(requested: BudgetEstimate, available: BudgetEstimate) -> bool:
    for budget_field in (
        "cost_usd",
        "cpu_hours",
        "gpu_hours",
        "wall_time_minutes",
        "memory_gb",
        "storage_gb",
    ):
        need = getattr(requested, budget_field)
        limit = getattr(available, budget_field)
        if need is not None and (limit is None or need > limit):
            return False
    return True
