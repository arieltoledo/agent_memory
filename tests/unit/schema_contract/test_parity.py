"""C3-03 — Pydantic <-> SQLite schema parity.

For each structural invariant, we drive BOTH the Pydantic domain model and the
raw SQLite storage with the same shape and assert they AGREE (both REJECT or
both ACCEPT). A disagreement (Pydantic REJECT / SQLite ACCEPT, or vice versa)
fires this suite as FAIL and must be recorded in the Schema Parity Matrix.

This automates the parity check the spec owner asked for, so a mismatch is
detected as a real, falsifiable test — not a hand-written observation table.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError, UUID4

from memory_agent.domain.enums import *
from memory_agent.domain.models import (
    PayloadObject, MemoryRecord, EvidenceRecord, ValueReference,
)
from memory_agent.domain.errors import DomainValidationError
from memory_agent.repository.sqlite import get_connection, apply_migrations
from tests.unit.schema_contract.conftest import _seed_base, MIGRATIONS

import uuid
from datetime import datetime, timezone

NOW = "2026-08-31T00:00:00Z"
NOW_DT = datetime(2026, 8, 31, tzinfo=timezone.utc)


def _u():
    return str(uuid.uuid4())


def _sql(name, conn, c):
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers: probe a case through Pydantic and through SQLite; return booleans.
# ---------------------------------------------------------------------------

def _pyd_rejects(builder) -> bool:
    """True if Pydantic rejects the shape described by `builder`."""
    try:
        builder()
        return False
    except (ValidationError, DomainValidationError):
        return True


def _sql_rejects(conn, sql: str, params: tuple) -> bool:
    try:
        conn.execute(sql, params)
        conn.commit()
        return False
    except Exception:
        conn.rollback()
        return True


def _assert_parity(name: str, conn, pyd: bool, sql: bool) -> None:
    if pyd != sql:
        raise AssertionError(
            f"SCHEMA PARITY BREAK [{name}]: Pydantic={'REJECT' if pyd else 'ACCEPT'}, "
            f"SQLite={'REJECT' if sql else 'ACCEPT'}. Must agree."
        )


# ---------------------------------------------------------------------------
# Personal memory -> VAULT_REF (never inline)
# ---------------------------------------------------------------------------

def _mk_record(storage_class, domain=MemoryDomain.PERSONAL, payload_ref=None,
               inline=None, status=RecordStatus.ACTIVE):
    return MemoryRecord(
        record_id=_u(), domain=domain, branch_id=None, semantic_key="k",
        kind=SemanticType.PERSONAL_FACT, status=status,
        sensitivity=Sensitivity.PERSONAL, storage_class=storage_class,
        inline_value=inline, payload_ref=payload_ref,
        lifetime=Lifetime.DURABLE, valid_until=None, timezone=None,
        policy_snapshot_id=_u(), mount_policy_id=None,
        created_commit_id=_u(), supersedes_record_id=None, created_at=NOW_DT,
        purged_at=None,
    )


def test_parity_personal_inline(conn):
    pyd = _pyd_rejects(lambda: _mk_record(
        ValueStorageClass.INLINE_NON_SENSITIVE, inline="secret"))
    sql = _sql_rejects(conn,
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'PERSONAL', NULL, 'k', 'PERSONAL_FACT', 'ACTIVE', 'PERSONAL', "
        "'INLINE_NON_SENSITIVE', 'secret', NULL, 'DURABLE', 'policy-1', 'commit-ref', ?)",
        (_u(), NOW))
    _assert_parity("Personal+INLINE", conn, pyd, sql)


def test_parity_personal_vault_ok(conn):
    # load a valid vault payload first so FK holds for the ACCEPT case
    conn.execute(
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) VALUES (?, 'MEMORY_VALUE', 'ACTIVE', 'PERSONAL', "
        "'kh', 'loc', ?)", (_u(), NOW))
    conn.commit()
    puid = _u()
    pyd = _pyd_rejects(lambda: _mk_record(
        ValueStorageClass.VAULT_REF, payload_ref=uuid.UUID(puid)))
    sql = _sql_rejects(conn,
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'PERSONAL', NULL, 'k', 'PERSONAL_FACT', 'ACTIVE', 'PERSONAL', "
        "'VAULT_REF', NULL, ?, 'DURABLE', 'policy-1', 'commit-ref', ?)",
        (_u(), puid, NOW))
    _assert_parity("Personal+VAULT valid", conn, pyd, sql)


# ---------------------------------------------------------------------------
# PayloadObject lifecycle: DESTROYED must clear key+location
# ---------------------------------------------------------------------------

def _mk_payload(status, key_handle=None, loc=None):
    return PayloadObject(
        payload_id=_u(), purpose="MEMORY_VALUE", status=status,
        sensitivity=Sensitivity.PERSONAL, key_handle=key_handle,
        ciphertext_location=loc, created_at=NOW_DT,
        activated_at=None, destroyed_at=NOW_DT if status in (
            PayloadStatus.DESTROYED, PayloadStatus.ABORTED) else None,
    )


def test_parity_destroyed_payload_clears_keys(conn):
    pyd_reject_kept = _pyd_rejects(lambda: _mk_payload(
        PayloadStatus.DESTROYED, key_handle="kh", loc="loc"))
    sql_reject_kept = _sql_rejects(conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at, destroyed_at) "
        "VALUES (?, 'MEMORY_VALUE', 'DESTROYED', 'PERSONAL', 'kh', 'loc', ?, ?)",
        (_u(), NOW, NOW))
    _assert_parity("DESTROYED keeps keys", conn, pyd_reject_kept, sql_reject_kept)


def test_parity_active_payload_requires_keys(conn):
    pyd_reject_missing = _pyd_rejects(lambda: _mk_payload(
        PayloadStatus.ACTIVE))
    sql_reject_missing = _sql_rejects(conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, 'MEMORY_VALUE', 'ACTIVE', 'PERSONAL', NULL, NULL, ?)",
        (_u(), NOW))
    _assert_parity("ACTIVE w/o keys", conn, pyd_reject_missing, sql_reject_missing)


# ---------------------------------------------------------------------------
# EvidenceRecord: scope_type BRANCH requires branch_id; PROHIBITED impossible
# ---------------------------------------------------------------------------

def _mk_evidence(scope_type, branch_id, storage_class, inline=None, payload_ref=None,
                 sensitivity=Sensitivity.ORDINARY):
    return EvidenceRecord(
        evidence_id=_u(), scope_type=scope_type, branch_id=branch_id,
        source_kind="MSG", status=EvidenceStatus.ACTIVE, sensitivity=sensitivity,
        storage_class=storage_class, inline_sanitized_text=inline,
        payload_ref=payload_ref, sanitization_applied=True,
        removed_categories=(), policy_snapshot_id=_u(), created_at=NOW_DT,
    )


def test_parity_evidence_branch_requires_branch_id(conn):
    pyd = _pyd_rejects(lambda: _mk_evidence(
        "BRANCH", None, ValueStorageClass.INLINE_NON_SENSITIVE, inline="x"))
    sql = _sql_rejects(conn,
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories, policy_snapshot_id, created_at) "
        "VALUES (?, 'BRANCH', NULL, 'MSG', 'ACTIVE', 'ORDINARY', 'INLINE_NON_SENSITIVE', "
        "'x', NULL, 1, '[]', 'policy-1', ?)",
        (_u(), NOW))
    _assert_parity("Evidence BRANCH w/o branch_id", conn, pyd, sql)


def test_parity_evidence_prohibited_impossible(conn):
    pyd = _pyd_rejects(lambda: _mk_evidence(
        "GLOBAL", None, ValueStorageClass.NONE, sensitivity=Sensitivity.PROHIBITED))
    sql = _sql_rejects(conn,
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories, policy_snapshot_id, created_at) "
        "VALUES (?, 'GLOBAL', NULL, 'MSG', 'ACTIVE', 'PROHIBITED', "
        "'NONE', NULL, NULL, 1, '[]', 'policy-1', ?)",
        (_u(), NOW))
    _assert_parity("Evidence PROHIBITED", conn, pyd, sql)


# ---------------------------------------------------------------------------
# KNOWN PARITY GAP (C3-03 finding, Pydantic ACCEPT / SQLite REJECT):
# MemoryRecord generic storage-shape is enforced in SQLite (INLINE requires
# inline_value, VAULT requires payload_ref) but MemoryRecord._memory_storage
# only checks PERSONAL->VAULT and PROHIBITED. Coder 1 must tighten per C1-04.
# ---------------------------------------------------------------------------

def _mk_generic_memory_record(storage_class, inline=None, payload_ref=None):
    return MemoryRecord(
        record_id=uuid.UUID(_u()), domain=MemoryDomain.OPERATIONAL, branch_id=None,
        semantic_key="k", kind=SemanticType.OTHER, status=RecordStatus.ACTIVE,
        sensitivity=Sensitivity.ORDINARY, storage_class=storage_class,
        inline_value=inline, payload_ref=payload_ref,
        lifetime=Lifetime.DURABLE, valid_until=None, timezone=None,
        policy_snapshot_id=uuid.UUID(_u()), mount_policy_id=None,
        created_commit_id=uuid.UUID(_u()), supersedes_record_id=None,
        created_at=NOW_DT, purged_at=None,
    )


def test_parity_memrec_inline_requires_inline_value(conn):
    """Reported as a parity break: Pydantic permissive, SQLite strict.

    Pydantic MemoryRecord ACCEPTS OPERATIONAL+INLINE with inline_value=None;
    SQLite REJECTS it. Per C1-04, MemoryRecord must enforce the generic
    INLINE/VAULT/NONE shape. This test is currently FAILING on Pydantic and
    documents the gap so Coder 1 can close it and turn it green.
    """
    pyd = _pyd_rejects(lambda: _mk_generic_memory_record(
        ValueStorageClass.INLINE_NON_SENSITIVE, inline=None))
    sql = _sql_rejects(conn,
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, 'OPERATIONAL', 'branch-1', 'k', 'OTHER', 'ACTIVE', 'ORDINARY', "
        "'INLINE_NON_SENSITIVE', NULL, NULL, 'DURABLE', 'policy-1', 'commit-ref', ?)",
        (_u(), NOW))
    assert sql is True, "SQLite must reject INLINE with missing inline_value"
    assert pyd is True, (
        "PARITY BREAK (Pydantic ACCEPT / SQLite REJECT): MemoryRecord must enforce "
        "that INLINE_NON_SENSITIVE carries inline_value (C1-04)."
    )

