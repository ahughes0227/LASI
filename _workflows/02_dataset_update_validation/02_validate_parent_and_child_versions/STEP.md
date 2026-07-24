# Step 02 — Validate Parent and Child Versions

Purpose
: Verify manifests, sample counts, schema, and access for both parent and child.

Inputs
- Parent and child manifests, sample snapshots

Expected output
- Validation notes and a `comparability_precheck.md` indicating mismatches.

Actions
- Check record counts, label distribution, schema drift, and metadata completeness.
- Run privacy and policy checks.

Stop / Escalation
- Ancillary data missing, or policy/privacy block.

Skill
- `dataset-characterization`
