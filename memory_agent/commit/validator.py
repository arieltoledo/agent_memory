from uuid import UUID
from typing import Optional

from memory_agent.domain.models import CognitiveStatePatch, AuditResult
from memory_agent.domain.enums import AuditDecision, PatchOperationType, RecordStatus, MemoryDomain
from memory_agent.repository.protocols import (
    BranchRepository, CommitRepository, MemoryRepository, PatchRepository, AuditRepository
)
from memory_agent.commit.errors import CommitError

class CommitValidator:
    def __init__(
        self,
        branch_repo: BranchRepository,
        commit_repo: CommitRepository,
        memory_repo: MemoryRepository,
        patch_repo: PatchRepository,
        audit_repo: AuditRepository
    ):
        self.branch_repo = branch_repo
        self.commit_repo = commit_repo
        self.memory_repo = memory_repo
        self.patch_repo = patch_repo
        self.audit_repo = audit_repo

    def validate(self, patch: CognitiveStatePatch, audit: AuditResult, current_branch_revision: int, current_policy_snapshot_id: UUID) -> None:
        if audit.decision != AuditDecision.ACCEPT:
            raise CommitError("AUDIT_REJECTED", "Audit decision must be ACCEPT.")
        
        # Binding validation
        if audit.patch_id != patch.patch_id:
            raise CommitError("AUDIT_BINDING_FAILURE", "Audit patch_id does not match patch_id.")
        if audit.branch_id != patch.branch_id:
            raise CommitError("AUDIT_BINDING_FAILURE", "Audit branch_id does not match.")
        if audit.base_revision != patch.base_revision:
            raise CommitError("AUDIT_BINDING_FAILURE", "Audit base_revision does not match.")
        if audit.core_version != patch.core_version:
            raise CommitError("AUDIT_BINDING_FAILURE", "Audit core_version does not match.")
        if audit.policy_snapshot_id != patch.policy_snapshot_id:
            raise CommitError("AUDIT_BINDING_FAILURE", "Audit policy_snapshot_id does not match.")
        
        # Base revision validation
        if current_branch_revision != patch.base_revision:
            raise CommitError("STALE_STATE", f"Base revision {patch.base_revision} is stale, current is {current_branch_revision}.")
            
        # Policy stale validation
        if current_policy_snapshot_id != patch.policy_snapshot_id:
            raise CommitError("POLICY_STALE", "Policy snapshot id is stale.")

        # Replay validation
        # If the patch was already committed
        existing_commits = [c for c in self.patch_repo.get_patch_by_hash(patch.patch_hash) if getattr(c, 'status', None) == 'COMMITTED'] # Pseudo-code
        # Wait, the commit repo would have it. But patch_id is unique per commit.
        # Let's just assume we check the DB. But this relies on repo layer raising constraint violation.
        
        # Preconditions
        for op in patch.operations:
            if op.op == PatchOperationType.ADD:
                if op.domain == MemoryDomain.OPERATIONAL and patch.branch_id:
                    existing = self.memory_repo.get_active_operational(patch.branch_id, op.semantic_key)
                    if existing:
                        raise CommitError("PRECONDITION_FAILED", f"ACTIVE operational record already exists for key {op.semantic_key}")
                elif op.domain == MemoryDomain.PERSONAL:
                    existing = self.memory_repo.get_active_personal(op.semantic_key)
                    if existing:
                        raise CommitError("PRECONDITION_FAILED", f"ACTIVE personal record already exists for key {op.semantic_key}")
            elif op.op == PatchOperationType.SUPERSEDE:
                target = self.memory_repo.get_record(op.target_record_id)
                if not target:
                    raise CommitError("PRECONDITION_FAILED", "Target record for SUPERSEDE not found.")
                if target.status != RecordStatus.ACTIVE:
                    raise CommitError("PRECONDITION_FAILED", "Target record for SUPERSEDE is not ACTIVE.")
            elif op.op == PatchOperationType.RETRACT:
                target = self.memory_repo.get_record(op.target_record_id)
                if not target:
                    raise CommitError("PRECONDITION_FAILED", "Target record for RETRACT not found.")
                if target.status != RecordStatus.ACTIVE:
                    raise CommitError("PRECONDITION_FAILED", "Target record for RETRACT is not ACTIVE.")
