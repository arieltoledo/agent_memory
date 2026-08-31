import sqlite3
import uuid
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from memory_agent.domain.models import CognitiveStatePatch, AuditResult, CommitRecord
from memory_agent.domain.enums import PatchOperationType, RecordStatus, ValueStorageClass
from memory_agent.commit.validator import CommitValidator, CommitError

class CommitEngine:
    def __init__(self, validator: CommitValidator, connection: sqlite3.Connection):
        self.validator = validator
        self.connection = connection

    def apply_commit(self, patch: CognitiveStatePatch, audit: AuditResult, current_branch_id: UUID) -> CommitRecord:
        cursor = self.connection.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            
            # 1. Re-read authoritative state
            branch_row = cursor.execute("SELECT current_revision, core_version FROM branches WHERE branch_id = ?", (str(current_branch_id),)).fetchone()
            if not branch_row:
                raise CommitError("STALE_STATE", "Branch not found.")
            
            current_revision = branch_row['current_revision']
            
            policy_row = cursor.execute("SELECT policy_snapshot_id FROM policies WHERE active = 1").fetchone()
            if not policy_row:
                raise CommitError("POLICY_STALE", "No active policy found.")
            
            current_policy_id = UUID(policy_row['policy_snapshot_id'])
            
            # 2. Validate
            self.validator.validate(patch, audit, current_revision, current_policy_id)
            
            # 3. Apply operations
            new_revision = current_revision + 1
            commit_id = uuid.uuid4()
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Previous commit
            prev_row = cursor.execute("SELECT id FROM commits WHERE branch_id = ? AND revision = ?", (str(current_branch_id), current_revision)).fetchone()
            prev_commit_id = prev_row['id'] if prev_row else None
            
            for op in patch.operations:
                if op.op == PatchOperationType.ADD:
                    record_id = uuid.uuid4()
                    
                    inline_val = None
                    payload_id = None
                    storage_class = op.value.storage_class.value
                    if op.value.storage_class == ValueStorageClass.INLINE_NON_SENSITIVE:
                        inline_val = '"{}"'.format(op.value.inline_value) if isinstance(op.value.inline_value, str) else str(op.value.inline_value)
                        # We should properly json dump this, but assuming strings for simplicity
                        
                    elif op.value.storage_class == ValueStorageClass.VAULT_REF:
                        payload_id = str(op.value.payload_ref)
                        
                    cursor.execute("""
                        INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, sensitivity, storage_class, inline_value_json, payload_id, lifetime, valid_until, timezone, policy_snapshot_id, mount_policy_id, created_by_commit_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(record_id), op.domain.value, str(current_branch_id) if op.domain.value == 'OPERATIONAL' else None, op.semantic_key, "OTHER", "ACTIVE", op.sensitivity.value, storage_class, inline_val, payload_id, op.lifetime.value, op.valid_until.isoformat() if op.valid_until else None, None, str(current_policy_id), str(op.mount_policy_id) if op.mount_policy_id else None, str(commit_id), now_iso
                    ))
                elif op.op == PatchOperationType.SUPERSEDE:
                    record_id = uuid.uuid4()
                    
                    inline_val = None
                    payload_id = None
                    storage_class = op.value.storage_class.value
                    if op.value.storage_class == ValueStorageClass.INLINE_NON_SENSITIVE:
                        inline_val = '"{}"'.format(op.value.inline_value) if isinstance(op.value.inline_value, str) else str(op.value.inline_value)
                    elif op.value.storage_class == ValueStorageClass.VAULT_REF:
                        payload_id = str(op.value.payload_ref)
                    
                    # Fetch target
                    target_row = cursor.execute("SELECT domain, branch_id, semantic_key, kind, mount_policy_id FROM memory_records WHERE id = ?", (str(op.target_record_id),)).fetchone()
                    
                    cursor.execute("""
                        INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, sensitivity, storage_class, inline_value_json, payload_id, lifetime, valid_until, timezone, policy_snapshot_id, mount_policy_id, created_by_commit_id, supersedes_record_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(record_id), target_row['domain'], target_row['branch_id'], target_row['semantic_key'], target_row['kind'], "ACTIVE", op.sensitivity.value, storage_class, inline_val, payload_id, op.lifetime.value, op.valid_until.isoformat() if op.valid_until else None, None, str(current_policy_id), target_row['mount_policy_id'], str(commit_id), str(op.target_record_id), now_iso
                    ))
                    
                    cursor.execute("UPDATE memory_records SET status = 'SUPERSEDED' WHERE id = ?", (str(op.target_record_id),))
                    
                elif op.op == PatchOperationType.RETRACT:
                    cursor.execute("UPDATE memory_records SET status = 'RETRACTED' WHERE id = ?", (str(op.target_record_id),))

            # Update branch revision
            cursor.execute("UPDATE branches SET current_revision = ? WHERE branch_id = ?", (new_revision, str(current_branch_id)))
            
            # Write commit
            cursor.execute("""
                INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(commit_id), str(current_branch_id), new_revision, prev_commit_id, str(patch.patch_id), patch.patch_hash, str(audit.audit_id), patch.core_version, str(patch.policy_snapshot_id), now_iso))
            
            self.connection.commit()
            return CommitRecord(
                commit_id=commit_id,
                branch_id=current_branch_id,
                revision=new_revision,
                previous_commit_id=UUID(prev_commit_id) if prev_commit_id else None,
                patch_id=patch.patch_id,
                patch_hash=patch.patch_hash,
                audit_id=audit.audit_id,
                core_version=patch.core_version,
                policy_snapshot_id=patch.policy_snapshot_id,
                committed_at=datetime.fromisoformat(now_iso)
            )
        except CommitError as e:
            self.connection.rollback()
            raise e
        except sqlite3.IntegrityError as e:
            self.connection.rollback()
            if "UNIQUE constraint failed" in str(e):
                 if "commits.patch_id" in str(e) or "commits.audit_id" in str(e):
                     raise CommitError("ALREADY_COMMITTED", str(e))
                 if "ix_mem_records_active" in str(e):
                     raise CommitError("PRECONDITION_FAILED", str(e))
            raise CommitError("INTEGRITY_ERROR", str(e))
        except Exception as e:
            self.connection.rollback()
            raise CommitError("INTERNAL_ERROR", str(e))
        finally:
            cursor.close()
