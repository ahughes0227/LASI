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
The CLI is the operating surface.

---

## High-Level System Diagram

```text
CLI
│
Harness Core
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
