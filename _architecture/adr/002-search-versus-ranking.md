# ADR-002: The symbolic layer owns legality; the learned layer owns ranking

**Status:** accepted

## Context

LASI plans deterministically. `DomainStatePlanner` performs backward search over
`CapabilityDomainContract` preconditions and effects, filters candidates through
`DomainPolicyEvaluator`, and returns a `DomainPlan`. Among the admissible plans
it finds, it chooses one using a hand-authored objective:

```python
(len(steps), sum(side_effect_rank), count(require_approval), tuple(capability_ids))
```

Fewest steps, least side-effect risk, fewest approvals — then **alphabetical
order by capability id**. That final term is a coin flip standing in for
judgment.

Separately, an external plan argued for learned action selection over
hand-authored routing, and for learning from execution outcomes. Read naively,
that argument deletes the symbolic planner as "manually encoded cognitive
structure". Read carefully, the two are complementary, because they operate on
different questions.

## Decision

Split the planner's two responsibilities and assign them to different layers:

- **Admissibility is symbolic and deterministic.** Which plans exist, which
  satisfy preconditions, which reach the goal, and which survive policy — all
  decided by `DomainStatePlanner` and `DomainPolicyEvaluator`.
- **Selection among admissible plans is learned.** The objective tuple is
  extracted behind a `PlanRanker` protocol. The current behavior becomes
  `LexicographicPlanRanker`, the default. Later rankers may use episode history,
  cost, and outcome feedback.

### The invariant

> **No learned component may widen the admissible set.**

A ranker chooses among candidates the symbolic layer already approved. It cannot
introduce a plan, relax a precondition, or overturn a policy decision. This is
enforced in code by a test asserting that any ranker's chosen plan is a member of
the candidate set, and structurally by the fact that rankers receive only
already-filtered candidates.

## Consequences

- Learning is bounded by construction. A badly trained ranker produces a
  suboptimal legal plan, never an illegal one. Governance does not depend on
  model quality.
- `DomainStatePlanner._search` must retain non-winning admissible plans rather
  than discarding them. These are the counterfactuals; without them, every
  future training set is confounded by the policy that generated it.
- The thesis "prior experience improves later decisions" becomes measurable as a
  single quantity: does a ranker beat `LexicographicPlanRanker` on held-out
  episodes?
- The alphabetical tie-break disappears as soon as any ranker with real signal
  replaces it, which is a small correctness improvement independent of learning.
