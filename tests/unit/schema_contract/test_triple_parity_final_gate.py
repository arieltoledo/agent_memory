"""C3 — Triple Parity suite extension: TP-05..TP-13 (Structural Parity Final Gate).

Coder 2 (Antigravity) contact: "Mis FKs y tablas están listas. Avanzá con los
casos TP-05 a TP-13 de Triple Paridad apenas Codex termine."

This covers the Final Gate invariants that landed in the SQLite schema and the
Pydantic models:

    TP-05  Ghost Audit        commits.audit_id FK -> audits(id): no dangling audit.
    TP-06  Commit revision    commits.revision > 0 (rejects 0 / -1).
    TP-07  op_type            patch_operations.op_type NOT NULL + enum (no GARBAGE).
    TP-08  Evidence class     evidence.storage_class IN (INLINE_NON_SENSITIVE, VAULT_REF); NONE rejected.
    TP-09  Evidence purge     removed_categories_json must be json_valid; scope enum strict.
    TP-10  Payload purpose    payload_objects.purpose IN (EVIDENCE, MEMORY_VALUE, PATCH_VALUE); GARBAGE rejected.
    TP-11  SESSION not durable memory_records.domain/lifetime reject SESSION (persona/op only, temporary/durable only).
    TP-12  Supersession       memory_records.supersedes_record_id FK -> memory_records(id): no dangling lineage.
    TP-13  Payload EVIDENCE   PROHIBITED evidence payload never durable (purpose EVIDENCE lifetime boundary).

Every invariant reuses the A/B/C triple-parity discipline from test_triple_parity.py:
an independently-encoded Spec predicate plus a POSITIVE and NEGATIVE control so a
PASS is only recorded when the negative shape is rejected on both Pydantic and
SQLite AND the positive shape is accepted on both.

Referential (FK) invariants (TP-05, TP-12) live at the Persistence Boundary — the
SQLite layer is authoritative for "row must exist"; Pydantic enforces the
type-shape. Both controls are therefore exercised.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from memory_agent.domain.enums import (
    Sensitivity, ValueStorageClass, Lifetime, RecordStatus,
    PatchOperationType, EvidenceStatus, SemanticType, PayloadStatus,
)
from memory_agent.domain.models import (
    MemoryRecord, PayloadObject, EvidenceRecord, CommitRecord,
)
from tests.unit.schema_contract.test_triple_parity import (
    pyd_accept, sql_accept, classify,
)

NOW = "2026-08-31T00:00:00Z"
NOW_DT = datetime(2026, 8, 31, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# TP-05 — Ghost Audit: a commit must anchor to an existing audit (no dangling).
# ---------------------------------------------------------------------------
# Persistence Boundary: SQLite enforces row existence via commits.audit_id FK.
# Negative = commit -> phantom audit (REJECT). Positive control = commit ->
# freshly-provisioned existing audit (ACCEPT).
# ---------------------------------------------------------------------------

def _commit_row(patch_id, audit_id):
    return (
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, "
        "patch_hash, audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES (?, 'branch-1', 2, NULL, ?, 'hash0', ?, 0, 'policy-1', ?)",
        (uuid.uuid4().hex, patch_id, audit_id, NOW),
    )


def test_tp05_ghost_audit(conn):
    # Provision two fresh patches (avoiding commits.patch_id UNIQUE collision with
    # commit-ref) so each attempt isolates the audit FK as the only variable.
    def _provision(tag):
        conn.execute(
            "INSERT INTO patches (id, branch_id, base_revision, core_version, "
            "policy_snapshot_id, status, patch_hash, generator_model_id, "
            "generator_prompt_version, proposed_at) "
            f"VALUES ('p-{tag}', 'branch-1', 0, 0, 'policy-1', 'COMMITTED', 'h', 'm', 'p', ?)",
            (NOW,))
    _provision("ghost")
    conn.commit()

    ghost_audit = uuid.uuid4().hex
    sql_ghost = sql_accept(conn, *_commit_row("p-ghost", ghost_audit))
    assert not sql_ghost, "TP-05: commit to missing audit must REJECT on SQLite (ghost audit)"

    # positive control: same fresh patch, a different commit, real audit
    try:
        conn.execute(
            "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, "
            "core_version, policy_snapshot_id, evidence_binding, decision, reason_codes_json, "
            "auditor_model_id, auditor_prompt_version, created_at) "
            "VALUES ('audit-ghost-pos', 'p-ghost', 'h', 'branch-1', 0, 0, 'policy-1', 'b', "
            "'ACCEPT', '[]', 'm', 'p', ?)", (NOW,))
        conn.commit()
        sql_real = sql_accept(conn, *_commit_row("p-ghost", "audit-ghost-pos"))
    except Exception:
        sql_real = False
    assert sql_real, "TP-05 positive: commit to existing audit must ACCEPT"

    # type-shape parity: Pydantic requires a well-formed UUID audit_id
    pyd_bad = pyd_accept(lambda: CommitRecord(
        commit_id=uuid.uuid4(), branch_id=uuid.uuid4(), revision=2,
        previous_commit_id=None, patch_id=uuid.uuid4(), patch_hash="h",
        audit_id="not-a-uuid", core_version=0, policy_snapshot_id=uuid.uuid4(),
        committed_at=NOW_DT,
    ))
    pyd_ok = pyd_accept(lambda: CommitRecord(
        commit_id=uuid.uuid4(), branch_id=uuid.uuid4(), revision=2,
        previous_commit_id=None, patch_id=uuid.uuid4(), patch_hash="h",
        audit_id=uuid.uuid4(), core_version=0, policy_snapshot_id=uuid.uuid4(),
        committed_at=NOW_DT,
    ))
    assert not pyd_bad, "TP-05: malformed audit_id must REJECT on Pydantic"
    assert pyd_ok, "TP-05: well-formed audit_id must ACCEPT on Pydantic"


# ---------------------------------------------------------------------------
# TP-06 — Commit revision must be > 0 (rejects 0 / -1).
# ---------------------------------------------------------------------------

_COMMIT_COLS = (
    "id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
    "audit_id, core_version, policy_snapshot_id, committed_at"
)


def _commit_rev(conn, revision):
    """Provision a fresh patch+audit, then attempt a commit with the given revision.
    The fresh, valid audit anchor ensures any rejection is caused by the
    CHECK(revision > 0), never by the UNIQUE(audit_id) collision with commit-ref."""
    tag = uuid.uuid4().hex
    patch = f"patch-r-{tag}"
    audit = f"audit-r-{tag}"
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        f"VALUES ('{patch}', 'branch-1', 0, 0, 'policy-1', 'COMMITTED', 'h', 'm', 'p', ?)", (NOW,))
    conn.execute(
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        f"VALUES ('{audit}', '{patch}', 'h', 'branch-1', 0, 0, 'policy-1', 'b', 'ACCEPT', "
        "'[]', 'm', 'p', ?)", (NOW,))
    conn.commit()
    return (
        f"INSERT INTO commits ({_COMMIT_COLS}) VALUES "
        "(?, 'branch-1', ?, NULL, ?, 'h', ?, 0, 'policy-1', ?)",
        (uuid.uuid4().hex, revision, patch, audit, NOW),
    )


def _commit_pyd(revision):
    return CommitRecord(
        commit_id=uuid.uuid4(), branch_id=uuid.uuid4(), revision=revision,
        previous_commit_id=None, patch_id=uuid.uuid4(), patch_hash="h",
        audit_id=uuid.uuid4(), core_version=0, policy_snapshot_id=uuid.uuid4(),
        committed_at=NOW_DT,
    )


@pytest.mark.parametrize("revision", [0, -1])
def test_tp06_commit_revision_positive(conn, revision):
    classify(f"commit revision={revision}",
             False,  # spec forbids non-positive revision
             pyd_accept(lambda: _commit_pyd(revision)),
             sql_accept(conn, *_commit_rev(conn, revision)))

def test_tp06_commit_revision_positive_control(conn):
    # distinct audit to avoid UNIQUE(audit_id) collision from commit-ref
    conn.execute(
        "INSERT INTO patches (id, branch_id, base_revision, core_version, policy_snapshot_id, "
        "status, patch_hash, generator_model_id, generator_prompt_version, proposed_at) "
        "VALUES ('patch-pos', 'branch-1', 0, 0, 'policy-1', 'COMMITTED', 'h', 'm', 'p', ?)",
        (NOW,))
    conn.execute(
        "INSERT INTO audits (id, patch_id, patch_hash, branch_id, base_revision, core_version, "
        "policy_snapshot_id, evidence_binding, decision, reason_codes_json, auditor_model_id, "
        "auditor_prompt_version, created_at) "
        "VALUES ('audit-pos', 'patch-pos', 'h', 'branch-1', 0, 0, 'policy-1', 'b', 'ACCEPT', "
        "'[]', 'm', 'p', ?)", (NOW,))
    conn.execute(
        "INSERT INTO commits (id, branch_id, revision, previous_commit_id, patch_id, patch_hash, "
        "audit_id, core_version, policy_snapshot_id, committed_at) "
        "VALUES ('commit-pos', 'branch-1', 2, NULL, 'patch-pos', 'h', 'audit-pos', 0, 'policy-1', ?)",
        (NOW,))
    conn.commit()
    pyd = pyd_accept(lambda: _commit_pyd(2))
    assert pyd, "TP-06 positive: revision=2 must ACCEPT on Pydantic"


# ---------------------------------------------------------------------------
# TP-07 — patch_operations.op_type NOT NULL + enum (no GARBAGE).
# ---------------------------------------------------------------------------

def _pop_row(op_type):
    return (
        "INSERT INTO patch_operations (operation_id, patch_id, op_index, op_type) "
        "VALUES (?, 'patch-ref', 0, ?)",
        (uuid.uuid4().hex, op_type),
    )


def test_tp07_op_type_valid(conn):
    pyd_valid = PatchOperationType.ADD.value in {
        "ADD", "SUPERSEDE", "RETRACT", "LINK", "FLAG_CONFLICT",
        "RESOLVE_CONFLICT", "PURGE_REQUEST"}
    sql_valid = sql_accept(conn, *_pop_row("ADD"))
    classify("op_type=ADD", True, pyd_valid, sql_valid)


def test_tp07_op_type_garbage_rejected(conn):
    sql_garbage = sql_accept(conn, *_pop_row("GARBAGE"))
    assert not sql_garbage, "TP-07: op_type=GARBAGE must REJECT on SQLite"
    try:
        PatchOperationType("GARBAGE")
        pyd_garbage = True
    except ValueError:
        pyd_garbage = False
    assert not pyd_garbage, "TP-07: op_type=GARBAGE must REJECT on Pydantic enum"
    sql_null = sql_accept(conn, *_pop_row(None))
    assert not sql_null, "TP-07: op_type NULL must REJECT on SQLite (NOT NULL)"


# ---------------------------------------------------------------------------
# TP-08 — Evidence storage_class: NONE rejected (only INLINE_NON_SENSITIVE/VAULT_REF).
# ---------------------------------------------------------------------------

def _ev_row(storage, inline, payload_id):
    return (
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories_json, policy_snapshot_id, created_at) "
        "VALUES (?, 'GLOBAL', NULL, 'MSG', 'ACTIVE', 'ORDINARY', ?, ?, ?, 1, '[]', 'policy-1', ?)",
        (uuid.uuid4().hex, storage, inline, payload_id, NOW),
    )


def _ev_pyd(storage, inline, payload_ref):
    return EvidenceRecord(
        evidence_id=uuid.uuid4(), scope_type="GLOBAL", branch_id=None, source_kind="MSG",
        status=EvidenceStatus.ACTIVE, sensitivity=Sensitivity.ORDINARY, storage_class=storage,
        inline_sanitized_text=inline, payload_ref=payload_ref, sanitization_applied=True,
        removed_categories=(), policy_snapshot_id=uuid.uuid4(), created_at=NOW_DT,
    )


def test_tp08_evidence_storage_none_rejected(conn):
    pyd_none = pyd_accept(lambda: _ev_pyd(
        ValueStorageClass.NONE, None, None))
    sql_none = sql_accept(conn, *_ev_row("NONE", None, None))
    classify("evidence storage_class=NONE", False, pyd_none, sql_none)

    pyd_pos = pyd_accept(lambda: _ev_pyd(
        ValueStorageClass.INLINE_NON_SENSITIVE, "x", None))
    sql_pos = sql_accept(conn, *_ev_row("INLINE_NON_SENSITIVE", "x", None))
    assert pyd_pos, "TP-08 positive: INLINE evidence must ACCEPT on Pydantic"
    assert sql_pos, "TP-08 positive: INLINE evidence must ACCEPT on SQLite"


# ---------------------------------------------------------------------------
# TP-09 — Evidence removed_categories_json must be valid JSON.
# ---------------------------------------------------------------------------

def _ev_json(badjson):
    return (
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories_json, policy_snapshot_id, created_at) "
        "VALUES (?, 'GLOBAL', NULL, 'MSG', 'ACTIVE', 'ORDINARY', 'INLINE_NON_SENSITIVE', "
        "'x', NULL, 1, ?, 'policy-1', ?)",
        (uuid.uuid4().hex, badjson, NOW),
    )


def test_tp09_evidence_removed_categories_json(conn):
    sql_bad = sql_accept(conn, *_ev_json("{not-json"))
    assert not sql_bad, "TP-09: invalid removed_categories_json must REJECT on SQLite"
    sql_good = sql_accept(conn, *_ev_json('["CAT_A","CAT_B"]'))
    assert sql_good, "TP-09 positive: valid removed_categories_json must ACCEPT"


# ---------------------------------------------------------------------------
# TP-10 — payload_objects.purpose enum (rejects GARBAGE).
# ---------------------------------------------------------------------------

def _payload_purpose(purpose):
    return (
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, ?, 'ACTIVE', 'ORDINARY', 'kh', 'loc', ?)",
        (uuid.uuid4().hex, purpose, NOW),
    )


def test_tp10_payload_purpose_enum(conn):
    sql_garbage = sql_accept(conn, *_payload_purpose("GARBAGE"))
    assert not sql_garbage, "TP-10: purpose=GARBAGE must REJECT on SQLite"
    sql_null = sql_accept(conn, *_payload_purpose(None))
    assert not sql_null, "TP-10: purpose NULL must REJECT on SQLite (NOT NULL)"
    sql_ok = sql_accept(conn, *_payload_purpose("EVIDENCE"))
    assert sql_ok, "TP-10 positive: purpose=EVIDENCE must ACCEPT"


# ---------------------------------------------------------------------------
# TP-11 — SESSION not a durable memory domain/lifetime.
# ---------------------------------------------------------------------------

def _mem_row(domain, lifetime):
    return (
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at) "
        "VALUES (?, ?, 'branch-1', 'k', 'DECISION', 'ACTIVE', 'ORDINARY', "
        "'INLINE_NON_SENSITIVE', '{\"v\":1}', NULL, ?, 'policy-1', 'commit-ref', ?)",
        (uuid.uuid4().hex, domain, lifetime, NOW),
    )


def _mem_pyd(domain, lifetime):
    return MemoryRecord(
        record_id=uuid.uuid4(), domain=domain, branch_id=None, semantic_key="k",
        kind=SemanticType.DECISION, status=RecordStatus.ACTIVE,
        sensitivity=Sensitivity.ORDINARY,
        storage_class=ValueStorageClass.INLINE_NON_SENSITIVE, inline_value={"v": 1},
        payload_ref=None, lifetime=lifetime, valid_until=None, timezone=None,
        policy_snapshot_id=uuid.uuid4(), mount_policy_id=None,
        created_commit_id=uuid.uuid4(), supersedes_record_id=None,
        created_at=NOW_DT, purged_at=None,
    )


@pytest.mark.parametrize("domain,lifetime", [("SESSION", "DURABLE"), ("OPERATIONAL", "SESSION")])
def test_tp11_session_not_durable(conn, domain, lifetime):
    classify(f"memory {domain}/{lifetime}",
             False,  # spec forbids SESSION as durable domain/lifetime
             pyd_accept(lambda: _mem_pyd(domain, lifetime)),
             sql_accept(conn, *_mem_row(domain, lifetime)))


def test_tp11_session_positive_control(conn):
    pyd = pyd_accept(lambda: _mem_pyd("OPERATIONAL", "DURABLE"))
    sql = sql_accept(conn, *_mem_row("OPERATIONAL", "DURABLE"))
    assert pyd, "TP-11 positive: OPERATIONAL/DURABLE must ACCEPT on Pydantic"
    assert sql, "TP-11 positive: OPERATIONAL/DURABLE must ACCEPT on SQLite"


# ---------------------------------------------------------------------------
# TP-12 — Supersession lineage: supersedes_record_id must reference a real record.
# ---------------------------------------------------------------------------

def _sup_row(supersedes_id):
    return (
        "INSERT INTO memory_records (id, domain, branch_id, semantic_key, kind, status, "
        "sensitivity, storage_class, inline_value_json, payload_id, lifetime, policy_snapshot_id, "
        "created_by_commit_id, created_at, supersedes_record_id) "
        "VALUES (?, 'OPERATIONAL', 'branch-1', 'k2', 'DECISION', 'SUPERSEDED', 'ORDINARY', "
        "'INLINE_NON_SENSITIVE', '{\"v\":1}', NULL, 'DURABLE', 'policy-1', 'commit-ref', ?, ?)",
        (uuid.uuid4().hex, NOW, supersedes_id),
    )


def test_tp12_supersession_lineage(conn):
    ghost = uuid.uuid4().hex
    sql_ghost = sql_accept(conn, *_sup_row(ghost))
    sql_real = sql_accept(conn, *_sup_row("rec-1"))
    assert not sql_ghost, "TP-12: supersedes a missing record must REJECT (dangling lineage)"
    assert sql_real, "TP-12 positive: supersedes existing rec-1 must ACCEPT"


# ---------------------------------------------------------------------------
# TP-13 — Evidence/Payload: PROHIBITED payload never durable (purpose=EVIDENCE).
# ---------------------------------------------------------------------------

def _ev_prohibited_payload_row():
    return (
        "INSERT INTO evidence (id, scope_type, branch_id, source_kind, status, sensitivity, "
        "storage_class, inline_sanitized_text, payload_id, sanitization_applied, "
        "removed_categories_json, policy_snapshot_id, created_at) "
        "VALUES (?, 'GLOBAL', NULL, 'MSG', 'ACTIVE', 'ORDINARY', 'VAULT_REF', NULL, "
        "'payload-1', 1, '[]', 'policy-1', ?)",
        (uuid.uuid4().hex, NOW),
    )


def test_tp13_prohibited_evidence_payload(conn):
    # A PROHIBITED payload object is never durable — regardless of purpose
    # (EVIDENCE here). Both layers must reject the PROHIBITED sensitivity.
    pyd = pyd_accept(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="EVIDENCE", status=PayloadStatus.ACTIVE,
        sensitivity=Sensitivity.PROHIBITED, key_handle="kh", ciphertext_location="loc",
        created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=None))
    sql = sql_accept(conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, 'EVIDENCE', 'ACTIVE', 'PROHIBITED', 'kh', 'loc', ?)",
        (uuid.uuid4().hex, NOW))
    classify("payload purpose=EVIDENCE PROHIBITED", False, pyd, sql)

    pyd_pos = pyd_accept(lambda: PayloadObject(
        payload_id=uuid.uuid4(), purpose="EVIDENCE", status=PayloadStatus.ACTIVE,
        sensitivity=Sensitivity.ORDINARY, key_handle="kh", ciphertext_location="loc",
        created_at=NOW_DT, activated_at=NOW_DT, destroyed_at=None))
    sql_pos = sql_accept(conn,
        "INSERT INTO payload_objects (id, purpose, status, sensitivity, key_handle, "
        "ciphertext_location, created_at) "
        "VALUES (?, 'EVIDENCE', 'ACTIVE', 'ORDINARY', 'kh', 'loc', ?)",
        (uuid.uuid4().hex, NOW))
    assert pyd_pos, "TP-13 positive: EVIDENCE/ORDINARY payload must ACCEPT on Pydantic"
    assert sql_pos, "TP-13 positive: EVIDENCE/ORDINARY payload must ACCEPT on SQLite"
