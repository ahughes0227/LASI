Skill: Dataset Intake
======================

Purpose
-------

Bring a new dataset into LASI as a canonical versioned asset and produce a dataset manifest.

When to use
-----------

Use at project start when a dataset is newly provided or when ingesting a new dataset version.

Required inputs
---------------

- Raw dataset export or access instructions
- Ownership and privacy constraints

Required outputs
----------------

- `dataset_manifest.md` saved under project artifacts.

Files to read first
-------------------

- _core/glossary.md
- _core/authority_boundaries.md
- _templates/dataset_manifest/dataset_manifest_template.md

Forbidden actions
-----------------

- Do not modify labels or authoritative storage directly.

Completion criteria
-------------------

- A valid `dataset_manifest.md` exists and provenance is recorded.
