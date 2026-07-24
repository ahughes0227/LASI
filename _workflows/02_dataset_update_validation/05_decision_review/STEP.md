# Step 05 — Decision Review

Purpose
: Present planned experiments and risks to the decision authority and obtain an explicit decision record.

Inputs
- Validation experiment plan, risk assessment, budget estimate

Actions
- Create a `decision_record.md` following `_templates/decision_record/decision_record_template.md` and the canonical schema.
- If decision is `allow` or `allow_with_warning`, include `execution_backend` and `remote_host_profile` if needed.
- If decision is `block`/`defer`/`escalate_for_approval`, record reasons and next steps.

Skill
- decision_review

Expected output
- `decision_record.md` saved to `projects/<id>/decisions.md` and linked to ticket

Stop / Escalation
- No execution may happen without `decision_record.decision` in [allow, allow_with_warning].

Handoff
- Attach decision to experiment plan and hand off to execution only when allowed.
