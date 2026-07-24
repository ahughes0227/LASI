Dataset Intake Output Contract
==============================

Produces a markdown `dataset_manifest.md` with fields:

- project_id
- dataset_version_id
- source_description
- file_list (filenames + checksums)
- privacy_tags
- owner_contact
- provenance (agent_id, timestamp, source_path)

The file must be human-readable and reference the `_templates/dataset_manifest/dataset_manifest_template.md`.
