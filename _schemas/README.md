# Contract Schemas

The canonical source for LASI contracts is `src/lasi/contracts/models.py`.
`contract_json_schema(Model)` returns the complete JSON Schema emitted by Pydantic;
`validate_contract(Model, value)` validates the same contract at runtime.

The YAML files are stable handoff schemas for authored templates. They use schema
version `1.0` and reject unknown top-level fields. Conformance tests keep the
authored schemas and Pydantic boundary visible while the generated schema remains
the complete source of truth.

Canonical contracts: `ProjectConfig`, `DatasetManifest`, `DatasetVersion`,
`DatasetCharacterization`, `DatasetImprovementProposal`, `ToolSpec`,
`ToolRunResult`, `ExperimentPlan`, `RemoteRunSpec`, `RemoteHostProfile`,
`DiagnosticPacket`, `ProviderProfile`, `ProviderError`, `ScientistReview`,
`DecisionRecord`, `ApprovalRecord`, `ArtifactRecord`, `StaticReportData`,
`ProjectOutcome`, `OutcomeEvent`, `KnowledgeDocument`, `KnowledgeProposal`,
`EvaluationPolicy`.
