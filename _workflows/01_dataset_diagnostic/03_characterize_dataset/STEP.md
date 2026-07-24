Step: 03 Characterize Dataset
=============================

Purpose
-------

Produce a dataset characterization that identifies likely failure modes.

Inputs
------

- `dataset_manifest.md`

Actions
-------

1. Run `dataset_characterization` skill checklist.
2. Produce `dataset_characterization.md` with identified issues and recommended experiments.

Skill
-----

dataset_characterization

Expected output
---------------

- `dataset_characterization.md`

Stop / Escalation
-----------------

- If representative sample cannot be obtained, document the limitation and propose a sampling plan.

Handoff
-------

Pass characterization to `04_plan_experiments`.
