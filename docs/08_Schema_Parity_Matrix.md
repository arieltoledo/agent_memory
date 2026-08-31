# Schema Parity Matrix (Persistence Boundary Final Closure)

## 1. Triple Paridad Verification
All invariants are tested against the three failure classes:
- **Case A (Pydantic ACCEPT / SQLite REJECT)**: 0 occurrences (eliminated)
- **Case B (Pydantic REJECT / SQLite ACCEPT)**: 0 occurrences (eliminated)
- **Case C (Pydantic ACCEPT / SQLite ACCEPT / Spec FORBIDS)**: 0 occurrences (e.g., SENSITIVE+INLINE resolved in both layers)

## 2. Parity Table

| Invariant / Field | Spec/Data Model | Pydantic | SQLite | Positive control | Negative control | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Branch revision >= 0** | §38 `current_revision >= 0` | Validated in `Branch` (`ge=0`) | `CHECK (current_revision >= 0)` | Valid revision ACCEPTS | Negative revision REJECTS | **PASS** |
| **Core snapshot JSON** | §37 `core_version, json_valid` | `CoreSnapshot` model | `CHECK (json_valid(content_json))` | Valid JSON string ACCEPTS | Malformed JSON REJECTS | **PASS** |
| **Branch contracts UNIQUE** | §39 `UNIQUE(branch_id, version)` | Domain identity model | `UNIQUE(branch_id, version)` | Distinct (b, v) ACCEPTS | Same (b, v) twice REJECTS | **PASS** |
| **Mount policies mode & flags** | §41 structured mode, bool | `MountPolicy` structured | `mode CHECK, allow_sens IN (0,1)` | Valid mode ACCEPTS | Invalid mode/flag REJECTS | **PASS** |
| **Enum CHECK constraints** | §37–§60 exact enums | Pydantic `StrEnum` (25 enums) | All tables `CHECK (col IN (...))` | Spec status ACCEPTS | GARBAGE/MAYBE REJECTS | **PASS** |
| **Storage: INLINE shape** | §27 inline requires value | `MemoryRecord` rejects w/o value | `CHECK` prevents payload_id | `INLINE + value` ACCEPTS | `INLINE + NULL` REJECTS | **PASS** |
| **Storage: VAULT_REF shape** | §27 vault requires payload | `MemoryRecord` rejects w/o payload | `CHECK` prevents inline_value | `VAULT + payload` ACCEPTS | `VAULT + inline` REJECTS | **PASS** |
| **Storage: NONE shape** | §27 NONE prohíbe ambos | `MemoryRecord` rejects both | `CHECK` prevents both | `NONE + nulls` ACCEPTS | `NONE + value` REJECTS | **PASS** |
| **Personal Vault-Only** | §3 `PERSONAL -> VAULT_REF` | `MemoryRecord` enforces VAULT | `CHECK` prevents INLINE | `PERSONAL + VAULT` ACCEPTS | `PERSONAL + INLINE` REJECTS | **PASS** |
| **Sensitive Vault-Only (Universal)** | P0-01: `SENSITIVE -> VAULT_REF` | `MemoryRecord` & `EvidenceRecord` | `CHECK` prevents INLINE | `OPERATIONAL + SENSITIVE + VAULT` ACCEPTS | `OPERATIONAL + SENSITIVE + INLINE` REJECTS | **PASS** |
| **Prohibited Payload Impossible** | P0-02: No `PROHIBITED` payload | `PayloadObject` rejects PROHIBITED | `CHECK (sensitivity IN (...))` | `SENSITIVE payload` ACCEPTS | `PROHIBITED payload` REJECTS | **PASS** |
| **Payload Lifecycle (4 partial)** | P1-01: exact key/location presence | `PayloadObject._payload_state` | `CHECK` (STAGED/ACTIVE vs DESTROYED) | ACTIVE w/ keys ACCEPTS | Partial key/location REJECTS | **PASS** |
| **Payload Destroyed Keys Cleared** | §43 DESTROYED -> keys NULL | `PayloadObject` forces NULL | `CHECK` forces keys NULL | DESTROYED w/ null keys ACCEPTS | DESTROYED w/ key REJECTS | **PASS** |
| **Patch hash Non-Unique** | §45 `ix_patches_patch_hash` | Non-unique in Pydantic | Non-unique index in SQLite | 2 patches same hash ACCEPTS | N/A (valid concurrency) | **PASS** |
| **Patch Idempotency** | §47 `commits.patch_id UNIQUE` | N/A (Persistence level) | `commits.patch_id UNIQUE` | New patch commit ACCEPTS | Replay same patch_id REJECTS | **PASS** |
| **Audit Decision Enum** | §46 `ACCEPT, REJECT, DEFER` | `AuditDecision` enum | `CHECK (decision IN (...))` | Valid decision ACCEPTS | `MAYBE` decision REJECTS | **PASS** |
| **PURGE Tombstone Retention** | §48 PURGED keeps payload_id | `MemoryRecord` tombstone shape | `CHECK` payload_id remains | PURGED w/ payload ACCEPTS | PURGED w/ inline REJECTS | **PASS** |
| **Evidence Record Scopes** | §44 BRANCH -> branch_id req | `EvidenceRecord` rejects w/o branch | `CHECK` branch_id NOT NULL | `BRANCH + branch_id` ACCEPTS | `BRANCH + NULL` REJECTS | **PASS** |
| **DraftPatch Boundary** | ADR-008 Discriminated Union | `DraftPatchOperation` typed | N/A (RAM LLM boundary) | Valid typed ops ACCEPTS | `dict[str, Any]` REJECTS | **PASS** |
| **JsonValue Recursive** | ADR-011 Nominal recursive | `JsonValue` TypeAliasType | `json_valid()` in SQLite | Arbitrary JSON ACCEPTS | Python object REJECTS | **PASS** |
| **Commit Revision Uniqueness** | §47 `UNIQUE(branch_id, revision)` | Domain model | `UNIQUE(branch_id, revision)` | Next revision ACCEPTS | Duplicate revision REJECTS | **PASS** |
| **Record Links Uniqueness** | §49 `UNIQUE(src, tgt, rel)` | Domain model | `UNIQUE(src, tgt, relation_type)` | Distinct relation ACCEPTS | Duplicate relation REJECTS | **PASS** |
| **Conflict Records Role** | §53 `role IN (WINNER, ...)` | `ConflictRecordRole` | `CHECK (role IN (...))` | Valid role ACCEPTS | Invalid role REJECTS | **PASS** |

