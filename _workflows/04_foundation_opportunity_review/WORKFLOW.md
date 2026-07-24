# Foundation Opportunity Review Workflow

goal
: Assess whether LASI has enough related data, repeated structure, and task value to justify a foundation/self-supervised prototype.

when to use it
: When a candidate domain or set of datasets is proposed for a foundation effort.

required inputs
- Inventory of related datasets, downstream tasks, cost estimates, privacy constraints

ordered steps
- 01_define_candidate_domain
- 02_inventory_related_datasets
- 03_review_primitives_and_failures
- 04_review_downstream_tasks
- 05_check_privacy_and_pooling_constraints
- 06_score_opportunity
- 07_draft_prototype_plan
- 08_decision_review
- 09_generate_foundation_opportunity_report

skills used
- `dataset_characterization`, `knowledge_curation`, `experiment_planning`, `decision_review`

expected outputs
- Opportunity scorecard, prototype plan draft, decision record

stop conditions
- Insufficient data, unstable label policy, privacy constraints, weak benchmark, or prohibitive compute cost

approval points
- Any decision to proceed to prototype or training must be accompanied by explicit decision record and budget approval.

handoff rules
- Approved prototype plans are handed to an experiment team via a decision-record-linked handoff; no training runs occur without approved decision.
