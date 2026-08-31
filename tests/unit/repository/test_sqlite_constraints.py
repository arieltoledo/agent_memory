import sqlite3
import pytest
from memory_agent.repository.sqlite import get_connection, apply_migrations

@pytest.fixture
def conn():
    connection = get_connection()
    apply_migrations(connection, "memory_agent/repository/migrations/0001_initial.sql")
    connection.execute("INSERT INTO core_snapshots (core_version, content_json, content_hash, created_at) VALUES (1, '{}', 'hash', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO branches (branch_id, name, status, current_revision, core_version, created_at) VALUES ('branch-1', 'main', 'ACTIVE', 1, 1, '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO policies (policy_snapshot_id, policy_version, policy_hash, source_ref, active, created_at) VALUES ('policy-1', 1, 'hash', 'ref', 1, '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-ref', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash0', 'model', 'v1', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-ref', 'patch-ref', 'hash0', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-ref', 'branch-1', 1, 'patch-ref', 'hash0', 'audit-ref', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    yield connection
    connection.close()

def test_patch_rechazado_no_bloquea_nueva_propuesta(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-1', 'branch-1', 1, 1, 'policy-1', 'AUDIT_REJECTED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'PROPOSED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    assert conn.execute("SELECT count(*) FROM patches WHERE patch_hash = 'hashX'").fetchone()[0] == 2

def test_replay_fails(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-1', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash1', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-1', 'patch-1', 'hash1', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-1', 'branch-1', 2, 'patch-1', 'hash1', 'audit-1', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-2', 'patch-1', 'hash1', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 3, 'patch-1', 'hash1', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")

def test_personal_inline_fails(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
            INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, inline_value_json, lifetime, policy_snapshot_id, created_by_commit_id, created_at) 
            VALUES ('record-1', 'PERSONAL', 'key1', 'PERSONAL_FACT', 'ACTIVE', 'ORDINARY', 'INLINE_NON_SENSITIVE', '"{}"', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')
        """)

def test_personal_vault_ref_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
            INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, inline_value_json, lifetime, policy_snapshot_id, created_by_commit_id, created_at) 
            VALUES ('record-1', 'PERSONAL', 'key1', 'PERSONAL_FACT', 'ACTIVE', 'ORDINARY', 'NONE', NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')
        """)

def test_purged_tombstone(conn):
    conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, created_at) VALUES ('payload-1', 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', '2026-08-31T00:00:00Z')")
    conn.execute("""
        INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, payload_id, lifetime, policy_snapshot_id, created_by_commit_id, created_at) 
        VALUES ('record-1', 'PERSONAL', 'key1', 'PERSONAL_FACT', 'PURGED', 'ORDINARY', 'VAULT_REF', 'payload-1', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')
    """)
    row = conn.execute("SELECT inline_value_json, payload_id FROM memory_records WHERE id = 'record-1'").fetchone()
    assert row['inline_value_json'] is None
    assert row['payload_id'] == 'payload-1'

def test_destroyed_payload(conn):
    conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, ciphertext_location, created_at) VALUES ('payload-1', 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', NULL, NULL, '2026-08-31T00:00:00Z')")
    row = conn.execute("SELECT status, key_handle, ciphertext_location FROM payload_objects WHERE id = 'payload-1'").fetchone()
    assert row['status'] == 'DESTROYED'
    assert row['key_handle'] is None
    assert row['ciphertext_location'] is None

def test_active_key_uniqueness(conn):
    conn.execute("""
        INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, branch_id, lifetime, policy_snapshot_id, created_by_commit_id, created_at) 
        VALUES ('record-1', 'OPERATIONAL', 'key1', 'OTHER', 'ACTIVE', 'ORDINARY', 'NONE', 'branch-1', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')
    """)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
            INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, branch_id, lifetime, policy_snapshot_id, created_by_commit_id, created_at) 
            VALUES ('record-2', 'OPERATIONAL', 'key1', 'OTHER', 'ACTIVE', 'ORDINARY', 'NONE', 'branch-1', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')
        """)

def test_revisions(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-1', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash1', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-1', 'patch-1', 'hash1', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-1', 'branch-1', 2, 'patch-1', 'hash1', 'audit-1', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash2', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-2', 'patch-2', 'hash2', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 2, 'patch-2', 'hash2', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")

def test_ghost_audit_rejected(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'PROPOSED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 2, 'patch-2', 'hashX', 'ghost-audit', 1, 'policy-1', '2026-08-31T00:00:00Z')")

def test_revision_zero_and_negative(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'PROPOSED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-2', 'patch-2', 'hashX', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 0, 'patch-2', 'hashX', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', -1, 'patch-2', 'hashX', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    # Positive control
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 2, 'patch-2', 'hashX', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")

def test_op_type_null_and_invalid(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type) VALUES ('op-1', 'patch-ref', 1, NULL)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type) VALUES ('op-1', 'patch-ref', 1, 'INVALID_OP')")
    # Positive control
    conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type) VALUES ('op-1', 'patch-ref', 1, 'ADD')")

def test_evidence_invalid_scope_and_none(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, storage_class, sanitization_applied, policy_snapshot_id, created_at) VALUES ('ev-1', 'INVALID', 'branch-1', 'kind', 'ACTIVE', 'ORDINARY', 'INLINE_NON_SENSITIVE', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, storage_class, sanitization_applied, policy_snapshot_id, created_at) VALUES ('ev-1', 'GLOBAL', NULL, 'kind', 'ACTIVE', 'ORDINARY', 'NONE', 1, 'policy-1', '2026-08-31T00:00:00Z')")

def test_payload_purpose_garbage(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, created_at) VALUES ('payload-1', 'GARBAGE', 'DESTROYED', 'ORDINARY', '2026-08-31T00:00:00Z')")
    # Positive
    conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, created_at) VALUES ('payload-1', 'EVIDENCE', 'DESTROYED', 'ORDINARY', '2026-08-31T00:00:00Z')")

def test_memory_record_session_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, lifetime, policy_snapshot_id, created_by_commit_id, created_at) VALUES ('rec-1', 'SESSION', 'key', 'kind', 'ACTIVE', 'ORDINARY', 'NONE', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, lifetime, policy_snapshot_id, created_by_commit_id, created_at) VALUES ('rec-1', 'OPERATIONAL', 'key', 'kind', 'ACTIVE', 'ORDINARY', 'NONE', 'SESSION', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')")

def test_supersession_roundtrip(conn):
    conn.execute("INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, branch_id, lifetime, policy_snapshot_id, created_by_commit_id, created_at) VALUES ('rec-a', 'OPERATIONAL', 'keyA', 'OTHER', 'SUPERSEDED', 'ORDINARY', 'NONE', 'branch-1', 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO memory_records (id, domain, semantic_key, kind, status, sensitivity, storage_class, branch_id, lifetime, policy_snapshot_id, created_by_commit_id, supersedes_record_id, created_at) VALUES ('rec-b', 'OPERATIONAL', 'keyB', 'OTHER', 'ACTIVE', 'ORDINARY', 'NONE', 'branch-1', 'DURABLE', 'policy-1', 'commit-ref', 'rec-a', '2026-08-31T00:00:00Z')")
    row = conn.execute("SELECT supersedes_record_id FROM memory_records WHERE id = 'rec-b'").fetchone()
    assert row['supersedes_record_id'] == 'rec-a'

def test_patch_operations_persistence_boundary(conn):
    # SENSITIVE + INLINE_NON_SENSITIVE must be rejected
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type, sensitivity, value_storage_class, inline_value_json) VALUES ('op-sens', 'patch-ref', 2, 'ADD', 'SENSITIVE', 'INLINE_NON_SENSITIVE', '\"secret\"')")
    # PROHIBITED is rejected
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type, sensitivity) VALUES ('op-pro', 'patch-ref', 2, 'ADD', 'PROHIBITED')")
    
    # Missing payload_id for VAULT_REF must be rejected
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type, value_storage_class, payload_id) VALUES ('op-vault', 'patch-ref', 2, 'ADD', 'VAULT_REF', NULL)")

def test_restored_constraints(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO branches (branch_id, name, status, current_revision, core_version, created_at) VALUES ('b2', 'b2', 'INVALID_STATUS', 1, 1, '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO branches (branch_id, name, status, current_revision, core_version, created_at) VALUES ('b2', 'b2', 'ACTIVE', -1, 1, '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('p2', 'branch-1', -1, 1, 'policy-1', 'PROPOSED', 'hx', 'model', 'v1', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO mount_policies (mount_policy_id, version, mode, allowed_scopes_json, allow_sensitive_operational_mount, policy_hash, created_at) VALUES ('mp1', 1, 'INVALID_MODE', '[]', 0, 'hash', '2026-08-31T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO mount_policies (mount_policy_id, version, mode, allowed_scopes_json, allow_sensitive_operational_mount, policy_hash, created_at) VALUES ('mp1', 1, 'BRANCH_ONLY', 'INVALID_JSON', 0, 'hash', '2026-08-31T00:00:00Z')")

def test_conflicts_schema_restored(conn):
    with pytest.raises(sqlite3.IntegrityError):
        # Should fail due to NOT NULL semantic_key and created_at if we omit them
        conn.execute("INSERT INTO conflicts (id, branch_id, status, opened_by_commit_id) VALUES ('c1', 'branch-1', 'OPEN', 'commit-ref')")
