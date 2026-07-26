Starter Glossary
================

- LASI: Learning as a Service — institutional ML research harness.
- Dataset Version: an immutable snapshot or manifest describing a dataset state.
- Dataset Characterization: structured summary of dataset properties and failure modes.
- Experiment Plan: ordered set of experiments with inputs, metrics, and expected outcomes.
- Tool Run: a recorded execution of a tool with inputs, outputs, and provenance.
- Remote Run: a tool run executed on a remote host with host profile and logs.
- Diagnostic Packet: collected artifacts (metrics, plots, logs) that summarize an experiment.
- Scientist Review: provider-created analysis and recommendations (not authority).
- Decision Record: human-authored approval/rejection with rationale and scope.
- Static Report Data: structured content used to render fixed reports.
- Project Outcome: final status of a project (validated, deployed, failed, etc.).
- Knowledge Document: Git-backed markdown fact, policy, lesson, or hypothesis.
- Knowledge Proposal: a draft change to knowledge requiring review/approval.
- Sabbatical Review: periodic, scoped retrospective to surface lessons and open questions.
- Foundation Opportunity: assessment of whether a reusable representation should be pursued.
- Challenge Spec: strict, user-confirmed definition of a local benchmark challenge and its evaluation/submission rules.
- Prediction Artifact: immutable model output tied to a challenge, test dataset version, model run, checksum, and schema.
- Submission Validation: structured check that a prediction artifact conforms to the required challenge submission schema.
- Hidden Evaluator: evaluator-only boundary that may read hidden labels and returns aggregate metrics without per-row comparisons.
- Benchmark Isolation: fail-closed execution policy preventing answer lookup, network access, external providers, remote execution, arbitrary subprocesses, and hidden-label access.
- OpenCode Operating Surface: the supported user and agent interface consisting of OpenCode commands, agents, and skills.
- Reusable Python Service: implementation-layer code invoked by OpenCode procedures; it is not a separate user-facing operating surface.
- Canonical Skill Identifier: the hyphenated skill name and discovery path under `.opencode/skills/`, such as `dataset-intake` or `scientist-review`.
- Workflow Routing Limitation: the current OpenCode surface has bounded commands and procedures but no general runner that automatically executes every `_workflows/` manifest and step or maps every workflow name to a command.
