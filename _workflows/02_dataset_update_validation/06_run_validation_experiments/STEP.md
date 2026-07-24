# Step 06 — Run Validation Experiments

Purpose
: Execute the approved validation experiments under the specified execution backend.

Inputs
- Approved experiment plan and decision record

Expected output
- Raw results saved to `projects/<id>/working/` and artifacts to `projects/<id>/artifacts/`

requirements
- Execution only allowed when decision record permits; remote runs require remote host profile in decision.

Skill
- `remote_execution` (if remote) or local run procedures
