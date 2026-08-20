# ADR-001: Capability, component, and belief terminology

**Status:** accepted

## Context

An external architecture plan ("Lassie") proposed a three-level model of
Workflow → Capability → Component. Two of those words already mean something
specific in LASI, and one concept it introduces already exists here under two
different names. Adopting the plan's vocabulary as written would silently
redefine terms used across `_architecture/`, `_core/`, `_schemas/`,
`_workflows/`, and `services/contracts/models.py`.

## Decision

**Capability keeps its LASI meaning.** A capability is a semantic registry entry
describing *what LASI can do*, produced by the governed development pipeline in
`16_CAPABILITY_DEVELOPMENT_SYSTEM.md` and carrying a `CapabilityDomainContract`
sidecar of preconditions and effects. The plan's narrower notion — an LM-backed
reasoning operation with an optimizable program — is a new and distinct thing.
It is named **`ReasoningCapability`**: an implementation kind that a LASI
capability may declare, never a redefinition of the parent term.

**Component keeps its meaning in both.** A component is a deterministic,
registered, schema-backed executable. The two vocabularies already agree; no
action.

**Belief is not introduced.** LASI deliberately splits the concept in two, and
the split is load-bearing:

- `DomainFact` — machine state, aggregated from evidence by
  `ConfidenceAggregator`, carrying confidence, authority, and evidence refs.
- `ScientificClaim` — epistemic, with a governed status ladder
  (`proposed` → `experimentally_supported` → `challenged` → `refuted` →
  `survived_challenge` → `replicated`) whose validator explicitly refuses to let
  an agent claim become an accepted fact.

Collapsing these into one "belief" record would erase the boundary between what
the machine observed and what the institution accepts. Where external material
says "belief", map it to whichever of the two is meant, per site.

**The tool registry has no counterpart in the plan and is retained.** It is the
execution allowlist consulted by the decision system. It is not redundant with
the component registry — the component registry catalogs implementation
machinery, the tool registry constrains what may execute — and the two must not
be merged.

## Consequences

- `ReasoningCapability` needs a contract and a registry relationship to
  `CapabilitySpec` before the DSPy work in ADR-005 begins.
- External documents adopting plan vocabulary must be translated at the boundary
  rather than merged verbatim.
- Three registries persist (capability, component, tool). This is deliberate and
  should not be "simplified" without revisiting the governance argument in
  `01_ARCHITECTURE.md`.
