from uuid import UUID
from typing import Optional, List

from memory_agent.domain.models import CognitiveStatePatch, AuditResult
from memory_agent.domain.enums import AuditDecision, PatchOperationType, RecordStatus, MemoryDomain
from memory_agent.repository.protocols import (
    BranchRepository, CommitRepository, MemoryRepository, PatchRepository, AuditRepository
)
from memory_agent.domain.errors import DomainValidationError

class CommitValidationException(Exception):
    pass

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

    def validate(self, patch: CognitiveStatePatch, audit: AuditResult, current_branch_revision: int) -> None:
        if audit.decision != AuditDecision.ACCEPT:
            raise CommitValidationException("Audit decision must be ACCEPT.")
        
        # Binding validation
        if audit.patch_id != patch.patch_id:
            raise CommitValidationException("Audit patch_id does not match patch_id.")
        if audit.branch_id != patch.branch_id:
            raise CommitValidationException("Audit branch_id does not match.")
        if audit.base_revision != patch.base_revision:
            raise CommitValidationException("Audit base_revision does not match.")
        if audit.core_version != patch.core_version:
            raise CommitValidationException("Audit core_version does not match.")
        if audit.policy_snapshot_id != patch.policy_snapshot_id:
            raise CommitValidationException("Audit policy_snapshot_id does not match.")
        
        # Base revision validation
        if current_branch_revision != patch.base_revision:
            raise CommitValidationException("Base revision is stale.")
            
        # Preconditions
        for op in patch.operations:
            if op.op == PatchOperationType.ADD:
                if op.domain == MemoryDomain.OPERATIONAL and patch.branch_id:
                    existing = self.memory_repo.get_active_operational(patch.branch_id, op.semantic_key)
                    if existing:
                        raise CommitValidationException(f"ACTIVE operational record already exists for key {op.semantic_key}")
                elif op.domain == MemoryDomain.PERSONAL:
                    existing = self.memory_repo.get_active_personal(op.semantic_key)
                    if existing:
                        raise CommitValidationException(f"ACTIVE personal record already exists for key {op.semantic_key}")
            elif op.op == PatchOperationType.SUPERSEDE:
                target = self.memory_repo.get_record(op.target_record_id)
                if not target:
                    raise CommitValidationException("Target record for SUPERSEDE not found.")
                if target.status != RecordStatus.ACTIVE:
                    raise CommitValidationException("Target record for SUPERSEDE is not ACTIVE.")
            elif op.op == PatchOperationType.RETRACT:
                target = self.memory_repo.get_record(op.target_record_id)
                if not target:
                    raise CommitValidationException("Target record for RETRACT not found.")
                if target.status != RecordStatus.ACTIVE:
                    raise CommitValidationException("Target record for RETRACT is not ACTIVE.")
            elif op.op == PatchOperationType.LINK:
                pass
            elif op.op == PatchOperationType.FLAG_CONFLICT:
                pass
            elif op.op == PatchOperationType.RESOLVE_CONFLICT:
                pass
            elif op.op == PatchOperationType.PURGE_REQUEST:
                pass
