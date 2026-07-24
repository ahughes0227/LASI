---
description: Compile a dataset diagnosis into an ordered experiment plan.
agent: experiment-engineer
---

Use the experiment-planning skill for `$ARGUMENTS`. Use `lasi.experiments.compile_plan` to produce an ExperimentPlan with linked dataset version, dependencies, metrics, estimated cost, expected outcomes, success criteria, stop conditions, and provenance. Planning does not authorize or execute work; a later `lasi.decisions.gate.DecisionGate` evaluation is required.
