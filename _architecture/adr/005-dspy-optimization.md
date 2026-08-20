# ADR-005: DSPy for reasoning-capability optimization, challenger-only

**Status:** accepted

## Context

LASI has a provider abstraction (`services/providers/`) that normalizes scientist
reviews and critic assessments across model vendors, but it has no layer that
treats LM behavior as something to be *optimized* against recorded outcomes.
Prompts live as versioned files under `system/workflow_prompts/`; improving them
is a manual edit.

DSPy offers programmatic optimization of LM programs against a metric and a
dataset. LASI already has the two inputs that need: rubric criteria
(`ReasoningRubric`) supply the metric, and accumulated episodes supply the
examples.

## Decision

Introduce a `ReasoningCapability` layer (ADR-001) implemented with DSPy, behind
the existing `ScientistReview` and `CriticAssessment` contracts. Optimization is
**offline and explicit** — a command, not a background process.

**Optimized programs are challengers, never champions.** A newly optimized
program registers through the existing governed path
(`CapabilityRegistrationProposal` plus an `update_toolbox` approval bound to the
package hash). There is no code path that promotes an optimized program on the
strength of its own evaluation score.

### What implementation established

**The recommendation vocabulary is closed.** `normalize_review` rejects any
`recommended_next_action` outside an eleven-item allowlist, so an LM cannot widen its own
action space however it is prompted or optimised. The DSPy signature names that list
explicitly: optimising toward fluent recommendations the provider layer then discards
would train a program to fail validation more persuasively.

**DSPy is an optional extra.** It pulls a large dependency tree, and the core system must
import and run without it. `services.reasoning` speaks only in terms of
`ReasoningProgram`; DSPy appears in one module, so removing or replacing it is a
single-file change rather than a change to the system's vocabulary.

**The path is testable without a live model.** DSPy's `DummyLM` exercises the real
signature, adapter, and module, so the end-to-end test proves the integration rather than
proving a stub works.

**A program runs through the ordinary provider path.** `ReasoningScientistProvider`
implements the existing `ScientistProvider` protocol, so privacy filtering, normalisation,
and artifact capture apply unchanged. An LM-backed reviewer that needed its own path would
require every guarantee of the provider layer to be re-established for it.

## Consequences

- The "never silently deploy" discipline costs nothing new to build; it is
  already LASI policy with an implementation. Reusing it avoids a second,
  weaker promotion mechanism.
- With tens of episodes, optimization is prompt-tuning on noise. This is
  understood and accepted: the first deliverable is the evaluation and
  challenger machinery, not measured gains. Early improvements are treated as
  provisional and must survive replication before they mean anything.
- Provider agnosticism must survive. DSPy sits behind the provider interface; no
  DSPy type appears in a LASI contract.
- Evaluation datasets derived from episodes inherit whatever bias the ranker had
  when it generated them. ADR-002's retained counterfactuals partly mitigate
  this; occasional deliberate exploration would mitigate it further and is worth
  considering once volume justifies it.
