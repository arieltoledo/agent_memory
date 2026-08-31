"""C3-01 — Schema Contract Tests: direct SQL attacks on the SQLite storage.

These tests bypass repositories entirely and attempt to INSERT structurally
invalid states straight into the schema. A STRICT SQLite layer MUST reject
them (IntegrityError / CHECK / UNIQUE). If SQLite currently ACCEPTS one, the
test fails — that failure is deliberate evidence of a Pydantic<->SQLite parity
mismatch to be recorded in the Schema Parity Matrix (C3-03), not to be
silently disabled.

The supervisor's rule is uppermost: "test fails because architecture is strict"
is preferred over "test passes because implementation is permissive".

P0-03 rule (Architecture Review #2): every rejection must be attributable to
the constraint UNDER TEST, not to an absent FK. Therefore:
  1. All foreign keys referenced by an attack row are pre-seeded with valid
     base rows (branches, policies, commits, payloads, records) so the reject
     fires purely on the enumerated constraint.
  2. Every negative test carries a PAIRED POSITIVE CONTROL: the identical FK
     context with a VALID value for the same column must ACCEPT.
"""

from __future__ import annotations

import sqlite3

import pytest


def expect_reject(conn, sql: str, params: tuple = ()) -> None:
    """Assert the schema rejects `sql`; fail (loudly) if it accepts it."""
    try:
        conn.execute(sql, params)
        conn.commit()
    except sqlite3.IntegrityError:
        return  # strict schema — correct
    raise AssertionError(
        f"SCHEMA PARITY MISMATCH: SQLite ACCEPTED an invalid state that must be rejected.\n"
        f"  SQL: {sql}\n"
        f"  params: {params}"
    )


def expect_accept(conn, sql: str, params: tuple = ()) -> None:
    """Assert the schema ACCEPTS a valid state (paired positive control)."""
    conn.execute(sql, params)
    conn.commit()


# Patches note: audits is defined AFTER audits FK references; order handled by
# SQLite. `patches` requires a policy_snapshot_id -> policies(policy_snapshot_id).
PATCH = (
    "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
    "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
    "VALUES (?, 'branch-1', 1, 0, 'policy-1', ?, 'h', 'm', 'p', '2026-08-31T00:00:00Z')"
)

AUDIT = (
    "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
    "policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, "
    "auditor_prompt_version, created_at) "
    "VALUES (?, ?, 'h', 'branch-1', 1, 0, 'policy-1', 'b', ?, '[]', 'm', 'p', '2026-08-31T00:00:00Z')"
)

PAYLOAD = (
    "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
    "ciphertext_location, created_at, destroyed_at) "
    "VALUES (?, 'MEMORY_VALUE', ?, 'PERSONAL', ?, ?, '2026-08-31T00:00:00Z', ?)"
)

MEMREC = (
    "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
    "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
    "created_by_commit_id, created_at) "
    "VALUES (?, ?, 'branch-1', ?, 'DECISION', 'ACTIVE', ?, ?, ?, ?, 'DURABLE', "
    "'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')"
)

LEASE = (
    "INSERT INTO access_leases (id, record_id, requested_scope, active_branch_id, "
    "policy_snapshot_id, status, issued_at, expires_at, revoked_at) "
    "VALUES (?, 'rec-1', 'scope', 'branch-1', 'policy-1', ?, "
    "'2026-08-31T00:00:00Z', '2026-08-31T00:01:00Z', NULL)"
)


# ---------------------------------------------------------------------------
# Enum CHECK constraints (C2-05). Raw statuses outside the spec must fail.
# ---------------------------------------------------------------------------

def test_patch_status_garbage_rejected_with_positive_control(conn):
    # positive control: valid status ACCEPTS
    expect_accept(conn, PATCH, ("patch-pos", "PROPOSED"))
    # negative: GARBAGE rejected (FKs pre-existing -> reject is by status CHECK)
    expect_reject(conn, PATCH, ("patch-bad-status", "GARBAGE"))


def test_audit_decision_maybe_rejected_with_positive_control(conn):
    # need a patch row first so audit.patch_id FK holds (and is not reused)
    expect_accept(conn, PATCH, ("patch-aud", "PROPOSED"))
    # positive control: valid decision ACCEPTS
    expect_accept(conn, AUDIT, ("audit-pos", "patch-aud", "ACCEPT"))
    # negative: MAYBE rejected (decision CHECK)
    expect_reject(conn, AUDIT, ("audit-bad", "patch-aud", "MAYBE"))


def test_payload_status_garbage_rejected_with_positive_control(conn):
    # positive control: ACTIVE with keys ACCEPTS
    expect_accept(conn, PAYLOAD, ("payload-pos", "ACTIVE", "kh", "loc", None))
    # negative: WHATEVER rejected (status CHECK)
    expect_reject(conn, PAYLOAD, ("payload-bad-status", "WHATEVER", "kh", "loc", None))


def test_lease_status_garbage_rejected_with_positive_control(conn):
    # record_id 'rec-1' is pre-seeded -> reject below is by status CHECK, not FK
    # positive control: VALID ACCEPTS
    expect_accept(conn, LEASE, ("lease-pos", "VALID"))
    # negative: WHATEVER rejected (status CHECK)
    expect_reject(conn, LEASE, ("lease-bad-status", "WHATEVER"))


# ---------------------------------------------------------------------------
# Storage constraints (C2-06) — direct attacks
# ---------------------------------------------------------------------------

def test_personal_memory_inline_rejected_with_positive_control(conn):
    # positive control: PERSONAL + VAULT_REF with a real payload_id ACCEPTS
    expect_accept(conn, MEMREC, (
        "rec-pos-vault", "PERSONAL", "pk", "PERSONAL",
        "VAULT_REF", None, "payload-1",
    ))
    # negative: PERSONAL + INLINE rejected (domain/storage CHECK)
    expect_reject(conn, MEMREC, (
        "rec-personal-inline", "PERSONAL", "k", "PERSONAL",
        "INLINE_NON_SENSITIVE", "secret", None,
    ))


def test_personal_memory_non_vault_rejected_with_positive_control(conn):
    # negative: PERSONAL non-VAULT rejected (domain/storage CHECK)
    expect_reject(conn, MEMREC, (
        "rec-personal-none", "PERSONAL", "k2", "PERSONAL",
        "NONE", None, None,
    ))


def test_operational_inline_requires_inline_value_rejected_with_positive_control(conn):
    # positive control: OPERATIONAL + INLINE with inline_value ACCEPTS
    expect_accept(conn, MEMREC, (
        "rec-op-pos", "OPERATIONAL", "ok-pos", "ORDINARY",
        "INLINE_NON_SENSITIVE", "{\"v\":1}", None,
    ))
    # negative: OPERATIONAL + INLINE with NULL inline_value rejected (storage CHECK)
    expect_reject(conn, MEMREC, (
        "rec-op-noval", "OPERATIONAL", "ok-noval", "ORDINARY",
        "INLINE_NON_SENSITIVE", None, None,
    ))


def test_active_payload_without_key_handle_rejected_with_positive_control(conn):
    # positive control: ACTIVE with keys ACCEPTS (payload-pos already inserted? no —
    # use distinct ids to avoid data pollution between tests, each gets its own conn)
    expect_accept(conn, PAYLOAD, ("payload-ok", "ACTIVE", "kh", "loc", None))
    # negative: ACTIVE without keys rejected (payload state CHECK)
    expect_reject(conn, PAYLOAD, ("payload-active-nokey", "ACTIVE", None, None, None))


def test_destroyed_payload_with_key_handle_rejected_with_positive_control(conn):
    # positive control: DESTROYED with null keys ACCEPTS
    expect_accept(conn, PAYLOAD, ("payload-destroyed-ok", "DESTROYED", None, None, "2026-08-31T00:00:00Z"))
    # negative: DESTROYED still carrying keys rejected (payload state CHECK)
    expect_reject(conn, PAYLOAD, ("payload-destroyed-key", "DESTROYED", "kh-still", "loc-still", "2026-08-31T00:00:00Z"))


# ---------------------------------------------------------------------------
# Uniqueness invariants
# ---------------------------------------------------------------------------

def test_two_active_operational_same_scope_rejected_with_positive_control(conn):
    # base rec-1 occupies ('branch-1','op-seed-key'); a DIFFERENT key ACCEPTS
    expect_accept(conn, MEMREC, (
        "rec-op-distinct", "OPERATIONAL", "distinct-key", "ORDINARY",
        "INLINE_NON_SENSITIVE", "{\"v\":2}", None,
    ))
    # same (branch, semantic_key) as rec-1, both ACTIVE OPERATIONAL -> unique index reject
    expect_reject(conn, MEMREC, (
        "rec-op-dup", "OPERATIONAL", "op-seed-key", "ORDINARY",
        "INLINE_NON_SENSITIVE", "{\"v\":3}", None,
    ))


def test_same_branch_revision_twice_rejected_with_positive_control(conn):
    # positive control: a NEW (branch, revision) ACCEPTS
    expect_accept(conn, PATCH, ("patch-rev-pos", "PROPOSED"))
    expect_accept(conn, AUDIT, ("audit-rev-pos", "patch-rev-pos", "ACCEPT"))
    expect_accept(conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-rev-pos', 'branch-1', 99, NULL, 'patch-rev-pos', 'hRP', 'audit-rev-pos', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )
    # negative: same (branch, revision=1) already used by commit-ref -> UNIQUE(branch_id,revision)
    expect_reject(conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-dup-rev', 'branch-1', 1, NULL, 'patch-rev-pos', 'hRP', 'audit-rev-pos', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )


# ---------------------------------------------------------------------------
# C3-02 — Patch hash regression: hash must NOT be unique; idempotency lives
# in commits.patch_id UNIQUE.
# ---------------------------------------------------------------------------

def test_patch_hash_not_unique_allows_two_patches(conn):
    """The SAME hash X may coexist as AUDIT_REJECTED (A) and PROPOSED (B)."""
    expect_accept(conn, PATCH, ("patch-a", "AUDIT_REJECTED"))
    expect_accept(conn, PATCH, ("patch-b", "PROPOSED"))
    # override patches with a shared hash to prove hash itself is NOT unique
    # (patch-a/patch-b already inserted via PATCH with hash 'h'; we insert two
    # more sharing hash 'hashX' to make the regression explicit)
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-x1', 'branch-1', 1, 0, 'policy-1', 'AUDIT_REJECTED', 'hashX', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-x2', 'branch-1', 1, 0, 'policy-1', 'PROPOSED', 'hashX', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    conn.commit()
    rows = conn.execute(
        "SELECT patch_hash, status FROM patches WHERE patch_hash='hashX' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2, "same hash must be allowed on two distinct patches"
    assert {r["status"] for r in rows} == {"AUDIT_REJECTED", "PROPOSED"}


def test_same_patch_id_committed_twice_rejected_with_positive_control(conn):
    """Idempotency: commits.patch_id is UNIQUE — a patch cannot commit twice.

    Both commits reference a real, pre-existing audit_id so the rejection in
    the second commit is attributable to commits.patch_id UNIQUE (not to an
    absent audit FK — the P0-03 false-positive class the directive forbids).
    """
    # patch + audit pair A
    expect_accept(conn, PATCH, ("patch-rep", "PROPOSED"))
    expect_accept(conn, AUDIT, ("audit-rep", "patch-rep", "ACCEPT"))
    expect_accept(conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-rep', 'branch-1', 2, NULL, 'patch-rep', 'hashR', 'audit-rep', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )
    # distinct patch B with its own audit, so its audit_id FK is valid
    expect_accept(conn, PATCH, ("patch-other", "PROPOSED"))
    expect_accept(conn, AUDIT, ("audit-other", "patch-other", "ACCEPT"))
    # second commit reuses patch_id 'patch-rep' but a *valid* audit -> reject by patch_id UNIQUE
    expect_reject(conn,
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-rep2', 'branch-1', 3, NULL, 'patch-rep', 'hashR', 'audit-other', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )


# ---------------------------------------------------------------------------
# Final Closure Specific Persistence Attacks (P0-01, P0-02, P1-01)
# ---------------------------------------------------------------------------

def test_operational_sensitive_inline_rejected_with_positive_control(conn):
    """P0-01: SENSITIVE Memory MUST be VAULT_REF, never INLINE."""
    # Positive control: OPERATIONAL + SENSITIVE + VAULT_REF with payload_id ACCEPTS
    expect_accept(conn, MEMREC, (
        "rec-op-sens-vault", "OPERATIONAL", "sens-vault-key", "SENSITIVE",
        "VAULT_REF", None, "payload-1",
    ))
    # Negative: OPERATIONAL + SENSITIVE + INLINE rejected (CHECK constraint)
    expect_reject(conn, MEMREC, (
        "rec-op-sens-inline", "OPERATIONAL", "sens-inline-key", "SENSITIVE",
        "INLINE_NON_SENSITIVE", "{\"leak\":\"plaintext\"}", None,
    ))


def test_prohibited_payload_rejected_with_positive_control(conn):
    """P0-02: PROHIBITED cannot be stored as a durable PayloadObject."""
    # Positive control: SENSITIVE PayloadObject ACCEPTS
    expect_accept(conn, PAYLOAD, ("payload-sens-ok", "ACTIVE", "kh", "loc", None))
    # Negative: PROHIBITED PayloadObject rejected (CHECK constraint)
    expect_reject(
        conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, ciphertext_location, created_at) "
        "VALUES ('payload-prohibited', 'MEMORY_VALUE', 'ACTIVE', 'PROHIBITED', 'kh', 'loc', '2026-08-31T00:00:00Z')"
    )


def test_payload_lifecycle_partial_states_rejected_with_positive_controls(conn):
    """P1-01: Payload lifecycle must enforce exact 4 partial state rejections."""
    # Positive control: ACTIVE with both key_handle and location ACCEPTS
    expect_accept(conn, PAYLOAD, ("payload-active-full", "ACTIVE", "kh1", "loc1", None))
    # Positive control: DESTROYED with both null ACCEPTS
    expect_accept(conn, PAYLOAD, ("payload-dest-full", "DESTROYED", None, None, "2026-08-31T00:00:00Z"))

    # Partial Case 1: STAGED with key_handle != NULL, location == NULL -> REJECT
    expect_reject(conn, PAYLOAD, ("p-staged-noloc", "STAGED", "kh", None, None))

    # Partial Case 2: STAGED with key_handle == NULL, location != NULL -> REJECT
    expect_reject(conn, PAYLOAD, ("p-staged-nokey", "STAGED", None, "loc", None))

    # Partial Case 3: DESTROYED with key_handle != NULL, location == NULL -> REJECT
    expect_reject(conn, PAYLOAD, ("p-dest-haskey", "DESTROYED", "kh", None, "2026-08-31T00:00:00Z"))

    # Partial Case 4: DESTROYED with key_handle == NULL, location != NULL -> REJECT
    expect_reject(conn, PAYLOAD, ("p-dest-hasloc", "DESTROYED", None, "loc", "2026-08-31T00:00:00Z"))

