Projects Folder
===============

Each substantial project has an isolated workspace at `projects/<project_id>/`, generated
from the governed `project` scaffold template. The layout is fixed by
`_architecture/15_CONTEXT_SYSTEM.md`:

```text
00_task/       objective, success criteria, constraints
10_context/    current state, dataset profile, domain context, prior findings
20_work/       exploration, research, features, experiments, interpretation
30_evidence/   claims, metrics, plots, comparisons, failures, promotions
40_output/     recommendation, limitations, handoff
artifacts/     produced binaries and their provenance records
```

The layout is fixed rather than per-project because evidence is compared across projects.
Retrieval reads the same paths in every workspace, so a project shaped differently is not
comparable to the others.

Create a workspace through `services.scaffolds.ScaffoldService`, never by hand and never
with `copier copy`: the service records the template revision that produced the tree, and
a tree with no recorded revision cannot be shown to be comparable to any other.

Every generated workspace carries a `.scaffold.yml` naming its template and revision.
`wave5b-point-cloud-fixture` has none: it is a test fixture rather than a research
project, and is deliberately not migrated to the project layout.
