"""Append-only SQLite authority ledger."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .contracts import ApprovalRecord, LedgerEvent, OperatorResult, Plan, VerificationResult


class SqliteLedger:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                plan_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                plan_id TEXT PRIMARY KEY,
                digest TEXT NOT NULL,
                decision_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operator_runs (
                idempotency_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                plan_digest TEXT NOT NULL,
                step_id TEXT NOT NULL,
                approver_id TEXT NOT NULL,
                approval_json TEXT NOT NULL
            );
            """
        )

    def append(self, event: LedgerEvent) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO events(event_id, project_id, kind, payload_json, occurred_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.project_id,
                    event.kind,
                    json.dumps(event.payload, sort_keys=True),
                    event.occurred_at.isoformat(),
                ),
            )

    def record_plan(self, plan: Plan) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO plans(plan_id, project_id, digest, plan_json) VALUES (?, ?, ?, ?)",
                (plan.plan_id, plan.goal.project_id, plan.digest(), plan.model_dump_json()),
            )

    def record_decision(self, result: VerificationResult) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO decisions(plan_id, digest, decision_json) VALUES (?, ?, ?)",
                (result.plan_id, result.plan_digest, result.model_dump_json()),
            )

    def covers_plan(self, plan: Plan, decision: VerificationResult) -> bool:
        plan_row = self._connection.execute(
            "SELECT digest FROM plans WHERE plan_id = ?",
            (plan.plan_id,),
        ).fetchone()
        decision_row = self._connection.execute(
            "SELECT decision_json FROM decisions WHERE plan_id = ?",
            (plan.plan_id,),
        ).fetchone()
        if plan_row is None or decision_row is None:
            return False
        recorded = VerificationResult.model_validate_json(decision_row["decision_json"])
        return (
            plan_row["digest"] == plan.digest()
            and recorded == decision
            and recorded.allowed
            and recorded.plan_digest == plan.digest()
        )

    def record_operator_result(
        self,
        *,
        idempotency_key: str,
        run_id: str,
        step_id: str,
        result: OperatorResult,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO operator_runs(idempotency_key, run_id, step_id, status, result_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, run_id, step_id, result.status, result.model_dump_json()),
            )

    def successful_result(self, idempotency_key: str) -> OperatorResult | None:
        row = self._connection.execute(
            "SELECT result_json FROM operator_runs "
            "WHERE idempotency_key = ? AND status = 'succeeded'",
            (idempotency_key,),
        ).fetchone()
        return OperatorResult.model_validate_json(row["result_json"]) if row else None

    def record_approval(self, approval: ApprovalRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO approvals("
                "approval_id, plan_digest, step_id, approver_id, approval_json"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    approval.approval_id,
                    approval.plan_digest,
                    approval.step_id,
                    approval.approver_id,
                    approval.model_dump_json(),
                ),
            )

    def has_approval(self, approval_id: str, plan_digest: str, step_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM approvals "
            "WHERE approval_id = ? AND plan_digest = ? AND step_id = ?",
            (approval_id, plan_digest, step_id),
        ).fetchone()
        return row is not None

    def recent_events(self, project_id: str, *, limit: int = 100) -> tuple[LedgerEvent, ...]:
        rows = self._connection.execute(
            "SELECT event_id, project_id, kind, payload_json, occurred_at FROM events "
            "WHERE project_id = ? ORDER BY sequence DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return tuple(
            LedgerEvent(
                event_id=row["event_id"],
                project_id=row["project_id"],
                kind=row["kind"],
                payload=json.loads(row["payload_json"]),
                occurred_at=row["occurred_at"],
            )
            for row in reversed(rows)
        )

    def emit(self, project_id: str, kind: str, payload: dict[str, Any]) -> LedgerEvent:
        event = LedgerEvent(
            event_id=str(uuid4()), project_id=project_id, kind=kind, payload=payload
        )
        self.append(event)
        return event

    def close(self) -> None:
        self._connection.close()
