"""C3-01 — Schema Contract Tests: direct SQL attacks on the SQLite storage.

These tests bypass repositories entirely and attempt to INSERT structurally
invalid states straight into the schema. A STRICT SQLite layer MUST reject
them (IntegrityError / CHECK / UNIQUE). If SQLite currently ACCEPTS one, the
test fails — that failure is deliberate evidence of a Pydantic↔SQLite parity
mismatch to be recorded in the Schema Parity Matrix (C3-03), not to be
silently disabled.

The supervisor's rule is uppermost: "test fails because architecture is strict"
is preferred over "test passes because implementation is permissive".
"""

from __future__ import annotations

import sqlite3

import pytest


def expect_reject(conn, sql: str, params: tuple) -> None:
    """Assert the schema rejects `sql`; fail (loudly) if it accepts it."""
    try:
        conn.execute(sql, params)
        conn.commit()
    except sqlite3.IntegrityError:
        return  # strict schema — correct
    # SQLite accepted an invalid state: parity break / permissive storage.
    raise AssertionError(
        f"SCHEMA PARITY MISMATCH: SQLite ACCEPTED an invalid state that must be rejected.\n"
        f"  SQL: {sql}\n"
        f"  params: {params}"
    )


# ---------------------------------------------------------------------------
# Enum CHECK constraints (C2-05). Raw statuses outside the spec must fail.
# ---------------------------------------------------------------------------

def test_patch_status_garbage_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES (?, 'branch-1', 0, 0, 'policy-1', 'GARBAGE', 'h', 'm', 'p', '2026-08-31T00:00:00Z')",
        ("patch-bad-status",),
    )


def test_audit_decision_maybe_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        "VALUES (?, 'patch-ref', 'h', 'branch-1', 0, 0, 'policy-1', 'b', 'MAYBE', '', 'm', 'p', '2026-08-31T00:00:00Z')",
        ("audit-bad-decision",),
    )


def test_payload_status_garbage_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, 'MEMORY_VALUE', 'WHATEVER', 'PERSONAL', 'kh', 'loc', '2026-08-31T00:00:00Z')",
        ("payload-bad-status",),
    )


def test_lease_status_garbage_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO access_leases (id, record_id, requested_scope, active_branch_id, "
        "policy_snapshot_id, status, issued_at, expires_at, revoked_at) "
        "VALUES (?, 'rec-nonexistent', 'scope', 'branch-1', 'policy-1', 'WHATEVER', "
        "'2026-08-31T00:00:00Z', '2026-08-31T00:01:00Z', NULL)",
        ("lease-bad-status",),
    )


# ---------------------------------------------------------------------------
# Storage constraints (C2-06) — direct attacks
# ---------------------------------------------------------------------------

def test_personal_memory_inline_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'PERSONAL', 'branch-1', 'k', 'PERSONAL_FACT', 'ACTIVE', 'PERSONAL', "
        "'INLINE_NON_SENSITIVE', 'secret', NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')",
        ("rec-personal-inline",),
    )


def test_personal_memory_non_vault_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'PERSONAL', 'branch-1', 'k2', 'PERSONAL_FACT', 'ACTIVE', 'PERSONAL', "
        "'NONE', NULL, NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')",
        ("rec-personal-none",),
    )


def test_active_payload_without_key_handle_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, 'MEMORY_VALUE', 'ACTIVE', 'PERSONAL', NULL, NULL, '2026-08-31T00:00:00Z')",
        ("payload-active-nokey",),
    )


def test_destroyed_payload_with_key_handle_rejected(conn):
    expect_reject(
        conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at, destroyed_at) "
        "VALUES (?, 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', 'kh-still', 'loc-still', "
        "'2026-08-31T00:00:00Z', '2026-08-31T00:00:00Z')",
        ("payload-destroyed-key",),
    )


# ---------------------------------------------------------------------------
# Uniqueness invariants
# ---------------------------------------------------------------------------

def test_two_active_operational_same_scope_rejected(conn):
    def _insert(rid):
        conn.execute(
            "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
            "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
            "created_by_commit_id, created_at) "
            "VALUES (?, 'OPERATIONAL', 'branch-1', 'same-key', 'DECISION', 'ACTIVE', 'ORDINARY', "
            "'INLINE_NON_SENSITIVE', 'v', NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')",
            (rid,),
        )

    _insert("rec-op-1")
    conn.commit()
    # second ACTIVE record on same (branch, semantic_key) must be rejected
    expect_reject(conn, *_make_second())
    # (explicit helper below keeps the raw statement visible)


def _make_second():
    sql = (
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'OPERATIONAL', 'branch-1', 'same-key', 'DECISION', 'ACTIVE', 'ORDINARY', "
        "'INLINE_NON_SENSITIVE', 'v', NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')"
    )
    return (sql, ("rec-op-2",))


def test_same_branch_revision_twice_rejected(conn):
    # create valid patch+audit, then attempt a second commit with same revision
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-rev2', 'branch-1', 1, 0, 'policy-1', 'PROPOSED', 'hR2', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        "VALUES ('audit-rev2', 'patch-rev2', 'hR2', 'branch-1', 1, 0, 'policy-1', 'b', 'ACCEPT', "
        "'', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.commit()
    expect_reject(
        conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-dup-rev', 'branch-1', 0, NULL, 'patch-rev2', 'hR2', 'audit-rev2', 0, 'policy-1', '2026-08-31T00:00:00Z')",
        (),
    )


# ---------------------------------------------------------------------------
# C3-02 — Patch hash regression: hash must NOT be unique; idempotency lives
# in commits.patch_id UNIQUE.
# ---------------------------------------------------------------------------

def test_patch_hash_not_unique_allows_two_patches(conn):
    """The SAME hash X may coexist as AUDIT_REJECTED (A) and PROPOSED (B)."""
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-a', 'branch-1', 1, 0, 'policy-1', 'AUDIT_REJECTED', 'hashX', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-b', 'branch-1', 1, 0, 'policy-1', 'PROPOSED', 'hashX', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.commit()
    rows = conn.execute(
        "SELECT patch_hash, status FROM patches WHERE patch_hash='hashX' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2, "same hash must be allowed on two distinct patches"
    assert {r["status"] for r in rows} == {"AUDIT_REJECTED", "PROPOSED"}


def test_same_patch_id_committed_twice_rejected(conn):
    """Idempotency: commits.patch_id is UNIQUE — a patch cannot commit twice."""
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-rep', 'branch-1', 1, 0, 'policy-1', 'PROPOSED', 'hashR', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        "VALUES ('audit-rep', 'patch-rep', 'hashR', 'branch-1', 1, 0, 'policy-1', 'b', 'ACCEPT', "
        "'', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-rep', 'branch-1', 1, 'commit-ref', 'patch-rep', 'hashR', 'audit-rep', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )
    conn.commit()
    expect_reject(
        conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-rep2', 'branch-1', 2, NULL, 'patch-rep', 'hashR', ?, 0, 'policy-1', '2026-08-31T00:00:00Z')",
        ("audit-rep2",),
    )

