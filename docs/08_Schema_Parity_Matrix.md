# Schema Parity Matrix (OLA 1 Correction)

| Concept | Pydantic (Coder 1) | SQLite (Coder 2) | v1.1 Spec | Result |
|---------|-------------------|------------------|-----------|--------|
| Branch revision | `branch_id` PK | `branches.current_revision` | required | PASS |
| Core snapshot | `core_version` | `core_snapshots` table | required | PASS |
| Branch contracts | `contract_id` | `branch_contracts` + UNIQUE | required | PASS |
| Mount policies | `mount_policy_id` | `mount_policies` structured | structured | PASS |
| Enum CHECK constraints | Pydantic `StrEnum` | All tables `CHECK (col IN (...))` | required | PASS |
| Storage: INLINE | `MemoryRecord` rejects inline w/o value | `CHECK` prevents payload_id | required | PASS |
| Storage: VAULT_REF | `MemoryRecord` rejects vault w/o payload | `CHECK` prevents inline_value | required | PASS |
| Storage: NONE | `MemoryRecord` rejects value on NONE | `CHECK` prevents both | required | PASS |
| Personal Vault | `MemoryRecord` PERSONAL→VAULT_REF | `CHECK` prevents INLINE | required | PASS |
| Payload destroyed | `PayloadObject` rejects DESTROYED w/ keys | `CHECK` forces keys NULL | required | PASS |
| Patch hash | Not unique in Pydantic | `ix_patches_patch_hash` non-unique | non-unique | PASS |
| Patch replay | N/A | `commits.patch_id` UNIQUE | blocked by patch_id | PASS |
| Audit decision | Pydantic `AuditDecision` enum | Enum `CHECK` | enum | PASS |
| PURGE tombstone | `MemoryRecord` PURGED keeps payload, inline NULL | `CHECK` payload_id remains | payload ref remains | PASS |
| Evidence Record scopes | `EvidenceRecord` rejects BRANCH w/o branch_id | `CHECK` branch_id required if BRANCH | branch_id required | PASS |
| Patch Status Enum | Pydantic `PatchStatus` | Enum `CHECK` | enum | PASS |
