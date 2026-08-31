import sqlite3
import pytest
from memory_agent.repository.sqlite import get_connection, apply_migrations

@pytest.fixture
def conn():
    connection = get_connection()
    apply_migrations(connection, "memory_agent/repository/migrations/0001_initial.sql")
    connection.execute("INSERT INTO core_snapshots (core_version, content_json, content_hash, created_at) VALUES (1, '{}', 'hash', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO branches (branch_id, name, status, current_revision, core_version, created_at) VALUES ('branch-1', 'main', 'ACTIVE', 0, 1, '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO policies (policy_snapshot_id, policy_version, policy_hash, source_ref, active, created_at) VALUES ('policy-1', 1, 'hash', 'ref', 1, '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-ref', 'branch-1', 0, 1, 'policy-1', 'COMMITTED', 'hash0', 'model', 'v1', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-ref', 'patch-ref', 'hash0', 'branch-1', 0, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-ref', 'branch-1', 0, 'patch-ref', 'hash0', 'audit-ref', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    yield connection
    connection.close()

def test_patch_rechazado_no_bloquea_nueva_propuesta(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-1', 'branch-1', 1, 1, 'policy-1', 'AUDIT_REJECTED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'PROPOSED', 'hashX', 'model', 'v1', '2026-08-31T00:00:00Z')")
    assert conn.execute("SELECT count(*) FROM patches WHERE patch_hash = 'hashX'").fetchone()[0] == 2

def test_replay_fails(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-1', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash1', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-1', 'patch-1', 'hash1', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-1', 'branch-1', 1, 'patch-1', 'hash1', 'audit-1', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-2', 'patch-1', 'hash1', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 2, 'patch-1', 'hash1', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")

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
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-1', 'branch-1', 1, 'patch-1', 'hash1', 'audit-1', 1, 'policy-1', '2026-08-31T00:00:00Z')")
    
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) VALUES ('patch-2', 'branch-1', 1, 1, 'policy-1', 'COMMITTED', 'hash2', 'model', 'v1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, auditor_prompt_version, created_at) VALUES ('audit-2', 'patch-2', 'hash2', 'branch-1', 1, 1, 'policy-1', 'ev', 'ACCEPT', '[]', 'model', 'v1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) VALUES ('commit-2', 'branch-1', 1, 'patch-2', 'hash2', 'audit-2', 1, 'policy-1', '2026-08-31T00:00:00Z')")
