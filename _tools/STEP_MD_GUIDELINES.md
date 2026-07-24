STEP.md Headings Guideline
=========================

Purpose: Every STEP.md should include these canonical headings in this order (case-sensitive):

- Purpose
- Inputs
- Actions
- Skill
- Expected output
- Stop / Escalation
- Handoff

Notes:
- Use short, declarative lines under each heading.
- For automated parsing, avoid colon-only headings in lowercase; use the exact capitalization above.
- Keep `Skill` as a single skill name that maps to `_skills/<skill>/SKILL.md`.
- `Expected output` should reference template paths or artifact filenames.
- `Stop / Escalation` must list blocking conditions that prevent the next step.

Suggested next step: add a linter that checks each `STEP.md` contains these headings.
