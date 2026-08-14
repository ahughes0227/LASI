from datetime import UTC, datetime
from pathlib import Path

import pytest
from services.context import (
    ArtifactContract,
    ContextRequest,
    ContextResolver,
    EvidenceClaim,
    EvidenceItem,
    EvidenceStatus,
    ICMStore,
    OperationalMemoryRetriever,
    PromotionProposal,
    PromotionService,
)
from services.contracts import ApprovalRecord, ProjectConfig
from services.memory import (
    Artifact,
    Base,
    OperationalMemory,
    Project,
    create_engine,
    create_session_factory,
)


def config(project_id: str) -> ProjectConfig:
    return ProjectConfig(
        project_id=project_id,
        project_name=f"Project {project_id}",
        problem_type="classification",
        modality="tabular",
    )


def test_project_icm_isolated_and_context_is_selective(tmp_path: Path) -> None:
    store = ICMStore(tmp_path)
    store.initialize_system()
    store.initialize_project(config("alpha"))
    store.initialize_project(config("beta"))
    assert (tmp_path / "projects/alpha/40_output/limitations.md").is_file()
    assert (tmp_path / "projects/alpha/10_context/prior_findings.md").is_file()
    store.write_artifact(
        "alpha",
        "10_context/domain_context.md",
        "pressure variance and validation",
        overwrite=True,
    )
    store.write_artifact(
        "beta", "10_context/domain_context.md", "unrelated project", overwrite=True
    )

    context = ContextResolver(store).resolve(
        ContextRequest(
            project_id="alpha",
            assignment="review validation",
            keywords=["validation"],
            max_documents=2,
        )
    )

    assert any(
        "validation" in document.content
        for document in context.system_documents + context.project_documents
    )
    assert all("beta" not in document.path for document in context.project_documents)
    assert not any(
        document.path == "policies/escalation.md" for document in context.system_documents
    )


def test_artifact_contract_and_evidence_survive_store_restart(tmp_path: Path) -> None:
    store = ICMStore(tmp_path)
    store.initialize_project(config("alpha"))
    store.write_artifact("alpha", "20_work/exploration/report.md", "EDA complete")
    store.validate_contract(
        "alpha", ArtifactContract(capability="eda", reads=["20_work/exploration/report.md"])
    )
    claim = EvidenceClaim(
        claim_id="claim-1",
        project_id="alpha",
        claim="Validation is temporally sensitive.",
        evidence=[
            EvidenceItem(source="exp-1", type="ablation", result="blocked split changed recall")
        ],
        confidence="high",
        status=EvidenceStatus.SUPPORTED,
    )
    store.write_claim(claim)

    restarted = ICMStore(tmp_path)
    invalidated = restarted.invalidate_claim("alpha", "claim-1", "critic-1")

    assert invalidated.status == EvidenceStatus.INVALIDATED
    assert "critic-1" in invalidated.invalidated_by
    assert (tmp_path / "projects/alpha/30_evidence/failures/claim-1.md").exists()


def test_contract_rejects_path_escape() -> None:
    with pytest.raises(ValueError):
        ArtifactContract(capability="bad", writes=["../outside.md"])


def test_resolver_limits_total_context_and_inherits_only_requested_capability(
    tmp_path: Path,
) -> None:
    store = ICMStore(tmp_path)
    store.initialize_system()
    store.initialize_project(config("alpha"))
    store.write_artifact(
        "alpha", "10_context/domain_context.md", "classification evidence", overwrite=True
    )

    context = ContextResolver(store).resolve(
        ContextRequest(
            project_id="alpha",
            assignment="evaluate evidence",
            capability="evaluation",
            keywords=["evidence", "classification"],
            max_documents=3,
        )
    )

    documents = [*context.system_documents, *context.project_documents]
    assert len(documents) <= 3
    assert any(document.path == "capabilities/evaluation.md" for document in documents)
    assert not any(document.path == "capabilities/modeling.md" for document in documents)

    model_context = ContextResolver(store).resolve(
        ContextRequest(
            project_id="alpha",
            assignment="inspect routing",
            system_paths=["models/registry.yaml"],
            max_documents=1,
        )
    )
    assert [document.path for document in model_context.system_documents] == [
        "models/registry.yaml"
    ]


def test_contract_enforces_declared_writes_and_project_state_reconstructs_after_restart(
    tmp_path: Path,
) -> None:
    store = ICMStore(tmp_path)
    store.initialize_project(config("alpha"))
    contract = ArtifactContract(
        capability="modeling",
        reads=["00_task/objective.md"],
        writes=[
            "20_work/experiments/exp-1/hypothesis.md",
            "20_work/experiments/exp-1/config.yaml",
            "20_work/experiments/exp-1/inputs.md",
            "20_work/experiments/exp-1/results.md",
        ],
    )
    store.validate_contract("alpha", contract)
    store.initialize_experiment(
        "alpha",
        "exp-1",
        hypothesis="A baseline is sufficient.",
        config={"seed": 7},
        inputs=["dataset:v1"],
        contract=contract,
    )
    store.record_experiment_result(
        "alpha",
        "exp-1",
        status="succeeded",
        result="metric improved",
        contract=contract,
    )
    assert (tmp_path / "projects/alpha/20_work/experiments/exp-1/artifacts").is_dir()
    with pytest.raises(PermissionError):
        store.write_artifact("alpha", "40_output/handoff.md", "not allowed", contract=contract)

    state = ICMStore(tmp_path).reconstruct_project_state("alpha")
    assert [(experiment.experiment_id, experiment.status) for experiment in state.experiments] == [
        ("exp-1", "succeeded")
    ]
    assert "A baseline is sufficient" in state.experiments[0].hypothesis


def test_critic_invalidation_marks_affected_experiments_and_dependent_claims(
    tmp_path: Path,
) -> None:
    store = ICMStore(tmp_path)
    store.initialize_project(config("alpha"))
    store.initialize_experiment("alpha", "exp-1", hypothesis="h", config={}, inputs=[])
    store.record_experiment_result("alpha", "exp-1", status="succeeded", result="r")
    store.write_claim(
        EvidenceClaim(
            claim_id="source",
            project_id="alpha",
            claim="Temporal split is valid.",
            confidence="high",
            status=EvidenceStatus.SUPPORTED,
            experiment_ids=["exp-1"],
        )
    )
    store.write_claim(
        EvidenceClaim(
            claim_id="derived",
            project_id="alpha",
            claim="Model generalizes.",
            confidence="medium",
            status=EvidenceStatus.SUPPORTED,
            depends_on_claim_ids=["source"],
        )
    )

    store.invalidate_claim("alpha", "source", "critic found temporal leakage")
    state = store.reconstruct_project_state("alpha")

    assert {claim.claim_id: claim.status for claim in state.claims} == {
        "derived": EvidenceStatus.INVALIDATED,
        "source": EvidenceStatus.INVALIDATED,
    }
    assert state.experiments[0].status == "invalidated"
    assert "source.md" in state.failures
    assert "Claim source invalidated" in (
        tmp_path / "projects/alpha/10_context/current_state.md"
    ).read_text(encoding="utf-8")


def test_experiment_context_inherits_shared_state_without_competing_experiment(
    tmp_path: Path,
) -> None:
    store = ICMStore(tmp_path)
    store.initialize_project(config("alpha"))
    for experiment_id in ("exp-1", "exp-2"):
        store.initialize_experiment(
            "alpha", experiment_id, hypothesis=experiment_id, config={}, inputs=[]
        )
    resolver = ContextResolver(store)

    context = resolver.resolve(
        ContextRequest(
            project_id="alpha",
            assignment="evaluate exp-1",
            experiment_id="exp-1",
            max_documents=20,
        )
    )

    assert any("exp-1" in document.path for document in context.project_documents)
    assert not any("exp-2" in document.path for document in context.project_documents)
    with pytest.raises(ValueError, match="competing"):
        resolver.resolve(
            ContextRequest(
                project_id="alpha",
                assignment="bad handoff",
                experiment_id="exp-1",
                project_paths=["20_work/experiments/exp-2/results.md"],
            )
        )


def test_resolver_retrieves_structured_memory_as_references(tmp_path: Path) -> None:
    store = ICMStore(tmp_path)
    store.initialize_project(config("alpha"))
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    memory.add(
        Project(
            project_id="alpha",
            project_name="Project alpha",
            problem_type="classification",
            modality="tabular",
        )
    )
    memory.add(
        Artifact(
            artifact_id="artifact-1",
            artifact_uri="runs:/run-1/metrics.json",
            artifact_type="metrics",
            project_id="alpha",
        )
    )

    context = ContextResolver(
        store, structured_retriever=OperationalMemoryRetriever(memory)
    ).resolve(ContextRequest(project_id="alpha", assignment="inspect state"))

    assert context.structured_memory_refs == ["sql://artifacts/artifact-1"]


def test_promotion_is_explicit_and_requires_human_approval(tmp_path: Path) -> None:
    store = ICMStore(tmp_path)
    store.initialize_system()
    store.initialize_project(config("alpha"))
    store.write_claim(
        EvidenceClaim(
            claim_id="claim-1",
            project_id="alpha",
            claim="Blocked temporal validation prevents leakage.",
            confidence="high",
            status=EvidenceStatus.STRONGLY_SUPPORTED,
        )
    )
    promotion = PromotionProposal(
        proposal_id="temporal-validation",
        project_id="alpha",
        title="Temporal validation",
        principle="Temporal equipment prediction defaults to blocked validation.",
        source_claim_ids=["claim-1"],
        evidence_references=["claim-1"],
    )
    service = PromotionService(store)
    service.propose(promotion)
    approval = ApprovalRecord(
        approval_id="approve-promotion",
        project_id="alpha",
        action_type="promote_project_lesson",
        risk_level="high",
        requested_by="curator",
        approved_by="research-owner",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )

    principle = service.approve("alpha", promotion.proposal_id, approval)

    assert principle.is_file()
    assert "blocked validation" in principle.read_text(encoding="utf-8")
