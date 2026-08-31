import sqlite3
import pytest
from memory_agent.repository.sqlite import get_connection, apply_migrations

@pytest.fixture
def conn():
    connection = get_connection()
    apply_migrations(connection, "memory_agent/repository/migrations/0001_initial.sql")
    # Insert common data to satisfy FKs
    connection.execute("INSERT INTO branches (id, name, created_at) VALUES ('branch-1', 'main', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO policies (id, version, policy_hash, activated_at) VALUES ('policy-1', 1, 'hash', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-ref', 'branch-1', 0, 'COMMITTED', 'hash0', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO audits (id, patch_id, decision, policy_snapshot_id, audited_at) VALUES ('audit-ref', 'patch-ref', 'ACCEPT', 'policy-1', '2026-08-31T00:00:00Z')")
    connection.execute("INSERT INTO commits (id, branch_id, revision, patch_id, audit_id, committed_at) VALUES ('commit-ref', 'branch-1', 0, 'patch-ref', 'audit-ref', '2026-08-31T00:00:00Z')")
    yield connection
    connection.close()

def test_patch_rechazado_no_bloquea_nueva_propuesta(conn):
    # Two patches with same hash
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-1', 'branch-1', 1, 'REJECTED', 'hashX', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-2', 'branch-1', 1, 'PROPOSED', 'hashX', '2026-08-31T00:00:00Z')")
    assert conn.execute("SELECT count(*) FROM patches WHERE patch_hash = 'hashX'").fetchone()[0] == 2

def test_replay_fails(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-1', 'branch-1', 1, 'COMMITTED', 'hash1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, decision, policy_snapshot_id, audited_at) VALUES ('audit-1', 'patch-1', 'ACCEPT', 'policy-1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, audit_id, committed_at) VALUES ('commit-1', 'branch-1', 1, 'patch-1', 'audit-1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO audits (id, patch_id, decision, policy_snapshot_id, audited_at) VALUES ('audit-2', 'patch-1', 'ACCEPT', 'policy-1', '2026-08-31T00:00:00Z')")
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, audit_id, committed_at) VALUES ('commit-2', 'branch-1', 2, 'patch-1', 'audit-2', '2026-08-31T00:00:00Z')")

def test_personal_inline_fails(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
            INSERT INTO memory_records (id, domain, semantic_key, status, storage_class, inline_value, created_by_commit_id, created_at) 
            VALUES ('record-1', 'PERSONAL', 'key1', 'ACTIVE', 'INLINE_NON_SENSITIVE', 'value', 'commit-ref', '2026-08-31T00:00:00Z')
        """)

def test_purged_tombstone(conn):
    conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, created_at) VALUES ('payload-1', 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', '2026-08-31T00:00:00Z')")
    conn.execute("""
        INSERT INTO memory_records (id, domain, semantic_key, status, storage_class, payload_id, created_by_commit_id, created_at) 
        VALUES ('record-1', 'PERSONAL', 'key1', 'PURGED', 'VAULT_REF', 'payload-1', 'commit-ref', '2026-08-31T00:00:00Z')
    """)
    row = conn.execute("SELECT inline_value, payload_id FROM memory_records WHERE id = 'record-1'").fetchone()
    assert row['inline_value'] is None
    assert row['payload_id'] == 'payload-1'

def test_destroyed_payload(conn):
    conn.execute("INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, ciphertext_location, created_at) VALUES ('payload-1', 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', NULL, NULL, '2026-08-31T00:00:00Z')")
    row = conn.execute("SELECT status, key_handle, ciphertext_location FROM payload_objects WHERE id = 'payload-1'").fetchone()
    assert row['status'] == 'DESTROYED'
    assert row['key_handle'] is None
    assert row['ciphertext_location'] is None

def test_active_key_uniqueness(conn):
    conn.execute("""
        INSERT INTO memory_records (id, domain, semantic_key, status, storage_class, branch_id, created_by_commit_id, created_at) 
        VALUES ('record-1', 'OPERATIONAL', 'key1', 'ACTIVE', 'NONE', 'branch-1', 'commit-ref', '2026-08-31T00:00:00Z')
    """)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
            INSERT INTO memory_records (id, domain, semantic_key, status, storage_class, branch_id, created_by_commit_id, created_at) 
            VALUES ('record-2', 'OPERATIONAL', 'key1', 'ACTIVE', 'NONE', 'branch-1', 'commit-ref', '2026-08-31T00:00:00Z')
        """)

def test_revisions(conn):
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-1', 'branch-1', 1, 'COMMITTED', 'hash1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, decision, policy_snapshot_id, audited_at) VALUES ('audit-1', 'patch-1', 'ACCEPT', 'policy-1', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, audit_id, committed_at) VALUES ('commit-1', 'branch-1', 1, 'patch-1', 'audit-1', '2026-08-31T00:00:00Z')")
    
    conn.execute("INSERT INTO patches (id, branch_id, base_revision, status, patch_hash, proposed_at) VALUES ('patch-2', 'branch-1', 1, 'COMMITTED', 'hash2', '2026-08-31T00:00:00Z')")
    conn.execute("INSERT INTO audits (id, patch_id, decision, policy_snapshot_id, audited_at) VALUES ('audit-2', 'patch-2', 'ACCEPT', 'policy-1', '2026-08-31T00:00:00Z')")
    
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO commits (id, branch_id, revision, patch_id, audit_id, committed_at) VALUES ('commit-2', 'branch-1', 1, 'patch-2', 'audit-2', '2026-08-31T00:00:00Z')")
