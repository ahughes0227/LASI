# 01_ARCHITECTURE.md

## Purpose

This document describes the major runtime components of LASI and how they interact.

It does not define schemas, prompts, database tables, or implementation details. Those belong in separate documents.

---

## Architectural Principle

LASI separates execution, reasoning, memory, knowledge, reporting, and governance.

No single subsystem is authoritative over everything.

The database records what happened.
MLflow stores experimental artifacts.
The knowledge layer stores what was learned.
The scientist provider gives recommendations.
The decision system authorizes actions.
OpenCode commands, agents, and skills are the operating surface. Reusable Python services are the implementation layer behind that surface.

The current implementation is partial. `src/lasi/` provides typed contracts, configuration, dataset, experiment, tool, decision, provider, report, remote, knowledge, memory, and outcome components, with unit and fixture integration tests. These are reusable service building blocks, not proof that every OpenCode command and workflow step is wired end to end.

OpenCode skill identifiers are canonical only in their hyphenated form, for example `dataset-intake`, `dataset-characterization`, and `decision-review`. All skill procedures, contracts, checklists, and examples are discovered from and maintained under `.opencode/skills/`; no secondary skill tree is supported.

---

## High-Level System Diagram

```text
OpenCode command / agent / skill
│
Reusable Python Services
│
├── Tool Registry
├── Experiment Planner
├── SSH Remote Runner
├── Scientist Provider
├── Decision System
├── Report Generator
├── Knowledge Curator
│
├── Database
│   └── Operational Memory
│
├── MLflow
│   └── Experiment Artifacts
│
└── Knowledge Layer
    └── Semantic Memory

OpenCode routing limitation: the repository currently has nine commands and coordinator/specialist procedures, not a command for each workflow or a general workflow runner. A command may select a specialist and skill, but workflow sequencing, handoff interpretation, and service invocation remain bounded by the procedure and available integration code. This limitation does not change ownership, approval, provenance, or other authority boundaries.
