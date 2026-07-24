Step: 08 Generate Report
========================

Purpose
-------

Produce a fixed static report summarizing findings, recommendations, and decisions.

Inputs
------

- `scientist_review.md`, `decision_record.md`, and key artifacts

Actions
-------

1. Run `report-generation` checklist and fill the static report template.
2. Save immutable `static_report.html` (or markdown) in artifacts.

Skill
-----

report-generation

Expected output
---------------

- `static_report` artifact with links to evidence.

Stop / Escalation
-----------------

- If key sections are blocked, include placeholders and mark the report partial.

Handoff
-------

Pass report to `09_record_outcome`.
