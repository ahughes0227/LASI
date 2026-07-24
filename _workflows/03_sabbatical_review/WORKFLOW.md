# Sabbatical Review Workflow

goal
: Given recent LASI evidence, recommend what the organization should believe differently, test next, update, or retire. Produce proposals but do not apply changes.

when to use it
: Periodic reviews or triggered reviews after a set of project outcomes or pattern detection.

required inputs
- Project outcomes, scientist reviews, knowledge records, external literature

operating surface
- Start and resume this workflow through OpenCode commands or the LASI coordinator.
- OpenCode agents coordinate the review and invoke bounded skills; reusable Python services may implement individual operations.
- The operating surface does not grant the agent authority to approve proposals or apply knowledge changes.
- Skill procedures are available under `.opencode/skills/`.

ordered steps
- 01_define_review_scope
- 02_collect_internal_evidence
- 03_review_project_outcomes
- 04_review_tool_usefulness
- 05_review_knowledge_layer
- 06_review_external_literature
- 07_identify_patterns_and_contradictions
- 08_generate_sabbatical_report
- 09_create_proposals
- 10_decision_review

skills used
- `knowledge-curation`, `scientist-review`, `report-generation`, `decision-review`

expected outputs
- Sabbatical report with structured section statuses
- Knowledge proposals for changes to facts, policies, or tools (never auto-approved)
- Decision records for any high-consequence follow-ups

stop conditions
- Any proposal that changes policies, datasets, or approves production deployments must be escalated to decision review and human approval.

handoff rules
- Proposals are created and stored under `projects/<id>/artifacts/knowledge_proposals/` and do not modify the knowledge layer until approved.
