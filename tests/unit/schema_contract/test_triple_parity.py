"""C3 — Triple Parity suite (Pydantic <-> SQLite <-> Specification v0.3.0 / Data Model v1.1).

Coder 2's directive asks for cases A/B/C:
    A) Pydantic ACCEPT  / SQLite REJECT            -> parity break (Pydantic permissive)
    B) Pydantic REJECT  / SQLite ACCEPT            -> parity break (Pydantic strict)
    C) Pydantic ACCEPT / SQLite ACCEPT / Spec FORBIDS -> BOTH agree but BOTH wrong.

Case C is the subtle one: two implementations agreeing does not prove either is
correct. Here each invariant is driven through all three layers and the two
implementations must agree with an independently-encoded Specification predicate.

Every invariant carries a POSITIVE and a NEGATIVE control so a PASS is only
recorded when the negative shape is rejected on both Pydantic and SQLite (and by
Spec) AND the positive shape is accepted on both (and allowed by Spec).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from memory_agent.domain.enums import *
from memory_agent.domain.errors import DomainValidationError
from memory_agent.domain.models import (
    MemoryRecord, PayloadObject, EvidenceRecord,
)
from tests.unit.schema_contract.conftest import MIGRATIONS

NOW = "2026-08-31T00:00:00Z"
NOW_DT = datetime(2026, 8, 31, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Layer probes. Both return True == ACCEPT (consistent polarity).
# ---------------------------------------------------------------------------

def pyd_accept(builder) -> bool:
    try:
        builder()
        return True
    except (ValidationError, DomainValidationError):
        return False


def sql_accept(conn, sql: str, params: tuple) -> bool:
    try:
        conn.execute(sql, params)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def classify(name: str, spec_allows: bool, pyd: bool, sql: bool) -> str:
    """Verify triple parity for one shape. True flags mean ACCEPT.

    spec_allows=True  -> Data Model permits: both must ACCEPT.
    spec_allows=False -> Data Model forbids: both must REJECT.
    """
    if not spec_allows:
        if (not pyd) and (not sql):
            return "OK (Spec FORBIDS, both REJECT)"
        if (not pyd) and sql:
            raise AssertionError(f"[{name}] CASE B: Pydantic REJECT / SQLite ACCEPT (spec forbids)")
        if pyd and (not sql):
            raise AssertionError(f"[{name}] CASE A: Pydantic ACCEPT / SQLite REJECT (spec forbids)")
        raise AssertionError(
            f"[{name}] CASE C — Pydantic ACCEPT / SQLite ACCEPT but SPEC FORBIDS: "
            f"both agree but both are wrong."
        )
    if pyd and sql:
        return "OK (Spec allows, both ACCEPT)"
    if (not pyd) and (not sql):
        raise AssertionError(f"[{name}] both REJECT a spec-ALLOWED shape (over-strict)")
    raise AssertionError(f"[{name}] parity break A/B on a spec-ALLOWED shape")


# ---------------------------------------------------------------------------
# Invariant 1 — SENSITIVE never INLINE (must be VAULT_REF), both domains
# ---------------------------------------------------------------------------

def _mem_sql(domain, sensitivity, storage, inline, payload_id):
    return (
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, ?, 'branch-1', 'k', 'DECISION', 'ACTIVE', ?, ?, ?, ?, 'DURABLE', "
        "'policy-1', 'commit-ref', ?)",
        (uuid.uuid4().hex, domain, sensitivity, storage, inline, payload_id, NOW),
    )


def _mem_pyd(domain, sensitivity, storage, inline, payload_ref):
    return MemoryRecord(
        record_id=uuid.uuid4(), domain=domain, branch_id=None, semantic_key="k",
        kind=SemanticType.DECISION, status=RecordStatus.ACTIVE, sensitivity=sensitivity,
        storage_class=storage, inline_value=inline, payload_ref=payload_ref,
        lifetime=Lifetime.DURABLE, valid_until=None, timezone=None,
        policy_snapshot_id=uuid.uuid4(), mount_policy_id=None, created_commit_id=uuid.uuid4(),
        supersedes_record_id=None, created_at=NOW_DT, purged_at=None,
    )


@pytest.mark.parametrize("domain", [MemoryDomain.OPERATIONAL, MemoryDomain.PERSONAL])
def test_memory_sensitive_never_inline(conn, domain):
    # negative: SENSITIVE + INLINE -> spec forbids
    pyd = pyd_accept(lambda: _mem_pyd(
        domain, Sensitivity.SENSITIVE, ValueStorageClass.INLINE_NON_SENSITIVE, "x", None))
    sql = sql_accept(conn, *_mem_sql(domain.value, "SENSITIVE", "INLINE_NON_SENSITIVE", '"x"', None))
    classify("mem SENSITIVE+INLINE", False, pyd, sql)

    # positive control: SENSITIVE + VAULT_REF -> spec allows
    pyd_pos = pyd_accept(lambda: _mem_pyd(
        domain, Sensitivity.SENSITIVE, ValueStorageClass.VAULT_REF, None, uuid.uuid4()))
    sql_pos = sql_accept(conn, *_mem_sql(domain.value, "SENSITIVE", "VAULT_REF", None, "payload-1"))
    assert pyd_pos, "positive control: SENSITIVE+VAULT must ACCEPT on Pydantic"
    assert sql_pos, "positive control: SENSITIVE+VAULT must ACCEPT on SQLite"


@pytest.mark.parametrize("sensitivity", [s for s in (
    Sensitivity.ORDINARY, Sensitivity.PERSONAL, Sensitivity.SENSITIVE)
    if s != Sensitivity.SENSITIVE])
def test_memory_non_sensitive_inline_ok(conn, sensitivity):
    pyd = pyd_accept(lambda: _mem_pyd(
        MemoryDomain.OPERATIONAL, sensitivity, ValueStorageClass.INLINE_NON_SENSITIVE, "x", None))
    sql = sql_accept(conn, *_mem_sql(
        "OPERATIONAL", sensitivity.value, "INLINE_NON_SENSITIVE", '"x"', None))
    classify("mem non-sensitive INLINE", True, pyd, sql)


# ---------------------------------------------------------------------------
# Invariant 2 — PROHIBITED never a durable PayloadObject
# ---------------------------------------------------------------------------

def _payload_sql(status, sensitivity, kh, loc, destroyed):
    return (
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at, activated_at, destroyed_at) "
        "VALUES (?, 'MEMORY_VALUE', ?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, status, sensitivity, kh, loc, NOW,
         NOW if status in ("ACTIVE", "PURGE_PENDING") else None, destroyed),
    )


def _payload_pyd(status, sensitivity, kh, loc):
    return PayloadObject(
        payload_id=uuid.uuid4(), purpose="MEMORY_VALUE", status=status,
        sensitivity=sensitivity, key_handle=kh, ciphertext_location=loc,
        created_at=NOW_DT,
        activated_at=NOW_DT if status in (PayloadStatus.ACTIVE, PayloadStatus.PURGE_PENDING) else None,
        destroyed_at=NOW_DT if status in (PayloadStatus.DESTROYED, PayloadStatus.ABORTED) else None,
    )


def test_payload_prohibited_never_durable(conn):
    pyd = pyd_accept(lambda: _payload_pyd(
        PayloadStatus.ACTIVE, Sensitivity.PROHIBITED, "kh", "loc"))
    sql = sql_accept(conn, *_payload_sql("ACTIVE", "PROHIBITED", "kh", "loc", None))
    classify("payload PROHIBITED", False, pyd, sql)

    pyd_pos = pyd_accept(lambda: _payload_pyd(
        PayloadStatus.ACTIVE, Sensitivity.SENSITIVE, "kh", "loc"))
    sql_pos = sql_accept(conn, *_payload_sql("ACTIVE", "SENSITIVE", "kh", "loc", None))
    assert pyd_pos, "positive control: SENSITIVE payload must ACCEPT"
    assert sql_pos, "positive control: SENSITIVE payload must ACCEPT"


# ---------------------------------------------------------------------------
# Invariant 3 — Payload lifecycle: the four partial key/location cases (P1-01)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kh,loc", [
    ("k", "l"),    # both present
    (None, None),  # both absent
    ("k", None),   # key only
    (None, "l"),   # loc only
])
def test_payload_lifecycle_partial_states(conn, kh, loc):
    # ACTIVE: spec requires BOTH keys present
    spec_active = kh is not None and loc is not None
    pyd = pyd_accept(lambda: _payload_pyd(PayloadStatus.ACTIVE, Sensitivity.SENSITIVE, kh, loc))
    sql = sql_accept(conn, *_payload_sql("ACTIVE", "SENSITIVE", kh, loc, None))
    classify(f"payload ACTIVE kh={kh} loc={loc}", spec_active, pyd, sql)

    # DESTROYED: spec requires BOTH null
    spec_destroyed = kh is None and loc is None
    pyd_d = pyd_accept(lambda: _payload_pyd(PayloadStatus.DESTROYED, Sensitivity.SENSITIVE, kh, loc))
    sql_d = sql_accept(conn, *_payload_sql("DESTROYED", "SENSITIVE", kh, loc, NOW))
    classify(f"payload DESTROYED kh={kh} loc={loc}", spec_destroyed, pyd_d, sql_d)


# ---------------------------------------------------------------------------
# Invariant 4 — Evidence: BRANCH requires branch_id; SENSITIVE -> VAULT; PROHIBITED impossible
# ---------------------------------------------------------------------------

def _ev_pyd(scope_type, branch_id, storage, sensitivity, inline, payload_ref):
    return EvidenceRecord(
        evidence_id=uuid.uuid4(), scope_type=scope_type, branch_id=branch_id,
        source_kind="MSG", status=EvidenceStatus.ACTIVE, sensitivity=sensitivity,
        storage_class=storage, inline_sanitized_text=inline,
        payload_ref=payload_ref, sanitization_applied=True,
        removed_categories=(), policy_snapshot_id=uuid.uuid4(), created_at=NOW_DT,
    )


def _ev_sql(scope_type, branch_id, storage, sensitivity, inline, payload_id):
    return (
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories, policy_snapshot_id, created_at) "
        "VALUES (?, ?, ?, 'MSG', 'ACTIVE', ?, ?, ?, ?, 1, '[]', 'policy-1', ?)",
        (uuid.uuid4().hex, scope_type, branch_id, sensitivity, storage, inline,
         payload_id, NOW),
    )


@pytest.mark.parametrize("scope_type", ["BRANCH", "GLOBAL"])
def test_evidence_branch_requires_branch_id(conn, scope_type):
    spec_allows = scope_type != "BRANCH"
    pyd = pyd_accept(lambda: _ev_pyd(
        scope_type, None, ValueStorageClass.INLINE_NON_SENSITIVE,
        Sensitivity.ORDINARY, "x", None))
    sql = sql_accept(conn, *_ev_sql(
        scope_type, None, "INLINE_NON_SENSITIVE", "ORDINARY", "x", None))
    classify(f"evidence {scope_type} w/o branch_id", spec_allows, pyd, sql)


def test_evidence_sensitive_never_inline(conn):
    pyd = pyd_accept(lambda: _ev_pyd(
        "GLOBAL", None, ValueStorageClass.INLINE_NON_SENSITIVE,
        Sensitivity.SENSITIVE, "x", None))
    sql = sql_accept(conn, *_ev_sql(
        "GLOBAL", None, "INLINE_NON_SENSITIVE", "SENSITIVE", "x", None))
    classify("evidence SENSITIVE+INLINE", False, pyd, sql)

    pyd_pos = pyd_accept(lambda: _ev_pyd(
        "GLOBAL", None, ValueStorageClass.VAULT_REF,
        Sensitivity.SENSITIVE, None, uuid.uuid4()))
    sql_pos = sql_accept(conn, *_ev_sql(
        "GLOBAL", None, "VAULT_REF", "SENSITIVE", None, "payload-1"))
    assert pyd_pos, "positive control: evidence SENSITIVE+VAULT must ACCEPT"
    assert sql_pos, "positive control: evidence SENSITIVE+VAULT must ACCEPT"


def test_evidence_prohibited_impossible(conn):
    pyd = pyd_accept(lambda: _ev_pyd(
        "GLOBAL", None, ValueStorageClass.NONE, Sensitivity.PROHIBITED, None, None))
    sql = sql_accept(conn, *_ev_sql("GLOBAL", None, "NONE", "PROHIBITED", None, None))
    classify("evidence PROHIBITED", False, pyd, sql)
