"""Signed local identities, deterministic grants, and tiered approvals."""

from __future__ import annotations

import base64
from datetime import timedelta
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .contracts import (
    ApprovalChoice,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    IdentityRecord,
    IdentitySnapshot,
    RiskLevel,
    SignedAction,
    content_digest,
    utc_now,
)
from .ledger import AuthorityStore


class AuthenticationError(RuntimeError):
    pass


class AuthorizationError(RuntimeError):
    pass


class LocalSigner:
    def __init__(
        self,
        *,
        subject_id: str,
        credential_id: str,
        private_key: Ed25519PrivateKey,
    ) -> None:
        self.subject_id = subject_id
        self.credential_id = credential_id
        self.private_key = private_key

    @classmethod
    def generate(cls, subject_id: str, credential_id: str | None = None) -> LocalSigner:
        return cls(
            subject_id=subject_id,
            credential_id=credential_id or str(uuid4()),
            private_key=Ed25519PrivateKey.generate(),
        )

    def identity_record(self, roles: frozenset[str] = frozenset()) -> IdentityRecord:
        public = self.private_key.public_key().public_bytes_raw()
        return IdentityRecord(
            subject_id=self.subject_id,
            credential_id=self.credential_id,
            public_key_base64=base64.b64encode(public).decode(),
            roles=roles,
        )

    def sign(
        self,
        *,
        action: str,
        payload: object,
        ttl: timedelta = timedelta(minutes=5),
    ) -> SignedAction:
        unsigned = SignedAction.unsigned(
            action_id=str(uuid4()),
            actor_id=self.subject_id,
            credential_id=self.credential_id,
            action=action,
            payload_digest=content_digest(payload),
            nonce=str(uuid4()),
            ttl=ttl,
        )
        signature = self.private_key.sign(unsigned.signing_bytes())
        return unsigned.model_copy(
            update={"signature_base64": base64.b64encode(signature).decode()}
        )


class IdentityService:
    def __init__(self, store: AuthorityStore, *, policy_version: str) -> None:
        self.store = store
        self.policy_version = policy_version

    def snapshot(self, subject_id: str) -> IdentitySnapshot:
        record = self.store.identity(subject_id)
        if record is None or not record.active:
            raise AuthenticationError("identity is unknown or inactive")
        execution, approval = self.store.grants(subject_id)
        return IdentitySnapshot(
            subject_id=record.subject_id,
            credential_id=record.credential_id,
            identity_version=record.version,
            roles=record.roles,
            execution_grants=execution,
            approval_grants=approval,
            policy_version=self.policy_version,
        )

    def authenticate(
        self,
        signed: SignedAction,
        *,
        expected_action: str,
        expected_payload: object,
    ) -> IdentitySnapshot:
        now = utc_now()
        if signed.action != expected_action:
            raise AuthenticationError("signed action type does not match")
        if signed.payload_digest != content_digest(expected_payload):
            raise AuthenticationError("signed payload digest does not match")
        if signed.issued_at > now + timedelta(seconds=30) or signed.expires_at <= now:
            raise AuthenticationError("signed action is expired or issued in the future")
        record = self.store.identity(signed.actor_id)
        if record is None or not record.active or record.credential_id != signed.credential_id:
            raise AuthenticationError("credential is unknown or inactive")
        try:
            public = Ed25519PublicKey.from_public_bytes(base64.b64decode(record.public_key_base64))
            public.verify(base64.b64decode(signed.signature_base64), signed.signing_bytes())
        except (InvalidSignature, ValueError) as exc:
            raise AuthenticationError("invalid action signature") from exc
        if not self.store.claim_nonce(signed.nonce, signed.action_id, signed.actor_id):
            raise AuthenticationError("signed action nonce was already used")
        return self.snapshot(signed.actor_id)


class ApprovalService:
    def __init__(
        self,
        store: AuthorityStore,
        identities: IdentityService,
        *,
        ttl: timedelta = timedelta(hours=24),
    ) -> None:
        self.store = store
        self.identities = identities
        self.ttl = ttl

    @staticmethod
    def required_count(risk: RiskLevel, explicitly_required: bool) -> int:
        if risk == RiskLevel.CRITICAL:
            return 2
        if risk == RiskLevel.HIGH or explicitly_required:
            return 1
        return 0

    def ensure_request(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        step_id: str,
        project_id: str,
        requester_id: str,
        risk: RiskLevel,
        required: int,
    ) -> ApprovalRequest:
        existing = self.store.approval_request(plan_id, step_id)
        if existing:
            if existing.plan_digest != plan_digest:
                raise AuthorizationError("approval request is bound to another plan digest")
            return existing
        now = utc_now()
        request = ApprovalRequest(
            request_id=str(uuid4()),
            plan_id=plan_id,
            plan_digest=plan_digest,
            step_id=step_id,
            project_id=project_id,
            requester_id=requester_id,
            risk=risk,
            required_approvals=required,
            policy_version=self.identities.policy_version,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + self.ttl,
        )
        self.store.save_approval_request(request)
        return request

    def decide(
        self,
        *,
        request_id: str,
        choice: ApprovalChoice,
        reason: str,
        signed_action: SignedAction,
    ) -> ApprovalDecision:
        request = self.store.approval_request_by_id(request_id)
        if request is None:
            raise AuthorizationError("approval request does not exist")
        payload = {"request_id": request_id, "choice": choice, "reason": reason}
        snapshot = self.identities.authenticate(
            signed_action, expected_action="approval_decision", expected_payload=payload
        )
        if (
            request.expires_at <= utc_now()
            or request.policy_version != self.identities.policy_version
        ):
            raise AuthorizationError("approval request is expired or stale")
        if request.status != ApprovalStatus.PENDING:
            raise AuthorizationError("approval request is not pending")
        if snapshot.subject_id == request.requester_id:
            raise AuthorizationError("requester cannot approve their own plan")
        if not any(
            grant.permits(request.risk, request.project_id, utc_now())
            for grant in snapshot.approval_grants
        ):
            raise AuthorizationError("identity lacks approval authority")
        decision = ApprovalDecision(
            approval_id=str(uuid4()),
            request_id=request_id,
            approver_id=snapshot.subject_id,
            choice=choice,
            reason=reason,
            identity_snapshot_digest=snapshot.digest(),
            signed_action_id=signed_action.action_id,
        )
        self.store.save_approval(decision, request.project_id)
        decisions = self.store.approvals(request_id)
        status = (
            ApprovalStatus.DENIED
            if any(item.choice == ApprovalChoice.DENY for item in decisions)
            else ApprovalStatus.APPROVED
            if len({item.approver_id for item in decisions}) >= request.required_approvals
            else ApprovalStatus.PENDING
        )
        self.store.update_approval_request(request.model_copy(update={"status": status}))
        return decision

    def satisfied(self, request: ApprovalRequest) -> bool:
        if (
            request.status != ApprovalStatus.APPROVED
            or request.expires_at <= utc_now()
            or request.policy_version != self.identities.policy_version
        ):
            return False
        valid: set[str] = set()
        for decision in self.store.approvals(request.request_id):
            if decision.choice != ApprovalChoice.APPROVE:
                continue
            try:
                snapshot = self.identities.snapshot(decision.approver_id)
            except AuthenticationError:
                continue
            if snapshot.digest() != decision.identity_snapshot_digest:
                continue
            if any(
                grant.permits(request.risk, request.project_id, utc_now())
                for grant in snapshot.approval_grants
            ):
                valid.add(decision.approver_id)
        return len(valid) >= request.required_approvals
