Step: 01 Intake
===============

Purpose
-------

Create a canonical dataset manifest and record provenance.

Inputs
------

- Raw dataset export or access instructions

Actions
-------

1. Run `dataset-intake` skill checklist.
2. Produce `dataset_manifest.md` using `_templates/dataset_manifest/dataset_manifest_template.md`.

Skill
-----

dataset-intake

Expected output
---------------

- `dataset_manifest.md` in project artifacts.

Stop / Escalation
-----------------

- If owner or privacy constraints are unclear, stop and create a blocking note for humans.

Handoff
-------

Pass `dataset_manifest.md` to `02_validate_dataset`.
