---
name: experiment-planning
description: Use after dataset characterization and before execution to translate evidence into an ordered LASI ExperimentPlan.
---

# Experiment Planning

Translate dataset issues into `experiment_plan.md` with project and dataset version links, ordered experiments, inputs, metrics, model specifications, expected outcomes, estimated cost, dependencies, success criteria, stop conditions, and provenance.

Read `AGENTS.md`, `_architecture/01_ARCHITECTURE.md`, `_architecture/04_EXPERIMENT_SYSTEM.md`, and `_templates/experiment_plan/experiment_plan_template.md`. Planning does not execute tools, remote runs, or high-consequence actions.

Prioritize experiments by expected information gain and cost. Follow `checklist.md`, validate the result against `output_contract.md`, and use only synthetic examples from `examples/` as guidance.

In an iterative assignment, record an approach signature, novelty score, novel dimensions, and differences from prior attempts. Increase the novelty floor after each completed novel attempt that does not meaningfully improve the objective. Parameter-only variants of an exhausted path are not divergent and do not count toward plateau patience.
