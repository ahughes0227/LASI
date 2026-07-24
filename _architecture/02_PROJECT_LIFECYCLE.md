# 02_PROJECT_LIFECYCLE.md

## Purpose

This document defines how a LASI project moves from creation to closure.

It defines project states, allowed transitions, lifecycle responsibilities, stopping conditions, and outcome recording.

It does not define database schemas, report templates, model metrics, or tool implementation details.

## Core Idea

A LASI project is not complete when experiments finish.

A project is complete when the outcome is recorded.

The outcome may be deployment, cancellation, failed validation, production failure, successful production use, research-only closure, or blocked status.

## Project Lifecycle

created
→ dataset_validated
→ characterized
→ baseline_complete
→ scientist_reviewed
→ decision_made
→ report_generated
→ outcome_recorded
→ knowledge_curated
→ closed
