from __future__ import annotations

from types import SimpleNamespace

import pytest
from services.artifacts import ArtifactStore
from services.contracts import (
    ApprovalGrant,
    ExecutionGrant,
    OperatorSpec,
    PlannerProfile,
    RiskLevel,
)
from services.execution import DeterministicExecutor, SubprocessOperatorRunner
from services.identity import ApprovalService, IdentityService, LocalSigner
from services.ledger import AuthorityStore
from services.operators import OperatorRegistry
from services.policy import PlanVerifier


@pytest.fixture
def core(tmp_path):
    store = AuthorityStore(tmp_path / "state.sqlite3")
    identities = IdentityService(store, policy_version="policy-v1")
    signers = {
        name: LocalSigner.generate(name)
        for name in ("requester", "planner-service", "approver-1", "approver-2")
    }
    for signer in signers.values():
        store.register_identity(signer.identity_record())
    for subject in ("requester", "planner-service"):
        store.add_execution_grant(
            ExecutionGrant(
                grant_id=f"execute-{subject}",
                subject_id=subject,
                operators=frozenset({"*"}),
                max_risk=RiskLevel.CRITICAL,
            )
        )
    for subject in ("approver-1", "approver-2"):
        store.add_approval_grant(
            ApprovalGrant(
                grant_id=f"approve-{subject}",
                subject_id=subject,
                max_risk=RiskLevel.CRITICAL,
            )
        )
    profile = PlannerProfile(
        profile_id="planner-profile",
        service_identity_id="planner-service",
        model="mock/model",
    )
    store.save_planner_profile(profile)
    registry = OperatorRegistry()
    registry.register(
        OperatorSpec(
            name="echo",
            description="Echo arguments.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="echo-v1",
        )
    )
    approvals = ApprovalService(store, identities)
    verifier = PlanVerifier(registry, store, identities, approvals)
    runner = SubprocessOperatorRunner(
        tmp_path / "workspaces", ArtifactStore(tmp_path / "artifacts")
    )
    executor = DeterministicExecutor(registry, store, verifier, runner)
    return SimpleNamespace(
        store=store,
        identities=identities,
        signers=signers,
        profile=profile,
        registry=registry,
        approvals=approvals,
        verifier=verifier,
        runner=runner,
        executor=executor,
        root=tmp_path,
    )
