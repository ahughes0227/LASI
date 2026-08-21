# Operators

An OperatorSpec declares name, version, risk, JSON input/output shape, side effects,
idempotency, and approval requirements. The runtime invokes only registered
implementations and can validate typed Pydantic input and output models.

Data intake, characterization, experiments, evaluation, remote execution, reports,
outcomes, and production actions return as ordinary domain operators. This keeps
domain behavior deterministic without recreating a workflow framework.
