# Step 03 — Compare Characterizations

Purpose
: Compare statistical and qualitative characterizations of parent and child datasets.

Inputs
- Characterization summaries for parent and child

Expected output
- `characterization_comparison.md` with per-field differences and flagged concerns

Actions
- Compare feature distributions, label balances, metadata fields, and known failure modes.
- Annotate non-comparable axes.

Stop / Escalation
- Major non-comparabilities that require redesign.

Skill
- `dataset-characterization`
