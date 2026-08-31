# Architecture Decision Log — Memory Agent Sprint A

> Maintained by Senior Architect
> Authoritative Baseline: Memory Agent Specification v0.3.0 (FROZEN) & Data Model v1.1

---

## ADR-001: patch_hash NOT UNIQUE — patch_id IS the idempotency key

```yaml
id: ADR-001
status: accepted
context: >
  The Data Model v1.1 (DR-02) explicitly confirmed that patch_hash cannot be UNIQUE
  because the same semantic proposal may be re-submitted with a different patch_id
  after a rejection. Idempotency is enforced via commits.patch_id UNIQUE.
decision: >
  Migration 0001_initial.sql implements:
  - CREATE INDEX ix_patches_patch_hash ON patches(patch_hash);  -- non-unique
  - commits.patch_id TEXT NOT NULL UNIQUE
  test_patch_rechazado_no_bloquea_nueva_propuesta confirms two patches
  with same hash can coexist.
alternatives:
  - UNIQUE(patch_hash) — rejected per DR-02
reason: >
  patch_hash is an audit binding snapshot, not an identity key.
  Two distinct proposals (different context/revision/policy) may produce
  the same hash but must be independently evaluable.
affected_components: [patches, commits, PatchRepository, CommitRepository]
spec_impact: none
tests_affected: [test_patch_rechazado_no_bloquea_nueva_propuesta, test_replay_fails]
```

---

## ADR-002: Personal Memory — VAULT_REF enforced at multiple layers

```yaml
id: ADR-002
status: accepted
context: >
  Data Model v1.1 Section 3 mandates ALL Personal Memory payloads use VAULT_REF,
  even when sensitivity is ORDINARY. This prevents PURGE from requiring
  historical commit rewriting.
decision: >
  Enforced at three layers:
  1. Pydantic: MemoryRecord._memory_storage() (models.py)
  2. SQL: CHECK(domain != 'PERSONAL' OR storage_class = 'VAULT_REF')
     in memory_records, patch_operations, evidence tables
  3. Test: test_personal_memory_is_never_inline, test_personal_inline_fails
alternatives:
  - Enforce only in SQL — weaker, allows invalid in-memory objects
  - Enforce only in Pydantic — weaker, allows SQL bypass via raw INSERT
reason: >
  Defense in depth. Both Pydantic and SQL enforce the invariant independently.
affected_components: [MemoryRecord, memory_records, patch_operations, evidence]
spec_impact: none
tests_affected: [test_personal_memory_is_never_inline, test_personal_inline_fails]
```

---

## ADR-003: PURGED tombstone retains payload_id, clears inline_value

```yaml
id: ADR-003
status: accepted
context: >
  A purged Personal Memory record must retain an opaque payload_id reference
  (for audit trail) but NEVER retain inline_value or content-derived hashes.
  The corresponding payload_objects row reaches status=DESTROYED with
  key_handle=NULL and ciphertext_location=NULL.
decision: >
  Enforced at:
  1. Pydantic: MemoryRecord._memory_storage() checks purged + personal → no inline
  2. Pydantic: PayloadObject._payload_state() enforces DESTROYED → NULL key/location
  3. SQL: payload_objects allows NULL key_handle, ciphertext_location
  4. Test: test_purged_tombstone, test_destroyed_payload,
     test_purged_tombstone_keeps_opaque_payload_reference
alternatives:
  - DELETE the payload_objects row entirely — breaks FK integrity
  - Set payload_id=NULL in memory_records — loses audit trail
reason: >
  Foreign keys must remain intact. PURGE destroys content, not metadata references.
affected_components: [MemoryRecord, PayloadObject, memory_records, payload_objects]
spec_impact: none
tests_affected: [test_purged_tombstone, test_destroyed_payload]
```

---

## ADR-004: COMMIT_ENGINE absent from DetectionLayer enum

```yaml
id: ADR-004
status: escalated
context: >
  Data Model v1.1 Section 81 traceability table assigns T20 (State Reconstruction)
  expected detection layer to COMMIT_ENGINE. However, the authoritative DetectionLayer
  enum (Section 7.22) does NOT include COMMIT_ENGINE as a member.
  Coder 3 correctly identified this as TEST_SPEC_CONFLICT and froze it without
  picking a substitute.
decision: >
  FROZEN for spec owner review. The test T20 is marked status=TEST_SPEC_CONFLICT
  and skipped in pytest. The reference kernel records the conflict value explicitly:
  "COMMIT_ENGINE (not in DetectionLayer enum)".
alternatives:
  - Add COMMIT_ENGINE to DetectionLayer enum — changes spec
  - Map T20 to COMMIT_VALIDATOR — changes traceability semantics
reason: >
  Neither alternative can be chosen without spec owner approval.
  This is a DESIGN_GAP between the traceability table and the enum definition.
affected_components: [DetectionLayer, detection_events, T20 fixture]
spec_impact: definite
tests_affected: [T20_state_reconstruction]
```

---

## ADR-005: SQLite schema parity against Data Model v1.1

```yaml
id: ADR-005
status: open (in progress - Coder 2 OLA 1 correction)
context: >
  Field-by-field audit revealed critical schema mismatches between 0001_initial.sql
  and Data Model v1.1 Sections 37-60 (e.g. branches missing current_revision, status,
  core_version; core_snapshots PK mismatch; mount_policies schema mismatch).
decision: >
  0001_initial.sql MUST be rewritten to achieve 100% exact parity with Data Model v1.1
  Sections 37-60, including all CHECK constraints, json_valid(), and partial indexes.
alternatives:
  - Partial compatibility — rejected; blocks CommitValidator TOCTOU checks
reason: >
  Specification and SQLite must describe exactly the same state machine.
affected_components: [core_snapshots, branches, branch_contracts, mount_policies,
  patch_operations, memory_records, purge_target_results]
spec_impact: none
tests_affected: [tests/unit/schema_contract/*]
```

---

## ADR-006: Repository protocols must use typed domain models and enums

```yaml
id: ADR-006
status: open (in progress - Coder 1 & Coder 2 OLA 1 correction)
context: >
  Repository protocol methods in protocols.py used Dict[str, Any] and primitive str IDs.
  BranchRepository and CoreRepository still return Optional[dict].
decision: >
  All repository protocols MUST take and return typed domain models (MemoryRecord,
  EvidenceRecord, Branch, CoreSnapshot, etc.), enums (RecordStatus, etc.), and UUIDs.
alternatives:
  - Dict[str, Any] with repository internal validation — rejected (breaks trust boundary)
reason: >
  The Trusted Deterministic Base cannot allow untyped dictionaries across its boundary.
affected_components: [protocols.py, Branch, CoreSnapshot, sqlite implementations]
spec_impact: none
tests_affected: [All repository integration tests]
```

---

## ADR-007: Python version compatibility — Minimum Python 3.11+ (Target 3.12+)

```yaml
id: ADR-007
status: accepted
context: >
  The domain layer utilizes enum.StrEnum which was introduced in Python 3.11.
  Technical Design v1.0 targets Python 3.12+. The stale .venv was on 3.10.
decision: >
  The project requires Python 3.11+ minimum (3.12+ recommended, 3.14 verified).
  pyproject.toml will enforce requires-python = ">=3.11".
alternatives:
  - Backport strenum for 3.10 — rejected
reason: >
  Aligns with Technical Design v1.0 standard.
affected_components: [.venv, pyproject.toml]
spec_impact: none
tests_affected: [All tests]
```

---

## ADR-008: DraftPatch.operations MUST be a strictly typed discriminated union

```yaml
id: ADR-008
status: accepted (SUPERSEDES previous draft decision)
context: >
  DraftPatch.operations was loosely typed as tuple[dict[str, Any], ...], creating
  a hole in the Pydantic trust boundary. The LLM raw output must be validated
  into a concrete discriminated union before reaching PatchStager.
decision: >
  DraftPatch.operations MUST be typed as tuple[DraftPatchOperation, ...] where
  DraftPatchOperation is an Annotated Union discriminated by op: Literal[...]
  (DraftAddOperation, DraftSupersedeOperation, DraftRetractOperation, DraftLinkOperation,
  DraftFlagConflictOperation, DraftResolveConflictOperation, DraftPurgeRequestOperation).
  Draft operations use proposed_value: JsonValue (RAM plaintext) and do NOT contain
  premature payload_refs or ciphertext digests.
alternatives:
  - tuple[dict[str, Any], ...] — REJECTED (untyped trust boundary leak)
  - Premature CognitiveStatePatch — REJECTED (violates Draft->Durable RAM separation)
reason: >
  Untrusted LLM JSON must be parsed and typed-validated before any cryptographic
  or staging resource allocation.
affected_components: [DraftPatch, DraftPatchOperation, models.py]
spec_impact: none
tests_affected: [Negative validation tests in tests/unit/domain/]
```

---

## ADR-009: PayloadRepository and VaultRepository protocols

```yaml
id: ADR-009
status: accepted
context: >
  The encrypted vault and payload metadata are distinct trust boundaries requiring
  isolated repository interfaces for crypto-erasure and closure verification.
decision: >
  Define PayloadRepository (metadata & destroyed state) and VaultRepository
  (ciphertext store/retrieve/delete) in protocols.py.
alternatives:
  - Combined into PurgeRepository — rejected (conflates responsibilities)
reason: >
  Adheres to single-responsibility and enables independent test doubles.
affected_components: [protocols.py, PayloadRepository, VaultRepository]
spec_impact: none
tests_affected: [PURGE erasure closure tests]
```

---

## ADR-010: Idempotent migration runner

```yaml
id: ADR-010
status: accepted
context: >
  apply_migrations() executed raw scripts via executescript() without recording version.
decision: >
  apply_migrations() must record applied migration versions in schema_migrations
  table to ensure deterministic, idempotent schema evolution.
alternatives:
  - Raw executescript without tracking — acceptable only for initial scratch, must be upgraded
reason: >
  Deterministic kernel guarantees require verifiable schema migration history.
affected_components: [sqlite.py, schema_migrations]
spec_impact: none
tests_affected: [Schema migration tests]
```

---

## ADR-011: Strict recursive JsonValue type definition

```yaml
id: ADR-011
status: accepted
context: >
  JsonValue was defined as JsonValue = Any, which allows arbitrary Python objects,
  functions, or non-serializable instances into values slated for hashing.
decision: >
  JsonValue MUST be defined as a strict recursive union:
  JsonValue = Union[None, bool, int, float, str, list['JsonValue'], dict[str, 'JsonValue']]
alternatives:
  - JsonValue = Any — REJECTED
reason: >
  Canonical hashing and SQLite json_valid() require strict JSON semantics.
affected_components: [models.py, DraftValue, ValueReference, MemoryRecord]
spec_impact: none
tests_affected: [Domain model strictness tests]
```
