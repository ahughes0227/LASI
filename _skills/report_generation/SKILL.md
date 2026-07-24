Skill: Report Generation
========================

Purpose
-------

Generate a fixed static report (HTML or markdown) from `StaticReportData` using the template.

When to use
-----------

At the end of a workflow when a human-readable deliverable is required.

Required inputs
---------------

- Structured `StaticReportData` or the constituent artifacts (experiment_plan, scientist_review, decision_record).

Required outputs
----------------

- `static_report.html` (or markdown) saved under project artifacts.

Files to read first
-------------------

- _templates/static_report/static_report_outline.md

Forbidden actions
-----------------

- Do not write freeform essays—reports must be derived from structured data and include provenance.

Completion criteria
-------------------

- Static report is generated, contains all required sections, and is stored as an immutable artifact.
