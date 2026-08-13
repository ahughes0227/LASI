# 02_PROJECT_LIFECYCLE.md

## Purpose

This document defines how a LASI project moves from creation to closure.

It defines project states, allowed transitions, lifecycle responsibilities, stopping conditions, and outcome recording.

It does not define database schemas, report templates, model metrics, or tool implementation details.

## Core Idea

A LASI project is not complete when experiments finish.

A project is complete when the outcome is recorded.

The outcome may be deployment, cancellation, failed validation, production failure, successful production use, research-only closure, or blocked status.

## Assignment Runtime Lifecycle

Project outcome and autonomous-assignment runtime state are separate. Runtime assignments use explicit `active`, `waiting`, `pausing`, `paused`, `escalated`, `runtime_blocked`, `cancelling`, `cancelled`, `completed`, and `failed` states. `runtime_blocked` is a deterministic local-infrastructure condition, such as a missing or unusable OpenCode CLI. It does not consume coordinator turns or retry patience and may be resumed after preflight succeeds. `pausing` and `cancelling` mean the current atomic coordinator turn must checkpoint before the requested state is final. A computer should be shut down only after `paused` or a terminal state is persisted. Resume launches a new worker from SQLite state and append-only assignment events; it never depends on conversation history.

Entering `escalated` also publishes a durable OpenCode UI notification. The UI shows a warning and pre-fills the pending question plus matching `/lasi-feedback` syntax. Restarting OpenCode replays unanswered notifications. Recording matching feedback clears the notification and resumes the assignment.

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
