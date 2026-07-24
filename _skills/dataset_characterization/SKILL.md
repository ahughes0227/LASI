Skill: Dataset Characterization
================================

Purpose
-------

Produce a structured dataset characterization describing class balance, missingness, label issues, and common failure modes.

When to use
-----------

After dataset intake and before experiment planning.

Required inputs
---------------

- `dataset_manifest.md`
- Access to a small representative sample (or summary statistics)

Required outputs
----------------

- `dataset_characterization.md` under project artifacts.

Files to read first
-------------------

- _core/glossary.md
- _templates/experiment_plan/experiment_plan_template.md

Forbidden actions
-----------------

- Do not change labels or the canonical dataset; propose label fixes in a knowledge proposal.

Completion criteria
-------------------

- Characterization includes a summary table, identified issues, and recommended diagnostic experiments.
