---
# Project Initiation Ticket Template

Example only. Fill with structured fields.

ticket_id: TICKET-XXXX
ticket_type: project_initiation
project_id: optional-project-id
project_name: Descriptive project name
created_by: name <email>
created_at: 2026-05-30T00:00:00Z
priority: low|medium|high|urgent
requested_due_date: YYYY-MM-DD
requested_workflow: e.g. dataset_update_validation
status: inbox|accepted|blocked|running|closed

problem_statement: |
  One-paragraph description of problem and context.

why_this_matters: |
  Short justification for business or research value.

current_pain: |
  What currently fails or limits progress.

primary_goal: |
  Concrete goal for this ticket.

desired_output: |
  What deliverable is expected (report, dataset, validation results).

minimum_useful_finding: |
  The minimally useful outcome to stop work.

dataset_name: |
dataset_location: |
data_format: |
label_location: |
metadata_location: |
access_notes: |
assumptions: |
privacy_mode: local_only|summary_only_to_scientist|plots_allowed|thumbnails_allowed|raw_samples_allowed|knowledge_allowed
compute_constraints: |
tooling_constraints: |
human_review_contact: name <email>
known_background: |
evaluation_preference: qualitative|quantitative

in_scope: |
out_of_scope: |
stop_conditions: |
notification_requested: yes|no
notification_channel: email|slack|none

acceptance_criteria: |
  Clear, testable acceptance criteria.
---
