Step: 02 Validate Dataset
==========================

Purpose
-------

Verify manifest completeness and basic dataset sanity checks.

Inputs
------

- `dataset_manifest.md`

Actions
-------

1. Confirm file checksums and schema presence.
2. Flag missing or inconsistent fields in manifest.

Skill
-----

dataset_characterization (validation subset)

Expected output
---------------

- Validation note and a short `validation_report.md` or blocking note.

Stop / Escalation
-----------------

- If files are missing or privacy policy blocks inspection, escalate to dataset owner.

Handoff
-------

Pass validated manifest to `03_characterize_dataset`.
