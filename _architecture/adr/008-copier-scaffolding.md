# ADR-008: Copier as the single scaffolding mechanism

**Status:** accepted

## Context

LASI scaffolds structure in at least four places, none of which share code:

- `CapabilityBuilder.scaffold` — `services/capabilities/development.py`
- `ComponentBuilder.scaffold` — `services/components/development.py`
- `WorkflowBuilder.scaffold` — `services/workflows/development.py`
- Project creation, which has no implementation at all

Each is `mkdir` plus `write_text` boilerplate, drifting independently. Project
layout has drifted furthest: `_architecture/15_CONTEXT_SYSTEM.md` documents the
ICM structure `00_task/ 10_context/ 20_work/ 30_evidence/ 40_output/`,
`projects/README.md` documents a different convention of `artifacts/` plus
`context.md`, and of three existing projects two follow the first and one follows
neither.

The governing intent is a research lab: structure is standard so effort goes to
the science rather than to reinventing process. That intent fails if every
project is shaped differently — and it fails in a way that matters technically,
because episode retrieval compares evidence across projects. Three layouts means
cross-project comparison is confounded before any learning begins.

## Decision

Adopt **Copier** as the single scaffolding mechanism, with templates under a new
`_scaffolds/<name>/` root. Deliberately not `_templates/`, which already holds
markdown artifact templates.

Copier is chosen over cookiecutter for `copier update`: the `.copier-answers.yml`
recorded in each generated tree lets a template revision propagate into trees
that already exist. That is the mechanism by which the lab bench improves as the
system learns, rather than improving only for projects created afterward.

### What `copier update` actually requires, and what is implemented

Probing established three constraints that shape the design:

1. `copier update` performs its three-way merge using **git**, and needs the template to
   be a tagged git repository. This repository has no tags, so `_commit` is absent from
   the answers file and `copier update` cannot run today.
2. Copier records neither `_`-prefixed settings nor skipped (`when: false`) questions in
   the answers file, so a template revision declared that way does not reach the
   generated tree.
3. Only files suffixed `.jinja` are rendered; everything else is copied verbatim.

The revision mechanism therefore does not depend on Copier internals. Each template
declares its identity in `_scaffolds/<name>/scaffold.yml`, `services.scaffolds` supplies
it at render time, and every generated tree carries a `.scaffold.yml` naming the template
and revision it came from. `ScaffoldRegistry` records the same pair in operational
memory, so the trees still on an older revision can be listed — which is the set a
governed update has to act on.

**Prerequisite for automatic propagation:** enabling `copier update` requires adopting a
tag namespace on this repository, `scaffolds/vN`, so Copier can resolve a template
version. That is a repository-workflow decision and is deliberately not taken here. Until
it is, propagation is a governed re-render rather than a merge, and `ScaffoldRegistry`
identifies what needs re-rendering. The recorded revision is useful either way; the tags
only add the automatic merge.

### Scaffolding stays governed

A fixed shell today is derived from a **frozen build plan** that is the authority
for what may be created, and `scaffold()` enforces real guards: `reuse` and
`extend` resolutions cannot create a package, the target must stay under the
requested root, and an existing package is a hard error.

> `scaffold()` remains the only entry point, with its guards intact. It calls
> Copier internally with answers derived from the frozen build plan. Copier
> renders the shell; the build plan remains the authority. `copier copy` against
> these templates is never a supported operation.

### Template revisions are governed changes

A template update can alter many projects at once, which is high-consequence by
LASI's own standard.

- Templates are versioned, and the template name and revision are recorded in
  operational memory for every generated project and package.
- `copier update` across existing projects requires an approval record, following
  the existing `update_toolbox` pattern rather than a new mechanism.

## Consequences

- Episodes become attributable to the bench they ran on. Without the recorded
  revision, cross-project comparison silently degrades every time a template
  changes — the confound simply moves rather than disappearing.
- `system/learned_principles/`, today an empty README, gains its first concrete
  channel: a validated lesson becomes a versioned, reviewable, propagable
  template revision instead of prose in a knowledge document.
- The three conflicting project layouts must be reconciled to one. The
  `_architecture` ICM structure wins; `projects/README.md` is corrected.
- Existing projects need answers files generated retroactively to become
  updatable. Whether the point-cloud fixture is migrated or grandfathered is an
  explicit choice, not an oversight.
- Copier becomes a runtime dependency, not a dev dependency, because the governed
  development pipelines import it during normal operation.
