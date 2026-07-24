# LASI

## Learning as a Service

### Purpose

LASI is a machine learning research operating system.

Its purpose is not to maximize model performance.

Its purpose is to identify:

- What is limiting performance
- What evidence supports that conclusion
- What action should be taken next
- Whether further work is justified

LASI treats machine learning development as a scientific process.

Every experiment should generate evidence.

Every recommendation should be justified.

Every decision should be traceable.

Every outcome should be remembered.

---

## Mission

LASI exists to reduce wasted machine learning effort.

Many ML projects fail because teams optimize the wrong thing.

Examples include:

- Training larger models when labels are ambiguous
- Collecting more data when coverage is already sufficient
- Building new architectures when preprocessing is the bottleneck
- Deploying models without understanding failure modes

LASI attempts to identify these limitations before significant resources are spent.

---

## Mental Model

LASI behaves like a research organization.

Each subsystem plays a role.

| Component | Role |
|------------|--------|
| Scientist Provider | Senior Scientist |
| Agent | Research Assistant |
| Tool Registry | Laboratory Equipment |
| Database | Operational Memory |
| Knowledge Layer | Institutional Memory |
| MLflow | Experiment Record |
| Decision System | Research Review Board |
| Outcome Ledger | Production History |
| Sabbatical System | Annual Research Review |

OpenCode is the operating surface for this organization: commands initiate bounded requests, agents coordinate specialist work, and canonical hyphenated skills under `.opencode/skills/` provide step-level procedures. Reusable Python services in `src/lasi/` perform implementation work beneath that surface where integration exists. The current commands do not constitute a workflow engine: they do not automatically interpret and execute every `_workflows/**` step or route arbitrary workflow names without coordinator or agent guidance.

---

## Core Principles

### Evidence Before Opinion

Recommendations should be supported by evidence.

### Memory Matters

The system should remember both successes and failures.

### Human Authority

Humans approve high-consequence actions.

### Explainability

Every recommendation should be traceable.

### Reproducibility

Experiments should be repeatable.

### Knowledge Preservation

Lessons should survive individual projects.

---

## Documentation Structure

The LASI documentation is organized into independent modules.

### 01_ARCHITECTURE.md

System structure and component relationships.

### 02_PROJECT_LIFECYCLE.md

How projects move through LASI.

### 03_DATASET_SYSTEM.md

Dataset management and characterization.

### 04_EXPERIMENT_SYSTEM.md

Experiment planning and execution.

### 05_MEMORY_SYSTEM.md

Operational memory and retrieval.

### 06_KNOWLEDGE_SYSTEM.md

Facts, policies, hypotheses, lessons, and literature.

### 07_SCIENTIST_PROVIDER.md

Scientific reasoning interface.

### 08_DECISION_SYSTEM.md

Decision gates and approval logic.

### 09_REMOTE_EXECUTION.md

SSH workers and compute infrastructure.

### 10_REPORTING_SYSTEM.md

Static report generation.

### 11_OUTCOME_SYSTEM.md

Deployment outcomes and retrospectives.

### 12_SABBATICAL_SYSTEM.md

Continuous improvement and literature review.

### 13_FOUNDATION_RECOMMENDER.md

Foundation-model opportunity discovery.

### 14_GOVERNANCE.md

Authority boundaries and approval rules.

---

## Reading Order

New agents should read:

1. LASI_OVERVIEW
2. ARCHITECTURE
3. PROJECT_LIFECYCLE
4. MEMORY_SYSTEM
5. KNOWLEDGE_SYSTEM
6. SCIENTIST_PROVIDER
7. DECISION_SYSTEM

All remaining documents are supporting references.

---

## Definition of Success

LASI is successful when it can answer:

"What is limiting this system?"

with evidence rather than opinion.
