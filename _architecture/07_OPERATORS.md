# Operators

An OperatorSpec declares name, version, risk, JSON input/output shape, side effects,
idempotency, approval requirements, implementation digest, process limits, and allowed
environment names. The runtime invokes only registered module entrypoints and can
validate typed Pydantic input and output models. Registry entries contain no in-process
callables.

A declared JSON schema is accepted only with the corresponding executable Pydantic
model, and must match that model. If omitted, the registry derives the planner-visible
schema from the model. This prevents documentation-only schemas from being mistaken
for enforcement.

Data intake, characterization, experiments, evaluation, remote execution, reports,
outcomes, and production actions return as ordinary domain operators. This keeps
domain behavior deterministic without recreating a workflow framework.

The core contains only small health-test operators. Domain behavior must return as a
new registered operator with contracts and tests; it must not revive a parallel tool,
workflow, capability, component, or dynamic-code system.
