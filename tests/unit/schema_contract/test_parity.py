"""C3-03 — Pydantic <-> SQLite schema parity.

For each structural invariant, we drive BOTH the Pydantic domain model and the
raw SQLite storage with the SAME shape and assert they AGREE (both REJECT or
both ACCEPT). A disagreement (Pydantic REJECT / SQLite ACCEPT, or vice versa)
fires this suite as FAIL and must be recorded in the Schema Parity Matrix.

P0-03 rule (Architecture Review #2):
  1. Real `uuid.UUID` instances (never `str(uuid.uuid4())`) are used for every
     UUID-typed Pydantic field under `strict=True`, so a rejection is by the
     CONSTRAINT under test, not by Python type coercion.
  2. Every negative case has a PAIRED POSITIVE CONTROL: the identical fixture
     with a VALID value for the target column must ACCEPT on both sides. This
     proves the fixture is otherwise valid and the reject is attributable to
     the invariant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

from memory_agent.domain.enums import *
from memory_agent.domain.models import (
    PayloadObject, MemoryRecord, EvidenceRecord,
)
from memory_agent.domain.errors import DomainValidationError
from memory_agent.repository.sqlite import get_connection, apply_migrations
from tests.unit.schema_contract.conftest import _seed_base, MIGRATIONS

NOW = "2026-08-31T00:00:00Z"
NOW_DT = datetime(2026, 8, 31, tzinfo=timezone.utc)


def _pyd_accepts(builder) -> bool:
    """True if Pydantic ACCEPTS the shape described by `builder`."""
    try:
        builder()
        return True
    except (ValidationError, DomainValidationError):
        return False


def _sql_accepts(conn, sql: str, params: tuple) -> bool:
    try:
        conn.execute(sql, params)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def _assert_parity(name: str, conn, pyd_valid, sql_valid, pyd_invalid, sql_invalid) -> None:
    """Assert the positive control ACCEPTs and negative control REJECTs on BOTH sides."""
    if not pyd_valid:
        raise AssertionError(
            f"PARITY CONTROL FAILED [{name}]: positive Pydantic control should ACCEPT "
            f"but it was REJECTED by type/constraint not under test."
        )
    if not sql_valid:
        raise AssertionError(
            f"PARITY CONTROL FAILED [{name}]: positive SQLite control should ACCEPT "
            f"but it was REJECTED (check pre-seeded FKs)."
        )
    if pyd_invalid:
        raise AssertionError(
            f"PARITY BREAK [{name}]: Pydantic ACCEPTED the invalid state; both must REJECT."
        )
    if sql_invalid:
        raise AssertionError(
            f"PARITY BREAK [{name}]: SQLite ACCEPTED the invalid state; both must REJECT."
        )


# ---------------------------------------------------------------------------
# MemoryRecord — PERSONAL must be VAULT_REF; generic INLINE/VAULT/NONE shapes
# ---------------------------------------------------------------------------

def _mk_record(storage_class, domain=MemoryDomain.PERSONAL, payload_ref=None,
               inline=None, status=RecordStatus.ACTIVE,
               sensitivity=Sensitivity.PERSONAL):
    return MemoryRecord(
        record_id=uuid.uuid4(), domain=domain, branch_id=None, semantic_key="k",
        kind=SemanticType.PERSONAL_FACT, status=status,
        sensitivity=sensitivity, storage_class=storage_class,
        inline_value=inline, payload_ref=payload_ref,
        lifetime=Lifetime.DURABLE, valid_until=None, timezone=None,
        policy_snapshot_id=uuid.uuid4(), mount_policy_id=None,
        created_commit_id=uuid.uuid4(), supersedes_record_id=None, created_at=NOW_DT,
        purged_at=None,
    )


MEMREC_SQL = (
    "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
    "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
    "created_by_commit_id, created_at) "
    "VALUES (?, ?, NULL, 'k', 'PERSONAL_FACT', 'ACTIVE', ?, ?, ?, ?, 'DURABLE', "
    "'policy-1', 'commit-ref', ?)"
)


def test_parity_personal_inline(conn):
    _assert_parity(
        "Personal+INLINE",
        conn,
        # positive: PERSONAL + VAULT_REF (valid)
        _pyd_accepts(lambda: _mk_record(ValueStorageClass.VAULT_REF, payload_ref=uuid.uuid4())),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "PERSONAL", "PERSONAL",
            "VAULT_REF", None, "payload-1", NOW)),
        # negative: PERSONAL + INLINE (invalid)
        _pyd_accepts(lambda: _mk_record(ValueStorageClass.INLINE_NON_SENSITIVE, inline="secret")),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "PERSONAL", "PERSONAL",
            "INLINE_NON_SENSITIVE", "secret", None, NOW)),
    )


def test_parity_operational_inline_requires_inline_value(conn):
    _assert_parity(
        "OPERATIONAL+INLINE without inline_value",
        conn,
        # positive: OPERATIONAL + INLINE with inline_value
        _pyd_accepts(lambda: _mk_record(ValueStorageClass.INLINE_NON_SENSITIVE, inline="v",
                                        domain=MemoryDomain.OPERATIONAL,
                                        sensitivity=Sensitivity.ORDINARY)),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "OPERATIONAL", "ORDINARY",
            "INLINE_NON_SENSITIVE", "{\"v\":1}", None, NOW)),
        # negative: OPERATIONAL + INLINE with NULL inline_value
        _pyd_accepts(lambda: _mk_record(ValueStorageClass.INLINE_NON_SENSITIVE, inline=None,
                                        domain=MemoryDomain.OPERATIONAL,
                                        sensitivity=Sensitivity.ORDINARY)),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "OPERATIONAL", "ORDINARY",
            "INLINE_NON_SENSITIVE", None, None, NOW)),
    )


# ---------------------------------------------------------------------------
# PayloadObject lifecycle: DESTROYED must clear key+location
# ---------------------------------------------------------------------------

def _mk_payload(status, key_handle=None, loc=None):
    return PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=status,
        sensitivity=Sensitivity.PERSONAL, key_handle=key_handle,
        ciphertext_location=loc, created_at=NOW_DT,
        activated_at=None, destroyed_at=NOW_DT if status in (
            PayloadStatus.DESTROYED, PayloadStatus.ABORTED) else None,
    )


PAYLOAD_SQL = (
    "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
    "ciphertext_location, created_at, destroyed_at) "
    "VALUES (?, 'MEMORY_VALUE', ?, 'PERSONAL', ?, ?, ?, ?)"
)


def test_parity_destroyed_payload_clears_keys(conn):
    _assert_parity(
        "DESTROYED keeps keys",
        conn,
        # positive: DESTROYED with null keys
        _pyd_accepts(lambda: _mk_payload(PayloadStatus.DESTROYED)),
        _sql_accepts(conn, PAYLOAD_SQL, (
            uuid.uuid4().hex, "DESTROYED", None, None, NOW, NOW)),
        # negative: DESTROYED still carrying keys
        _pyd_accepts(lambda: _mk_payload(PayloadStatus.DESTROYED, key_handle="kh", loc="loc")),
        _sql_accepts(conn, PAYLOAD_SQL, (
            uuid.uuid4().hex, "DESTROYED", "kh", "loc", NOW, NOW)),
    )


def test_parity_active_payload_requires_keys(conn):
    _assert_parity(
        "ACTIVE w/o keys",
        conn,
        # positive: ACTIVE with keys
        _pyd_accepts(lambda: _mk_payload(PayloadStatus.ACTIVE, key_handle="kh", loc="loc")),
        _sql_accepts(conn, PAYLOAD_SQL, (
            uuid.uuid4().hex, "ACTIVE", "kh", "loc", NOW, None)),
        # negative: ACTIVE without keys
        _pyd_accepts(lambda: _mk_payload(PayloadStatus.ACTIVE)),
        _sql_accepts(conn, PAYLOAD_SQL, (
            uuid.uuid4().hex, "ACTIVE", None, None, NOW, None)),
    )


# ---------------------------------------------------------------------------
# EvidenceRecord: scope_type BRANCH requires branch_id; PROHIBITED impossible
# ---------------------------------------------------------------------------

def _mk_evidence(scope_type, branch_id, storage_class, inline=None, payload_ref=None,
                 sensitivity=Sensitivity.ORDINARY):
    return EvidenceRecord(
        evidence_id=uuid.uuid4(), scope_type=scope_type, branch_id=branch_id,
        source_kind="MSG", status=EvidenceStatus.ACTIVE, sensitivity=sensitivity,
        storage_class=storage_class, inline_sanitized_text=inline,
        payload_ref=payload_ref, sanitization_applied=True,
        removed_categories=(), policy_snapshot_id=uuid.uuid4(), created_at=NOW_DT,
    )


EVID_SQL = (
    "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
    "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
    "removed_categories_json, policy_snapshot_id, created_at) "
    "VALUES (?, ?, ?, 'MSG', 'ACTIVE', ?, ?, ?, ?, 1, '[]', 'policy-1', ?)"
)


def test_parity_evidence_branch_requires_branch_id(conn):
    _assert_parity(
        "Evidence BRANCH w/o branch_id",
        conn,
        # positive: BRANCH + branch_id
        _pyd_accepts(lambda: _mk_evidence(
            "BRANCH", uuid.uuid4(), ValueStorageClass.INLINE_NON_SENSITIVE, inline="x")),
        _sql_accepts(conn, EVID_SQL, (
            uuid.uuid4().hex, "BRANCH", "branch-1", "ORDINARY",
            "INLINE_NON_SENSITIVE", "x", None, NOW)),
        # negative: BRANCH with NULL branch_id
        _pyd_accepts(lambda: _mk_evidence(
            "BRANCH", None, ValueStorageClass.INLINE_NON_SENSITIVE, inline="x")),
        _sql_accepts(conn, EVID_SQL, (
            uuid.uuid4().hex, "BRANCH", None, "ORDINARY",
            "INLINE_NON_SENSITIVE", "x", None, NOW)),
    )


def test_parity_evidence_prohibited_impossible(conn):
    _assert_parity(
        "Evidence PROHIBITED",
        conn,
        # positive: ORDINARY sensitivity
        _pyd_accepts(lambda: _mk_evidence(
            "GLOBAL", None, ValueStorageClass.INLINE_NON_SENSITIVE, inline="ok", sensitivity=Sensitivity.ORDINARY)),
        _sql_accepts(conn, EVID_SQL, (
            uuid.uuid4().hex, "GLOBAL", None, "ORDINARY",
            "INLINE_NON_SENSITIVE", "ok", None, NOW)),
        # negative: PROHIBITED sensitivity
        _pyd_accepts(lambda: _mk_evidence(
            "GLOBAL", None, ValueStorageClass.INLINE_NON_SENSITIVE, inline="ok", sensitivity=Sensitivity.PROHIBITED)),
        _sql_accepts(conn, EVID_SQL, (
            uuid.uuid4().hex, "GLOBAL", None, "PROHIBITED",
            "INLINE_NON_SENSITIVE", "ok", None, NOW)),
    )


# ---------------------------------------------------------------------------
# Final Closure Specific Parity Tests (P0-01, P0-02, P1-01)
# ---------------------------------------------------------------------------

def test_parity_operational_sensitive_never_inline(conn):
    """P0-01: OPERATIONAL + SENSITIVE must be VAULT_REF, never INLINE."""
    _assert_parity(
        "OPERATIONAL+SENSITIVE+INLINE",
        conn,
        # positive: OPERATIONAL + SENSITIVE + VAULT_REF
        _pyd_accepts(lambda: _mk_record(
            ValueStorageClass.VAULT_REF,
            domain=MemoryDomain.OPERATIONAL,
            sensitivity=Sensitivity.SENSITIVE,
            payload_ref=uuid.uuid4(),
        )),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "OPERATIONAL", "SENSITIVE",
            "VAULT_REF", None, "payload-1", NOW,
        )),
        # negative: OPERATIONAL + SENSITIVE + INLINE
        _pyd_accepts(lambda: _mk_record(
            ValueStorageClass.INLINE_NON_SENSITIVE,
            domain=MemoryDomain.OPERATIONAL,
            sensitivity=Sensitivity.SENSITIVE,
            inline="sensitive_data",
        )),
        _sql_accepts(conn, MEMREC_SQL, (
            uuid.uuid4().hex, "OPERATIONAL", "SENSITIVE",
            "INLINE_NON_SENSITIVE", "{\"leak\":1}", None, NOW,
        )),
    )


def test_parity_prohibited_payload_impossible(conn):
    """P0-02: PROHIBITED cannot be stored as a durable PayloadObject."""
    _assert_parity(
        "PayloadObject PROHIBITED",
        conn,
        # positive: SENSITIVE sensitivity
        _pyd_accepts(lambda: PayloadObject(
            payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.ACTIVE,
            sensitivity=Sensitivity.SENSITIVE, key_handle="kh", ciphertext_location="loc",
            created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=None,
        )),
        _sql_accepts(conn, PAYLOAD_SQL, (
            uuid.uuid4().hex, "ACTIVE", "kh", "loc", NOW, None,
        )),
        # negative: PROHIBITED sensitivity
        _pyd_accepts(lambda: PayloadObject(
            payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.ACTIVE,
            sensitivity=Sensitivity.PROHIBITED, key_handle="kh", ciphertext_location="loc",
            created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=None,
        )),
        _sql_accepts(conn,
            "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, ciphertext_location, created_at) "
            "VALUES (?, 'MEMORY_VALUE', 'ACTIVE', 'PROHIBITED', 'kh', 'loc', ?)",
            (uuid.uuid4().hex, NOW),
        ),
    )


def test_parity_payload_lifecycle_partial_rejected(conn):
    """P1-01: Partial lifecycle state rejections on both Pydantic and SQLite."""
    # Positive control: ACTIVE with both keys
    assert _pyd_accepts(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.ACTIVE,
        sensitivity=Sensitivity.ORDINARY, key_handle="kh", ciphertext_location="loc",
        created_at=NOW_DT, activated_at=None, destroyed_at=None,
    ))
    assert _sql_accepts(conn, PAYLOAD_SQL, (
        uuid.uuid4().hex, "ACTIVE", "kh", "loc", NOW, None,
    ))

    # Partial Case 1: STAGED with key_handle != None, loc == None
    assert not _pyd_accepts(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.STAGED,
        sensitivity=Sensitivity.ORDINARY, key_handle="kh", ciphertext_location=None,
        created_at=NOW_DT, activated_at=None, destroyed_at=None,
    ))
    assert not _sql_accepts(conn, PAYLOAD_SQL, (
        uuid.uuid4().hex, "STAGED", "kh", None, NOW, None,
    ))

    # Partial Case 2: STAGED with key_handle == None, loc != None
    assert not _pyd_accepts(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.STAGED,
        sensitivity=Sensitivity.ORDINARY, key_handle=None, ciphertext_location="loc",
        created_at=NOW_DT, activated_at=None, destroyed_at=None,
    ))
    assert not _sql_accepts(conn, PAYLOAD_SQL, (
        uuid.uuid4().hex, "STAGED", None, "loc", NOW, None,
    ))

    # Partial Case 3: DESTROYED with key_handle != None, loc == None
    assert not _pyd_accepts(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.DESTROYED,
        sensitivity=Sensitivity.ORDINARY, key_handle="kh", ciphertext_location=None,
        created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=NOW_DT,
    ))
    assert not _sql_accepts(conn, PAYLOAD_SQL, (
        uuid.uuid4().hex, "DESTROYED", "kh", None, NOW, NOW,
    ))

    # Partial Case 4: DESTROYED with key_handle == None, loc != None
    assert not _pyd_accepts(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=PayloadStatus.DESTROYED,
        sensitivity=Sensitivity.ORDINARY, key_handle=None, ciphertext_location="loc",
        created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=NOW_DT,
    ))
    assert not _sql_accepts(conn, PAYLOAD_SQL, (
        uuid.uuid4().hex, "DESTROYED", None, "loc", NOW, NOW,
    ))

