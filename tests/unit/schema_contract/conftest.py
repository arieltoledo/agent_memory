"""Pytest fixtures for C3-01 / C3-03 Schema Contract Tests.

These attack the SQLite schema directly with raw INSERT statements, bypassing
repositories, to prove the storage layer itself rejects structurally invalid
states (schema parity, not just application-level protection).

P0-03 rule (Architecture Review #2): every SQLite rejection under test must be
attributable to the CONSTRAINT under evaluation, not to an absent FK. Therefore
`_seed_base` pre-creates a minimal FK-consistent base (branches, policies,
commits, payloads, etc.) so that each attack only modifies the single column
being targeted.
"""

from __future__ import annotations

import pytest

from memory_agent.repository.sqlite import get_connection, apply_migrations

MIGRATIONS = "memory_agent/repository/migrations/0001_initial.sql"


@pytest.fixture
def conn():
    connection = get_connection()
    apply_migrations(connection, MIGRATIONS)
    _seed_base(connection)
    yield connection
    connection.close()


def _seed_base(c):
    c.execute(
        "INSERT INTO core_snapshots (core_version, content_json, content_hash, created_at) "
        "VALUES (0, '{}', 'core-hash-0', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO branches (branch_id, name, status, current_revision, core_version, created_at) "
        "VALUES ('branch-1', 'main', 'ACTIVE', 0, 0, '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO policies (policy_snapshot_id, policy_version, policy_hash, source_ref, active, created_at) "
        "VALUES ('policy-1', 1, 'hash', 'spec://v0.3.0', 1, '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES ('payload-1', 'MEMORY_VALUE', 'ACTIVE', 'PERSONAL', 'kh-1', 'loc-1', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, removed_categories, "
        "policy_snapshot_id, created_at) "
        "VALUES ('ev-1', 'BRANCH', 'branch-1', 'MSG', 'ACTIVE', 'ORDINARY', 'INLINE_NON_SENSITIVE', "
        "'sanitized', NULL, 1, '[]', 'policy-1', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-ref', 'branch-1', 0, 0, 'policy-1', 'COMMITTED', 'hash0', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        "VALUES ('audit-ref', 'patch-ref', 'hash0', 'branch-1', 0, 0, 'policy-1', 'b', 'ACCEPT', "
        "'[]', 'm', 'p', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-ref', 'branch-1', 0, NULL, 'patch-ref', 'hash0', 'audit-ref', 0, 'policy-1', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO mount_policies (mount_policy_id, version, mode, allowed_scopes_json, "
        "allow_sensitive_operational_mount, policy_hash, created_at) "
        "VALUES ('mp-1', 1, 'GLOBAL_INTERACTION_PREFERENCE', '[]', 0, 'mph', '2026-08-31T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES ('rec-1', 'OPERATIONAL', 'branch-1', 'op-seed-key', 'DECISION', 'ACTIVE', 'ORDINARY', "
        "'INLINE_NON_SENSITIVE', '{\"v\":1}', NULL, 'DURABLE', 'policy-1', 'commit-ref', '2026-08-31T00:00:00Z')"
    )
    c.commit()
