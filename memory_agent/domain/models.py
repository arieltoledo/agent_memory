from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretBytes, model_validator

from .enums import *
from .errors import DomainValidationError


class DomainModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class PersistentModel(DomainModel):
    @model_validator(mode="after")
    def _aware_datetimes(self):
        for value in self.__dict__.values():
            if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
                raise DomainValidationError("persisted datetimes must be timezone-aware")
        return self


JsonValue = Any


class EphemeralInput(DomainModel):
    input_id: UUID; session_id: UUID; text: str; received_at: datetime; timezone: str


class RestrictionSpan(DomainModel):
    span_id: UUID; input_id: UUID; start: int = Field(ge=0); end: int = Field(gt=0); category: str; restriction: RestrictionLevel; detector_id: str; confidence: float | None = None
    @model_validator(mode="after")
    def _valid_span(self):
        if self.start >= self.end or self.restriction == RestrictionLevel.NONE: raise DomainValidationError("restriction span must be non-empty and restricted")
        return self


class RestrictionMap(DomainModel):
    input_id: UUID; spans: tuple[RestrictionSpan, ...]
    def max_restriction_for_range(self, start: int, end: int) -> RestrictionLevel:
        levels = {RestrictionLevel.NONE: 0, RestrictionLevel.POTENTIALLY_SENSITIVE: 1, RestrictionLevel.NEVER_DURABLE: 2}
        applicable = [s.restriction for s in self.spans if s.start < end and start < s.end]
        return max(applicable, key=levels.get, default=RestrictionLevel.NONE)
    def restriction_for_range(self, start: int, end: int) -> RestrictionLevel: return self.max_restriction_for_range(start, end)
    def intersects_never_durable(self, start: int, end: int) -> bool: return self.max_restriction_for_range(start, end) == RestrictionLevel.NEVER_DURABLE


class MemoryCandidate(DomainModel):
    candidate_id: UUID; input_id: UUID; source_start: int; source_end: int; domain_hint: MemoryDomain; semantic_type: SemanticType; sensitivity: Sensitivity; persistence_intent: PersistenceIntent; temporal_scope: TemporalScope; subject: SubjectKind; polarity: Polarity; modality: Modality; semantic_key: str | None; analyzer_model_id: str; analyzer_prompt_version: str; source_span_ids: tuple[UUID, ...]

class PolicySnapshot(PersistentModel): policy_snapshot_id: UUID; policy_version: int; policy_hash: str; activated_at: datetime
class PolicyEvaluation(DomainModel): candidate_id: UUID; policy_snapshot_id: UUID; decision: PolicyDecision; effective_restriction: RestrictionLevel; reason_codes: tuple[str, ...]
class TemporalResolution(PersistentModel): source_expression: str | None; resolved_at: datetime; valid_until: datetime | None; timezone: str; resolution_status: Literal["RESOLVED", "NOT_REQUIRED", "DEFER"]
class SanitizedCandidate(DomainModel): candidate_id: UUID; policy_snapshot_id: UUID; semantic_key: str; domain: MemoryDomain; semantic_type: SemanticType; sensitivity: Sensitivity; sanitized_text: str | None; payload_ref: UUID | None; removed_categories: tuple[str, ...]; source_span_ids: tuple[UUID, ...]; temporal: TemporalResolution | None


class ValueReference(DomainModel):
    storage_class: ValueStorageClass; inline_value: JsonValue | None = None; payload_ref: UUID | None = None; ciphertext_digest: str | None = None
    @model_validator(mode="after")
    def _storage_shape(self):
        if self.storage_class == ValueStorageClass.INLINE_NON_SENSITIVE and (self.inline_value is None or self.payload_ref or self.ciphertext_digest): raise DomainValidationError("inline values require only inline_value")
        if self.storage_class == ValueStorageClass.VAULT_REF and (self.payload_ref is None or self.ciphertext_digest is None or self.inline_value is not None): raise DomainValidationError("vault values require payload_ref and ciphertext_digest only")
        if self.storage_class == ValueStorageClass.NONE and any(v is not None for v in (self.inline_value, self.payload_ref, self.ciphertext_digest)): raise DomainValidationError("NONE cannot carry a value")
        return self


class EvidenceRecord(PersistentModel):
    evidence_id: UUID; scope_type: Literal["BRANCH", "PERSONAL", "GLOBAL"]; branch_id: UUID | None; source_kind: str; status: EvidenceStatus; sensitivity: Sensitivity; storage_class: ValueStorageClass; inline_sanitized_text: str | None; payload_ref: UUID | None; sanitization_applied: bool; removed_categories: tuple[str, ...]; policy_snapshot_id: UUID; created_at: datetime
    @model_validator(mode="after")
    def _not_prohibited(self):
        if self.sensitivity == Sensitivity.PROHIBITED: raise DomainValidationError("prohibited evidence is not durable")
        return self

class PayloadObject(PersistentModel):
    payload_id: UUID; purpose: Literal["EVIDENCE", "MEMORY_VALUE", "PATCH_VALUE"]; status: PayloadStatus; sensitivity: Sensitivity; key_handle: str | None; ciphertext_location: str | None; created_at: datetime; activated_at: datetime | None; destroyed_at: datetime | None
    @model_validator(mode="after")
    def _payload_state(self):
        destroyed = self.status in {PayloadStatus.DESTROYED, PayloadStatus.ABORTED}
        if destroyed != (self.key_handle is None and self.ciphertext_location is None): raise DomainValidationError("destroyed payloads alone may clear key and location")
        return self

class DraftValue(DomainModel): proposed_value: JsonValue
class DraftPatch(DomainModel): draft_patch_id: UUID; branch_id: UUID | None; base_revision: int; core_version: int; policy_snapshot_id: UUID; operations: tuple[dict[str, Any], ...]
class PendingPayloadEnvelope(DomainModel): payload_id: UUID; ciphertext: bytes; ciphertext_digest: str; key_material: SecretBytes; purpose: str; sensitivity: Sensitivity
class PendingValueReference(DomainModel): storage_class: Literal[ValueStorageClass.VAULT_REF]; payload_ref: UUID; ciphertext_digest: str

class AddOperation(DomainModel): op: Literal[PatchOperationType.ADD]; operation_id: UUID; domain: MemoryDomain; semantic_key: str; sensitivity: Sensitivity; value: ValueReference; evidence_refs: tuple[UUID, ...]; lifetime: Lifetime; valid_until: datetime | None; mount_policy_id: UUID | None
class SupersedeOperation(DomainModel): op: Literal[PatchOperationType.SUPERSEDE]; operation_id: UUID; target_record_id: UUID; sensitivity: Sensitivity; value: ValueReference; evidence_refs: tuple[UUID, ...]; lifetime: Lifetime; valid_until: datetime | None
class RetractOperation(DomainModel): op: Literal[PatchOperationType.RETRACT]; operation_id: UUID; target_record_id: UUID; evidence_refs: tuple[UUID, ...]
class LinkOperation(DomainModel): op: Literal[PatchOperationType.LINK]; operation_id: UUID; source_record_id: UUID; target_record_id: UUID; relation_type: str; evidence_refs: tuple[UUID, ...]
class FlagConflictOperation(DomainModel): op: Literal[PatchOperationType.FLAG_CONFLICT]; operation_id: UUID; semantic_key: str; competing_record_refs: tuple[UUID, ...]; evidence_refs: tuple[UUID, ...]
class ResolveConflictOperation(DomainModel): op: Literal[PatchOperationType.RESOLVE_CONFLICT]; operation_id: UUID; conflict_id: UUID; winning_record_id: UUID | None; replacement: ValueReference | None; evidence_refs: tuple[UUID, ...]
class PurgeRequestOperation(DomainModel): op: Literal[PatchOperationType.PURGE_REQUEST]; operation_id: UUID; target_record_id: UUID; reason_code: str
PatchOperation = Annotated[Union[AddOperation, SupersedeOperation, RetractOperation, LinkOperation, FlagConflictOperation, ResolveConflictOperation, PurgeRequestOperation], Field(discriminator="op")]

class CognitiveStatePatch(DomainModel): patch_id: UUID; branch_id: UUID | None; base_revision: int; core_version: int; policy_snapshot_id: UUID; operations: tuple[PatchOperation, ...]; generator_model_id: str; generator_prompt_version: str
class AuditResult(PersistentModel): audit_id: UUID; patch_id: UUID; patch_hash: str; branch_id: UUID | None; base_revision: int; core_version: int; policy_snapshot_id: UUID; evidence_refs: tuple[UUID, ...]; evidence_binding: str; decision: AuditDecision; reason_codes: tuple[str, ...]; auditor_model_id: str; auditor_prompt_version: str; created_at: datetime
class CommitRecord(PersistentModel): commit_id: UUID; branch_id: UUID; revision: int; previous_commit_id: UUID | None; patch_id: UUID; patch_hash: str; audit_id: UUID; core_version: int; policy_snapshot_id: UUID; committed_at: datetime

class MemoryRecord(PersistentModel):
    record_id: UUID; domain: MemoryDomain; branch_id: UUID | None; semantic_key: str; kind: SemanticType; status: RecordStatus; sensitivity: Sensitivity; storage_class: ValueStorageClass; inline_value: JsonValue | None; payload_ref: UUID | None; lifetime: Lifetime; valid_until: datetime | None; timezone: str | None; policy_snapshot_id: UUID; mount_policy_id: UUID | None; created_commit_id: UUID; supersedes_record_id: UUID | None; created_at: datetime; purged_at: datetime | None
    @model_validator(mode="after")
    def _memory_storage(self):
        if self.sensitivity == Sensitivity.PROHIBITED: raise DomainValidationError("prohibited memory is never durable")
        if self.domain == MemoryDomain.PERSONAL and (self.storage_class != ValueStorageClass.VAULT_REF or self.payload_ref is None or self.inline_value is not None): raise DomainValidationError("personal memory must be vault-backed")
        if self.status == RecordStatus.PURGED and self.domain == MemoryDomain.PERSONAL and self.inline_value is not None: raise DomainValidationError("purged tombstones cannot retain inline values")
        return self

class ConflictRecord(DomainModel): conflict_id: UUID; branch_id: UUID; semantic_key: str; status: ConflictStatus; created_commit_id: UUID; resolved_commit_id: UUID | None
class MountPolicy(DomainModel): mount_policy_id: UUID; version: int; mode: Literal["GLOBAL_INTERACTION_PREFERENCE", "BRANCH_ONLY", "EXPLICIT_SCOPES", "EXPLICIT_ONLY"]; allowed_scopes: tuple[str, ...]; allow_sensitive_operational_mount: bool; policy_hash: str
class AccessLease(PersistentModel): lease_id: UUID; record_id: UUID; requested_scope: str; active_branch_id: UUID | None; policy_snapshot_id: UUID; status: LeaseStatus; issued_at: datetime; expires_at: datetime; revoked_at: datetime | None
class PurgeJob(PersistentModel): purge_id: UUID; record_id: UUID; status: PurgeStatus; requested_at: datetime; started_at: datetime | None; completed_at: datetime | None; failure_code: str | None
class PurgeTargetResult(PersistentModel): purge_id: UUID; target_id: str; purge_attempted: bool; purge_succeeded: bool; verify_absent: bool; last_checked_at: datetime; failure_code: str | None
class DetectionEvent(PersistentModel): event_id: UUID; run_id: UUID | None; threat_type: str; expected_detection_layer: DetectionLayer | None; actual_detection_layer: DetectionLayer | None; security_outcome: SecurityOutcome; architectural_outcome: ArchitecturalOutcome; policy_bypass: bool; category: str | None; created_at: datetime
class TestRun(PersistentModel): run_id: UUID; test_id: str; run_kind: Literal["GOLDEN", "ADVERSARIAL", "UNIT", "INTEGRATION"]; spec_version: str; technical_design_version: str; git_commit: str; policy_snapshot_id: UUID | None; analyzer_model_id: str | None; generator_model_id: str | None; auditor_model_id: str | None; analyzer_prompt_version: str | None; generator_prompt_version: str | None; auditor_prompt_version: str | None; temperature: float | None; seed: int | None; result: str; input_tokens: int | None; output_tokens: int | None; latency_ms: int | None; started_at: datetime; ended_at: datetime | None
class SessionState(DomainModel): session_id: UUID; created_at: datetime; expires_at: datetime; conversational_items: list[Any]
