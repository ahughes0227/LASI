"""SQLite authority store with append-only decisions and a transactional outbox."""

# ruff: noqa: E501

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .contracts import (
    ApprovalDecision,
    ApprovalGrant,
    ApprovalRequest,
    Evidence,
    ExecutionGrant,
    IdentityRecord,
    LedgerEvent,
    ModelInvocation,
    OperatorResult,
    Plan,
    PlannerProfile,
    ProjectionHealth,
    ProjectionStatus,
    RunSummary,
    SessionStatus,
    StepStatus,
    VerificationResult,
    canonical_json,
    utc_now,
)

SCHEMA_VERSION = 1


class AuthorityStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path != Path(":memory:"):
            parent_existed = self.path.parent.exists()
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not parent_existed:
                os.chmod(self.path.parent, 0o700)
            if self.path.exists():
                version = self._read_version()
                if version == 0 and self._user_tables():
                    backup = self._backup(version)
                    raise RuntimeError(
                        "refusing to initialize a non-empty unversioned database; "
                        f"evidence backup created at {backup}"
                    )
                if version not in {0, SCHEMA_VERSION}:
                    self._backup(version)
        self._connection = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._configure()
        self._migrate()
        if self.path != Path(":memory:"):
            os.chmod(self.path, 0o600)

    def _read_version(self) -> int:
        connection = sqlite3.connect(str(self.path))
        try:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()

    def _user_tables(self) -> tuple[str, ...]:
        connection = sqlite3.connect(str(self.path))
        try:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            return tuple(str(row[0]) for row in rows)
        finally:
            connection.close()

    def _backup(self, version: int) -> Path:
        backup = self.path.with_name(
            f"{self.path.stem}.v{version}.{uuid4().hex}.backup{self.path.suffix or '.sqlite3'}"
        )
        shutil.copy2(self.path, backup)
        os.chmod(backup, 0o600)
        return backup

    def _configure(self) -> None:
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute("PRAGMA busy_timeout = 5000")

    def _migrate(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"authority schema {version} is newer than supported")
        if version == 0:
            with self.transaction() as cursor:
                cursor.executescript(
                    """
                    CREATE TABLE identities (
                        subject_id TEXT PRIMARY KEY, credential_id TEXT NOT NULL UNIQUE,
                        record_json TEXT NOT NULL
                    );
                    CREATE TABLE execution_grants (
                        grant_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL,
                        grant_json TEXT NOT NULL,
                        FOREIGN KEY(subject_id) REFERENCES identities(subject_id)
                    );
                    CREATE TABLE approval_grants (
                        grant_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL,
                        grant_json TEXT NOT NULL,
                        FOREIGN KEY(subject_id) REFERENCES identities(subject_id)
                    );
                    CREATE TABLE used_nonces (
                        nonce TEXT PRIMARY KEY, action_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                        used_at TEXT NOT NULL
                    );
                    CREATE TABLE evidence (
                        evidence_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                        evidence_json TEXT NOT NULL
                    );
                    CREATE TABLE run_summaries (
                        run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                        summary_json TEXT NOT NULL
                    );
                    CREATE TABLE plans (
                        plan_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, digest TEXT NOT NULL,
                        plan_json TEXT NOT NULL
                    );
                    CREATE TABLE sessions (
                        session_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL UNIQUE,
                        goal_json TEXT NOT NULL, requester_id TEXT NOT NULL,
                        status TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE TABLE decisions (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT NOT NULL UNIQUE,
                        plan_id TEXT NOT NULL, digest TEXT NOT NULL, decision_json TEXT NOT NULL,
                        FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
                    );
                    CREATE TABLE approval_requests (
                        request_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, step_id TEXT NOT NULL,
                        request_json TEXT NOT NULL, UNIQUE(plan_id, step_id),
                        FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
                    );
                    CREATE TABLE approvals (
                        approval_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                        approver_id TEXT NOT NULL, decision_json TEXT NOT NULL,
                        UNIQUE(request_id, approver_id),
                        FOREIGN KEY(request_id) REFERENCES approval_requests(request_id)
                    );
                    CREATE TABLE runs (
                        run_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, status TEXT NOT NULL,
                        started_at TEXT NOT NULL, finished_at TEXT,
                        FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
                    );
                    CREATE TABLE step_runs (
                        run_id TEXT NOT NULL, step_id TEXT NOT NULL, operator TEXT NOT NULL,
                        status TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                        result_json TEXT, PRIMARY KEY(run_id, step_id)
                    );
                    CREATE TABLE operator_results (
                        idempotency_key TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL,
                        status TEXT NOT NULL, result_json TEXT NOT NULL
                    );
                    CREATE TABLE model_invocations (
                        invocation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                        invocation_json TEXT NOT NULL
                    );
                    CREATE TABLE planner_profiles (
                        profile_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL
                    );
                    CREATE TABLE events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
                        project_id TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                        occurred_at TEXT NOT NULL
                    );
                    CREATE TABLE projection_outbox (
                        sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                        project_id TEXT NOT NULL, envelope_json TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
                        projected_at TEXT, dead_lettered_at TEXT, last_error TEXT,
                        FOREIGN KEY(sequence) REFERENCES events(sequence)
                    );
                    CREATE TABLE coordinator_lease (
                        lease_name TEXT PRIMARY KEY, owner_id TEXT NOT NULL, expires_at TEXT NOT NULL
                    );
                    PRAGMA user_version = 1;
                    """
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                yield cursor
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
            finally:
                cursor.close()

    def _emit(
        self, cursor: sqlite3.Cursor, project_id: str, kind: str, payload: dict[str, Any]
    ) -> LedgerEvent:
        event = LedgerEvent(
            event_id=str(uuid4()), project_id=project_id, kind=kind, payload=payload
        )
        cursor.execute(
            "INSERT INTO events(event_id, project_id, kind, payload_json, occurred_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event.event_id,
                project_id,
                kind,
                canonical_json(payload),
                event.occurred_at.isoformat(),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("event insert did not produce a sequence")
        sequence = int(cursor.lastrowid)
        envelope = {
            "sequence": sequence,
            "event_id": event.event_id,
            "project_id": project_id,
            "kind": kind,
            "payload": payload,
            "occurred_at": event.occurred_at.isoformat(),
        }
        cursor.execute(
            "INSERT INTO projection_outbox("
            "sequence, event_id, project_id, envelope_json, next_attempt_at"
            ") VALUES (?, ?, ?, ?, ?)",
            (sequence, event.event_id, project_id, canonical_json(envelope), utc_now().isoformat()),
        )
        return event

    def register_identity(self, record: IdentityRecord) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO identities(subject_id, credential_id, record_json) VALUES (?, ?, ?)",
                (record.subject_id, record.credential_id, record.model_dump_json()),
            )
            self._emit(cursor, "system", "identity_registered", {"subject_id": record.subject_id})

    def identity(self, subject_id: str) -> IdentityRecord | None:
        row = self._connection.execute(
            "SELECT record_json FROM identities WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        return IdentityRecord.model_validate_json(row["record_json"]) if row else None

    def add_execution_grant(self, grant: ExecutionGrant) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO execution_grants(grant_id, subject_id, grant_json) VALUES (?, ?, ?)",
                (grant.grant_id, grant.subject_id, grant.model_dump_json()),
            )
            self._emit(cursor, "system", "execution_grant_added", {"grant_id": grant.grant_id})

    def add_approval_grant(self, grant: ApprovalGrant) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO approval_grants(grant_id, subject_id, grant_json) VALUES (?, ?, ?)",
                (grant.grant_id, grant.subject_id, grant.model_dump_json()),
            )
            self._emit(cursor, "system", "approval_grant_added", {"grant_id": grant.grant_id})

    def grants(
        self, subject_id: str
    ) -> tuple[tuple[ExecutionGrant, ...], tuple[ApprovalGrant, ...]]:
        execution_rows = self._connection.execute(
            "SELECT grant_json FROM execution_grants WHERE subject_id = ?", (subject_id,)
        ).fetchall()
        approval_rows = self._connection.execute(
            "SELECT grant_json FROM approval_grants WHERE subject_id = ?", (subject_id,)
        ).fetchall()
        return (
            tuple(ExecutionGrant.model_validate_json(row["grant_json"]) for row in execution_rows),
            tuple(ApprovalGrant.model_validate_json(row["grant_json"]) for row in approval_rows),
        )

    def revoke_approval_grant(self, grant_id: str) -> None:
        row = self._connection.execute(
            "SELECT grant_json FROM approval_grants WHERE grant_id = ?", (grant_id,)
        ).fetchone()
        if row is None:
            raise KeyError("approval grant does not exist")
        grant = ApprovalGrant.model_validate_json(row["grant_json"]).model_copy(
            update={"revoked_at": utc_now()}
        )
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE approval_grants SET grant_json = ? WHERE grant_id = ?",
                (grant.model_dump_json(), grant_id),
            )
            self._emit(cursor, "system", "approval_grant_revoked", {"grant_id": grant_id})

    def revoke_execution_grant(self, grant_id: str) -> None:
        row = self._connection.execute(
            "SELECT grant_json FROM execution_grants WHERE grant_id = ?", (grant_id,)
        ).fetchone()
        if row is None:
            raise KeyError("execution grant does not exist")
        grant = ExecutionGrant.model_validate_json(row["grant_json"]).model_copy(
            update={"revoked_at": utc_now()}
        )
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE execution_grants SET grant_json = ? WHERE grant_id = ?",
                (grant.model_dump_json(), grant_id),
            )
            self._emit(cursor, "system", "execution_grant_revoked", {"grant_id": grant_id})

    def claim_nonce(self, nonce: str, action_id: str, actor_id: str) -> bool:
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO used_nonces(nonce, action_id, actor_id, used_at) VALUES (?, ?, ?, ?)",
                    (nonce, action_id, actor_id, utc_now().isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def add_evidence(self, evidence: Evidence) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO evidence(evidence_id, project_id, evidence_json) VALUES (?, ?, ?)",
                (evidence.evidence_id, evidence.project_id, evidence.model_dump_json()),
            )
            self._emit(
                cursor, evidence.project_id, "evidence_observed", evidence.model_dump(mode="json")
            )

    def evidence(self, project_id: str) -> tuple[Evidence, ...]:
        rows = self._connection.execute(
            "SELECT evidence_json FROM evidence WHERE project_id = ? ORDER BY rowid", (project_id,)
        ).fetchall()
        return tuple(Evidence.model_validate_json(row["evidence_json"]) for row in rows)

    def add_run_summary(self, summary: RunSummary) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO run_summaries(run_id, project_id, summary_json) "
                "VALUES (?, ?, ?)",
                (summary.run_id, summary.project_id, summary.model_dump_json()),
            )
            self._emit(
                cursor, summary.project_id, "run_summarized", summary.model_dump(mode="json")
            )

    def run_summaries(self, project_id: str, limit: int) -> tuple[RunSummary, ...]:
        rows = self._connection.execute(
            "SELECT summary_json FROM run_summaries WHERE project_id = ? "
            "ORDER BY rowid DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return tuple(RunSummary.model_validate_json(row["summary_json"]) for row in reversed(rows))

    def record_plan(self, plan: Plan) -> None:
        with self.transaction() as cursor:
            row = cursor.execute(
                "SELECT digest FROM plans WHERE plan_id = ?", (plan.plan_id,)
            ).fetchone()
            if row:
                if row["digest"] != plan.digest():
                    raise ValueError("plan id already exists with a different digest")
                return
            cursor.execute(
                "INSERT INTO plans(plan_id, project_id, digest, plan_json) VALUES (?, ?, ?, ?)",
                (plan.plan_id, plan.goal.project_id, plan.digest(), plan.model_dump_json()),
            )
            self._emit(cursor, plan.goal.project_id, "plan_recorded", {"plan_id": plan.plan_id})

    def start_session(self, session_id: str, thread_id: str, goal: Any, requester_id: str) -> None:
        now = utc_now().isoformat()
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sessions("
                "session_id, thread_id, goal_json, requester_id, status, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    thread_id,
                    goal.model_dump_json(),
                    requester_id,
                    SessionStatus.PLANNING,
                    now,
                    now,
                ),
            )

    def update_session(self, session_id: str, status: SessionStatus) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                (status, utc_now().isoformat(), session_id),
            )

    def request_cancel(self, session_id: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE sessions SET cancel_requested = 1, status = ?, updated_at = ? "
                "WHERE session_id = ?",
                (SessionStatus.CANCELLED, utc_now().isoformat(), session_id),
            )

    def session(self, session_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def plan(self, plan_id: str) -> Plan | None:
        row = self._connection.execute(
            "SELECT plan_json FROM plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        return Plan.model_validate_json(row["plan_json"]) if row else None

    def record_decision(self, decision: VerificationResult) -> None:
        plan = self.plan(decision.plan_id)
        if plan is None:
            raise ValueError("decision cannot precede plan")
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT 1 FROM decisions WHERE decision_id = ?", (decision.decision_id,)
            ).fetchone()
            if existing:
                return
            cursor.execute(
                "INSERT INTO decisions(decision_id, plan_id, digest, decision_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.plan_id,
                    decision.plan_digest,
                    decision.model_dump_json(),
                ),
            )
            self._emit(
                cursor,
                plan.goal.project_id,
                "plan_verified",
                {
                    "decision_id": decision.decision_id,
                    "plan_id": decision.plan_id,
                    "allowed": decision.allowed,
                },
            )

    def latest_decision(self, plan_id: str) -> VerificationResult | None:
        row = self._connection.execute(
            "SELECT decision_json FROM decisions WHERE plan_id = ? ORDER BY sequence DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
        return VerificationResult.model_validate_json(row["decision_json"]) if row else None

    def approval_request(self, plan_id: str, step_id: str) -> ApprovalRequest | None:
        row = self._connection.execute(
            "SELECT request_json FROM approval_requests WHERE plan_id = ? AND step_id = ?",
            (plan_id, step_id),
        ).fetchone()
        return ApprovalRequest.model_validate_json(row["request_json"]) if row else None

    def approval_request_by_id(self, request_id: str) -> ApprovalRequest | None:
        row = self._connection.execute(
            "SELECT request_json FROM approval_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
        return ApprovalRequest.model_validate_json(row["request_json"]) if row else None

    def save_approval_request(self, request: ApprovalRequest) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO approval_requests("
                "request_id, plan_id, step_id, request_json"
                ") VALUES (?, ?, ?, ?)",
                (request.request_id, request.plan_id, request.step_id, request.model_dump_json()),
            )
            self._emit(
                cursor,
                request.project_id,
                "approval_requested",
                {"request_id": request.request_id, "step_id": request.step_id},
            )

    def save_approval(self, decision: ApprovalDecision, project_id: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO approvals(approval_id, request_id, approver_id, decision_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    decision.approval_id,
                    decision.request_id,
                    decision.approver_id,
                    decision.model_dump_json(),
                ),
            )
            self._emit(
                cursor,
                project_id,
                "approval_decided",
                {
                    "request_id": decision.request_id,
                    "approver_id": decision.approver_id,
                    "choice": decision.choice,
                },
            )

    def approvals(self, request_id: str) -> tuple[ApprovalDecision, ...]:
        rows = self._connection.execute(
            "SELECT decision_json FROM approvals WHERE request_id = ? ORDER BY rowid",
            (request_id,),
        ).fetchall()
        return tuple(ApprovalDecision.model_validate_json(row["decision_json"]) for row in rows)

    def update_approval_request(self, request: ApprovalRequest) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE approval_requests SET request_json = ? WHERE request_id = ?",
                (request.model_dump_json(), request.request_id),
            )

    def start_run(self, run_id: str, plan: Plan) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO runs(run_id, plan_id, status, started_at) VALUES (?, ?, ?, ?)",
                (run_id, plan.plan_id, SessionStatus.RUNNING, utc_now().isoformat()),
            )
            self._emit(
                cursor,
                plan.goal.project_id,
                "run_started",
                {"run_id": run_id, "plan_id": plan.plan_id},
            )

    def record_step(
        self,
        *,
        run_id: str,
        step_id: str,
        operator: str,
        status: StepStatus,
        idempotency_key: str,
        result: OperatorResult | None = None,
    ) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO step_runs(run_id, step_id, operator, status, idempotency_key, result_json) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(run_id, step_id) DO UPDATE SET "
                "status = excluded.status, result_json = excluded.result_json",
                (
                    run_id,
                    step_id,
                    operator,
                    status,
                    idempotency_key,
                    result.model_dump_json() if result else None,
                ),
            )
            if result:
                cursor.execute(
                    "INSERT OR REPLACE INTO operator_results("
                    "idempotency_key, run_id, step_id, status, result_json"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (idempotency_key, run_id, step_id, status, result.model_dump_json()),
                )

    def successful_result(self, idempotency_key: str) -> OperatorResult | None:
        row = self._connection.execute(
            "SELECT result_json FROM operator_results WHERE idempotency_key = ? AND status = ?",
            (idempotency_key, StepStatus.SUCCEEDED),
        ).fetchone()
        return OperatorResult.model_validate_json(row["result_json"]) if row else None

    def finish_run(self, run_id: str, plan: Plan, status: SessionStatus) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
                (status, utc_now().isoformat(), run_id),
            )
            self._emit(
                cursor,
                plan.goal.project_id,
                "run_finished",
                {"run_id": run_id, "plan_id": plan.plan_id, "status": status},
            )

    def record_model_invocation(self, invocation: ModelInvocation) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO model_invocations(invocation_id, session_id, invocation_json) "
                "VALUES (?, ?, ?)",
                (invocation.invocation_id, invocation.session_id, invocation.model_dump_json()),
            )

    def save_planner_profile(self, profile: PlannerProfile) -> None:
        with self.transaction() as cursor:
            row = cursor.execute(
                "SELECT profile_json FROM planner_profiles WHERE profile_id = ?",
                (profile.profile_id,),
            ).fetchone()
            if row:
                existing = PlannerProfile.model_validate_json(row["profile_json"])
                if existing.digest() != profile.digest():
                    raise ValueError("planner profile id already exists with different content")
                return
            cursor.execute(
                "INSERT INTO planner_profiles(profile_id, profile_json) VALUES (?, ?)",
                (profile.profile_id, profile.model_dump_json()),
            )

    def planner_profile(self, profile_id: str) -> PlannerProfile | None:
        row = self._connection.execute(
            "SELECT profile_json FROM planner_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        return PlannerProfile.model_validate_json(row["profile_json"]) if row else None

    def outbox_batch(self, limit: int = 100) -> tuple[dict[str, Any], ...]:
        rows = self._connection.execute(
            "SELECT sequence, envelope_json, attempts FROM projection_outbox "
            "WHERE projected_at IS NULL AND dead_lettered_at IS NULL AND next_attempt_at <= ? "
            "ORDER BY sequence LIMIT ?",
            (utc_now().isoformat(), limit),
        ).fetchall()
        return tuple(
            {
                "sequence": row["sequence"],
                "attempts": row["attempts"],
                **json.loads(row["envelope_json"]),
            }
            for row in rows
        )

    def mark_projected(self, sequence: int) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE projection_outbox SET projected_at = ?, last_error = NULL WHERE sequence = ?",
                (utc_now().isoformat(), sequence),
            )

    def mark_projection_failed(self, sequence: int, attempts: int, error: str) -> None:
        now = utc_now()
        dead = now.isoformat() if attempts >= 10 else None
        next_attempt = now + timedelta(seconds=min(300, 2 ** min(attempts, 8)))
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE projection_outbox SET attempts = ?, next_attempt_at = ?, "
                "dead_lettered_at = ?, last_error = ? WHERE sequence = ?",
                (attempts, next_attempt.isoformat(), dead, error[:1000], sequence),
            )

    def projection_health(self) -> ProjectionHealth:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS authoritative, "
            "COALESCE(MAX(CASE WHEN projected_at IS NOT NULL THEN sequence END), 0) AS projected, "
            "SUM(CASE WHEN projected_at IS NULL AND dead_lettered_at IS NULL THEN 1 ELSE 0 END) pending, "
            "SUM(CASE WHEN dead_lettered_at IS NOT NULL THEN 1 ELSE 0 END) dead, "
            "MAX(projected_at) last_success, "
            "MAX(CASE WHEN last_error IS NOT NULL THEN last_error END) last_error "
            "FROM projection_outbox"
        ).fetchone()
        pending = int(row["pending"] or 0)
        dead = int(row["dead"] or 0)
        status = (
            ProjectionStatus.DEGRADED
            if dead
            else ProjectionStatus.LAGGING
            if pending
            else ProjectionStatus.CURRENT
        )
        return ProjectionHealth(
            status=status,
            authoritative_sequence=int(row["authoritative"]),
            projected_sequence=int(row["projected"]),
            pending_count=pending,
            dead_letter_count=dead,
            last_success_at=row["last_success"],
            last_error=row["last_error"],
        )

    def acquire_lease(self, owner_id: str, ttl_seconds: int = 30) -> bool:
        now = utc_now()
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with self.transaction() as cursor:
            row = cursor.execute(
                "SELECT owner_id, expires_at FROM coordinator_lease WHERE lease_name = 'coordinator'"
            ).fetchone()
            if row and row["owner_id"] != owner_id and row["expires_at"] > now.isoformat():
                return False
            cursor.execute(
                "INSERT INTO coordinator_lease(lease_name, owner_id, expires_at) "
                "VALUES ('coordinator', ?, ?) ON CONFLICT(lease_name) DO UPDATE SET "
                "owner_id = excluded.owner_id, expires_at = excluded.expires_at",
                (owner_id, expires),
            )
        return True

    def close(self) -> None:
        self._connection.close()
